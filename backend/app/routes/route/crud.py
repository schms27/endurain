"""CRUD operations for planned routes."""

import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity.models as activity_models
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.crud as activity_streams_crud
import activities.activity_streams.models as activity_streams_models
import core.decorators as core_decorators
import core.geo as core_geo
import core.sanitization as core_sanitization
import routes.constants as routes_constants
import routes.route.models as route_models
import routes.route.schema as route_schema
import routes.route.utils as route_utils
import routes.route_file_import.parsers as route_parsers
import server_settings.utils as server_settings_utils
import users.users.models as users_models

_Route = route_models.Route
_NOT_FOUND = "Route not found"


def present_route(route: route_models.Route, *, is_owner: bool) -> route_schema.RouteRead:
    """
    Shape a route for its viewer.

    The owner sees everything. Everyone else loses the owner-only fields
    and, when ``hide_endpoints_m`` is set, sees the trimmed geometry with
    statistics recomputed and points of interest near the hidden ends
    removed.

    Args:
        route: The route ORM instance.
        is_owner: Whether the viewer owns the route.

    Returns:
        The route as the viewer may see it.
    """
    read = route_schema.RouteRead.model_validate(route)
    if is_owner:
        return read.model_copy(update={"is_owner": True})

    updates: dict[str, object] = {
        "is_owner": False,
        "share_token": None,
        "source_activity_id": None,
        "original_filename": None,
    }
    hidden = route.hide_endpoints_m or 0
    if hidden > 0:
        trimmed = route_utils.trim_endpoints(route.geometry, hidden)
        ends = [(route.start_lat, route.start_lon), (route.end_lat, route.end_lon)]
        updates["geometry"] = trimmed
        updates["waypoints"] = [
            poi for poi in read.waypoints if not route_utils.near_any(poi.lat, poi.lon, ends, hidden)
        ]
        try:
            stats = route_utils.build_route_geometry([(point[0], point[1], point[2]) for point in trimmed])
        except route_utils.RouteGeometryError:
            updates.update(
                distance=0.0,
                elevation_gain=None,
                elevation_loss=None,
                elevation_min=None,
                elevation_max=None,
                is_loop=False,
            )
        else:
            updates.update(
                distance=stats.distance,
                elevation_gain=stats.elevation_gain,
                elevation_loss=stats.elevation_loss,
                elevation_min=stats.elevation_min,
                elevation_max=stats.elevation_max,
                is_loop=stats.is_loop,
            )
    return read.model_copy(update=updates)


def _clean_name(name: str | None, fallback: str) -> str:
    """
    Sanitise a route name, falling back when nothing usable remains.

    Args:
        name: Raw name.
        fallback: Name to use when the cleaned name is empty.

    Returns:
        The cleaned name (at most 250 characters).
    """
    cleaned = core_sanitization.sanitize_plain_text(name) if name else None
    cleaned = cleaned.strip() if cleaned else None
    return (cleaned or fallback)[:250]


def _store(
    user_id: int,
    geometry: route_utils.RouteGeometry,
    db: Session,
    **fields: object,
) -> route_schema.RouteRead:
    """
    Insert a route row and return it.

    Args:
        user_id: Owner user ID.
        geometry: Derived geometry and statistics.
        db: Database session.
        **fields: Remaining column values.

    Returns:
        The created route.
    """
    (start_lat, start_lon), (end_lat, end_lon) = geometry.geometry[0][:2], geometry.geometry[-1][:2]
    route = _Route(
        user_id=user_id,
        geometry=geometry.geometry,
        distance=geometry.distance,
        elevation_gain=geometry.elevation_gain,
        elevation_loss=geometry.elevation_loss,
        elevation_min=geometry.elevation_min,
        elevation_max=geometry.elevation_max,
        is_loop=geometry.is_loop,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        bbox_min_lat=geometry.bbox.min_lat,
        bbox_min_lon=geometry.bbox.min_lon,
        bbox_max_lat=geometry.bbox.max_lat,
        bbox_max_lon=geometry.bbox.max_lon,
        **fields,
    )
    try:
        db.add(route)
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return present_route(route, is_owner=True)


