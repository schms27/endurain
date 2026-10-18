"""CRUD operations for planned routes."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.crud as activity_streams_crud
import core.decorators as core_decorators
import core.sanitization as core_sanitization
import routes.constants as routes_constants
import routes.route.models as route_models
import routes.route.schema as route_schema
import routes.route.utils as route_utils
import routes.route_file_import.parsers as route_parsers

_Route = route_models.Route


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
    return route_schema.RouteRead.model_validate(route)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return route


def get_route(route_id: int, user_id: int, db: Session) -> route_schema.RouteRead:
    """
    Get one of the user's routes.

    Args:
        route_id: Route ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The route.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    return route_schema.RouteRead.model_validate(get_owned_route_model(route_id, user_id, db))


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
    try:
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return route_schema.RouteRead.model_validate(route)


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