def import_route(
    user_id: int,
    data: bytes,
    filename: str,
    extension: str,
    db: Session,
) -> route_schema.RouteRead:
    """
    Create a route from an uploaded GPX, TCX or FIT file.

    Args:
        user_id: Owner user ID.
        data: File contents (already validated and size-checked).
        filename: Original file name, used for the default name.
        extension: Lowercase extension without the dot.
        db: Database session.

    Returns:
        The created route.

    Raises:
        HTTPException: 400 if the file cannot be read as a route.
    """
    try:
        parsed = route_parsers.parse_route_file(data, extension)
        geometry = route_utils.build_route_geometry(parsed.points)
    except (route_parsers.RouteFileError, route_utils.RouteGeometryError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    description = core_sanitization.sanitize_markdown(parsed.description) if parsed.description else None
    return _store(
        user_id,
        geometry,
        db,
        name=_clean_name(parsed.name, route_utils.default_route_name(filename)),
        description=description[:2500] if description else None,
        activity_type=None,
        source=routes_constants.RouteSource.IMPORT.value,
        source_activity_id=None,
        original_filename=_clean_name(filename, "route")[:250],
        waypoints=[poi.to_dict() for poi in parsed.pois],
    )


def create_route_from_activity(
    user_id: int,
    activity_id: int,
    request: route_schema.RouteFromActivity,
    db: Session,
) -> route_schema.RouteRead:
    """
    Save (part of) one of the user's activities as a route.

    Timestamps are dropped; elevation is joined from the elevation stream.

    Args:
        user_id: Owner user ID (must own the activity).
        activity_id: Source activity ID.
        request: Optional name and slice.
        db: Database session.

    Returns:
        The created route.

    Raises:
        HTTPException: 404 if the activity is missing or not owned, 400 if
            it has no GPS data or the slice is invalid.
    """
    activity = activity_crud.get_activity_by_id(activity_id, db)
    if activity is None or activity.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    map_stream = activity_streams_crud.get_activity_stream_by_type(
        activity_id, activity_streams_constants.STREAM_TYPE_MAP, user_id, db
    )
    if map_stream is None or not map_stream.stream_waypoints:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activity has no GPS data")
    elevation_stream = activity_streams_crud.get_activity_stream_by_type(
        activity_id, activity_streams_constants.STREAM_TYPE_ELEVATION, user_id, db
    )

    waypoints = map_stream.stream_waypoints
    start = request.start_index if request.start_index is not None else 0
    end = request.end_index if request.end_index is not None else len(waypoints) - 1
    if end >= len(waypoints) or start >= end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slice is outside the GPS stream")

    elevation_by_time = {
        waypoint.get("time"): waypoint.get("ele")
        for waypoint in (elevation_stream.stream_waypoints if elevation_stream else [])
        if isinstance(waypoint, dict) and waypoint.get("ele") is not None
    }
    points = []
    for waypoint in waypoints[start : end + 1]:
        elevation = elevation_by_time.get(waypoint.get("time"))
        point = route_parsers.valid_point(waypoint.get("lat"), waypoint.get("lon"), elevation)
        if point is not None:
            points.append(point)
    try:
        geometry = route_utils.build_route_geometry(points)
    except route_utils.RouteGeometryError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    return _store(
        user_id,
        geometry,
        db,
        name=_clean_name(request.name or activity.name, "Route"),
        description=None,
        activity_type=activity.activity_type,
        source=routes_constants.RouteSource.ACTIVITY.value,
        source_activity_id=activity.id,
        original_filename=None,
        waypoints=[],
        city=activity.city,
        town=activity.town,
        country=activity.country,
    )


@core_decorators.handle_db_errors
def list_routes(
    user_id: int,
    db: Session,
    *,
    query: str | None = None,
    activity_type: int | None = None,
    page_number: int = 1,
    num_records: int = 25,
) -> route_schema.RoutesPage:
    """
    One page of the user's routes, newest first.

    Args:
        user_id: Owner user ID.
        db: Database session.
        query: Case-insensitive name search.
        activity_type: Only routes for this activity type.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        The routes on the page and the total count.
    """
    conditions = [_Route.user_id == user_id]
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(_Route.name.ilike(f"%{escaped}%", escape="\\"))
    if activity_type is not None:
        conditions.append(_Route.activity_type == activity_type)

    total = db.scalar(select(func.count(_Route.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(_Route)
        .where(*conditions)
        .order_by(_Route.created_at.desc(), _Route.id.desc())
        .offset((page_number - 1) * num_records)
        .limit(num_records)
    ).all()
    return route_schema.RoutesPage(
        records=[route_schema.RouteSummary.model_validate(row) for row in rows],
        total=int(total),
    )


@core_decorators.handle_db_errors
def list_user_routes(
    owner_id: int,
    viewer_id: int,
    db: Session,
    *,
    page_number: int = 1,
    num_records: int = 25,
) -> route_schema.RoutesPage:
    """
    One page of a user's routes that the viewer may see, newest first.

    Args:
        owner_id: User whose routes are listed.
        viewer_id: Requesting user ID.
        db: Database session.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        The visible routes on the page (trimmed for non-owners) and the
        total count.
    """
    is_owner = owner_id == viewer_id
    conditions = [_Route.user_id == owner_id]
    if not is_owner:
        conditions.append(activity_crud.owner_visibility_condition(_Route, viewer_id))

    total = db.scalar(select(func.count(_Route.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(_Route)
        .where(*conditions)
        .order_by(_Route.created_at.desc(), _Route.id.desc())
        .offset((page_number - 1) * num_records)
        .limit(num_records)
    ).all()
    return route_schema.RoutesPage(
        records=[route_schema.RouteSummary.model_validate(present_route(row, is_owner=is_owner)) for row in rows],
        total=int(total),
    )


def get_owned_route_model(route_id: int, user_id: int, db: Session) -> route_models.Route:
    """
    Get one of the user's routes, or raise 404.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The route ORM instance.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = db.scalar(select(_Route).where(_Route.id == route_id, _Route.user_id == user_id))
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return route


def get_visible_route_model(route_id: int, user_id: int, db: Session) -> route_models.Route:
    """
    Get a route the user owns or may see (public, or followers-only for an
    accepted follower), or raise 404.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The route ORM instance.

    Raises:
        HTTPException: 404 if missing or not visible.
    """
    route = db.scalar(
        select(_Route).where(
            _Route.id == route_id,
            or_(_Route.user_id == user_id, activity_crud.owner_visibility_condition(_Route, user_id)),
        )
    )
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return route


def get_route(route_id: int, user_id: int, db: Session) -> route_schema.RouteRead:
    """
    Get a route the user owns or may see.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The route, trimmed for non-owners.

    Raises:
        HTTPException: 404 if missing or not visible.
    """
    route = get_visible_route_model(route_id, user_id, db)
    return present_route(route, is_owner=route.user_id == user_id)


def edit_route(
    route_id: int,
    user_id: int,
    edit: route_schema.RouteEdit,
    db: Session,
) -> route_schema.RouteRead:
    """
    Edit a route's name, description or intended sport.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID (must own the route).
        edit: Changes to apply.
        db: Database session.

    Returns:
        The updated route.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = get_owned_route_model(route_id, user_id, db)
    changes = edit.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        route.name = _clean_name(changes["name"], route.name)
    if "description" in changes:
        description = changes["description"]
        route.description = core_sanitization.sanitize_markdown(description) if description else None
    if "activity_type" in changes:
        route.activity_type = changes["activity_type"]
    if changes.get("visibility") is not None:
        route.visibility = int(changes["visibility"])
    if changes.get("hide_endpoints_m") is not None:
        route.hide_endpoints_m = changes["hide_endpoints_m"]
    return _commit(route, db)


def _commit(route: route_models.Route, db: Session) -> route_schema.RouteRead:
    """
    Commit changes to an owned route and return the owner's view.

    Args:
        route: The modified route.
        db: Database session.

    Returns:
        The updated route.
    """
    try:
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return present_route(route, is_owner=True)


def create_share_token(route_id: int, user_id: int, db: Session) -> route_schema.RouteRead:
    """
    Create or rotate a route's unlisted share link.

    Rotating invalidates the previous link.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID (must own the route).
        db: Database session.

    Returns:
        The route with its new share token.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = get_owned_route_model(route_id, user_id, db)
    route.share_token = secrets.token_urlsafe(routes_constants.SHARE_TOKEN_BYTES)
    return _commit(route, db)


def revoke_share_token(route_id: int, user_id: int, db: Session) -> route_schema.RouteRead:
    """
    Revoke a route's unlisted share link.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID (must own the route).
        db: Database session.

    Returns:
        The route without a share token.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = get_owned_route_model(route_id, user_id, db)
    route.share_token = None
    return _commit(route, db)


def _public_link_settings(db: Session) -> tuple[bool, bool]:
    """
    Read the public-link server settings.

    Args:
        db: Database session.

    Returns:
        Tuple of (public links enabled, creator info shown on public links).
    """
    settings = server_settings_utils.get_server_settings_or_404(db)
    return bool(settings.public_shareable_links), bool(settings.public_shareable_links_user_info)


def get_shared_route_model(token: str, db: Session) -> route_models.Route:
    """
    Get a route by its unlisted share token, or raise 404.

    Share links work only while public shareable links are enabled, and
    regardless of the route's visibility.

    Args:
        token: Share token.
        db: Database session.

    Returns:
        The route ORM instance.

    Raises:
        HTTPException: 404 if links are disabled or the token is unknown.
    """
    links_enabled, _ = _public_link_settings(db)
    route = db.scalar(select(_Route).where(_Route.share_token == token)) if links_enabled else None
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return route


def get_public_route_model(route_id: int, db: Session) -> route_models.Route:
    """
    Get a public route for an anonymous viewer, or raise 404.

    Args:
        route_id: Route ID.
        db: Database session.

    Returns:
        The route ORM instance.

    Raises:
        HTTPException: 404 if links are disabled or the route is not public.
    """
    links_enabled, _ = _public_link_settings(db)
    route = (
        db.scalar(select(_Route).where(_Route.id == route_id, activity_crud.owner_visibility_condition(_Route, None)))
        if links_enabled
        else None
    )
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return route


def present_public_route(route: route_models.Route, db: Session) -> route_schema.PublicRouteRead:
    """
    Shape a route for its public page.

    Args:
        route: The route ORM instance.
        db: Database session.

    Returns:
        The route as a non-owner sees it, with its creator when the server
        shares user info on public links.
    """
    _, show_user_info = _public_link_settings(db)
    owner = None
    if show_user_info:
        user = db.get(users_models.Users, route.user_id)
        if user is not None:
            owner = route_schema.RouteOwner(id=user.id, name=user.name, username=user.username)
    view = present_route(route, is_owner=False)
    return route_schema.PublicRouteRead(**dict(view), owner=owner)


def copy_route(route: route_models.Route, user_id: int, db: Session) -> route_schema.RouteRead:
    """
    Save a copy of a route the user may see into their library.

    The copy is built from what the user sees (the trimmed geometry for
    someone else's route), is private, and points back to the original.

    Args:
        route: The source route, already access-checked.
        user_id: Requesting user ID (owner of the copy).
        db: Database session.

    Returns:
        The new route.

    Raises:
        HTTPException: 400 if too little of the route is visible to copy.
    """
    view = present_route(route, is_owner=route.user_id == user_id)
    try:
        geometry = route_utils.build_route_geometry([(point[0], point[1], point[2]) for point in view.geometry])
    except route_utils.RouteGeometryError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    return _store(
        user_id,
        geometry,
        db,
        name=view.name,
        description=view.description,
        activity_type=view.activity_type,
        source=routes_constants.RouteSource.COPY.value,
        source_activity_id=None,
        source_route_id=route.id,
        original_filename=None,
        waypoints=[poi.model_dump(mode="json") for poi in view.waypoints],
        city=route.city,
        town=route.town,
        country=route.country,
    )


def _frequent_start_near(user_id: int, lat: float, lon: float, db: Session) -> bool:
    """
    Check whether several of the user's activities start near a point.

    Activities are pre-filtered by bounding box; then the first GPS sample
    of each candidate is compared with the point.

    Args:
        user_id: Owner user ID.
        lat: Latitude of the point.
        lon: Longitude of the point.
        db: Database session.

    Returns:
        True if at least ``HOME_MIN_ACTIVITIES`` activities start within
        ``HOME_RADIUS_M`` of the point.
    """
    radius = routes_constants.HOME_RADIUS_M
    box = core_geo.BoundingBox(lat, lon, lat, lon).padded(radius)
    activity = activity_models.Activity
    stream = activity_streams_models.ActivityStreams
    rows = db.execute(
        select(
            stream.stream_waypoints[(0, "lat")].as_float(),
            stream.stream_waypoints[(0, "lon")].as_float(),
        )
        .join(activity, activity.id == stream.activity_id)
        .where(
            activity.user_id == user_id,
            stream.stream_type == activity_streams_constants.STREAM_TYPE_MAP,
            activity.bbox_min_lat <= box.max_lat,
            activity.bbox_max_lat >= box.min_lat,
            activity.bbox_min_lon <= box.max_lon,
            activity.bbox_max_lon >= box.min_lon,
        )
    ).all()
    starts = [
        (start_lat, start_lon) for start_lat, start_lon in rows if start_lat is not None and start_lon is not None
    ]
    nearby = sum(1 for start in starts if route_utils.near_any(lat, lon, [start], radius))
    return nearby >= routes_constants.HOME_MIN_ACTIVITIES


@core_decorators.handle_db_errors
def home_location_warning(route_id: int, user_id: int, db: Session) -> route_schema.RouteHomeWarning:
    """
    Check whether a route's visible endpoints may reveal the owner's home.

    Uses the endpoints other users see, so trimming enough clears the
    warning.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID (must own the route).
        db: Database session.

    Returns:
        Which visible endpoints lie near a frequent activity start.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = get_owned_route_model(route_id, user_id, db)
    visible = route_utils.trim_endpoints(route.geometry, route.hide_endpoints_m or 0)
    if len(visible) < 2:
        return route_schema.RouteHomeWarning(start_near_home=False, end_near_home=False)
    (start_lat, start_lon), (end_lat, end_lon) = visible[0][:2], visible[-1][:2]
    return route_schema.RouteHomeWarning(
        start_near_home=_frequent_start_near(user_id, start_lat, start_lon, db),
        end_near_home=_frequent_start_near(user_id, end_lat, end_lon, db),
    )


def delete_route(route_id: int, user_id: int, db: Session) -> None:
    """
    Delete one of the user's routes.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID (must own the route).
        db: Database session.

    Returns:
        None.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    route = get_owned_route_model(route_id, user_id, db)
    try:
        db.delete(route)
        db.commit()
    except Exception:
        db.rollback()
        raise
