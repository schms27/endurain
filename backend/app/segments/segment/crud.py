"""CRUD operations for segments."""

from fastapi import HTTPException, status
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity.schema as activity_schema
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.crud as activity_streams_crud
import core.decorators as core_decorators
import core.geo as core_geo
import core.sanitization as core_sanitization
import segments.constants as segments_constants
import segments.matching.queue as segments_queue
import segments.segment.models as segment_models
import segments.segment.schema as segment_schema
import segments.segment.utils as segment_utils
import segments.segment_efforts.models as segment_efforts_models
import server_settings.crud as server_settings_crud
import users.users.models as users_models
import users.users.schema as users_schema


def _visible_to(user_id: int):
    """
    Condition for segments a user may see.

    Args:
        user_id: Requesting user ID.

    Returns:
        SQLAlchemy condition: public and not archived, or owned.
    """
    return or_(
        segment_models.Segment.user_id == user_id,
        (segment_models.Segment.visibility == segments_constants.SEGMENT_VISIBILITY_PUBLIC)
        & segment_models.Segment.is_archived.is_(False),
    )


def _bbox_intersects(stmt: Select, bbox: core_geo.BoundingBox) -> Select:
    """
    Restrict a segment query to segments overlapping a bounding box.

    Args:
        stmt: Segment select statement.
        bbox: Bounding box to intersect.

    Returns:
        The filtered statement.
    """
    return stmt.where(
        segment_models.Segment.bbox_min_lat <= bbox.max_lat,
        segment_models.Segment.bbox_max_lat >= bbox.min_lat,
        segment_models.Segment.bbox_min_lon <= bbox.max_lon,
        segment_models.Segment.bbox_max_lon >= bbox.min_lon,
    )


@core_decorators.handle_db_errors
def get_segment_model(segment_id: int, db: Session) -> segment_models.Segment | None:
    """
    Get a segment by ID without permission checks.

    Args:
        segment_id: Segment ID.
        db: Database session.

    Returns:
        The segment ORM instance, or None.
    """
    return db.get(segment_models.Segment, segment_id)


@core_decorators.handle_db_errors
def get_segment_visible_to_user(
    segment_id: int,
    user_id: int,
    db: Session,
) -> segment_schema.SegmentRead | None:
    """
    Get a segment if the user may see it.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The segment, or None when missing or not visible.
    """
    segment = db.scalar(
        select(segment_models.Segment).where(
            segment_models.Segment.id == segment_id,
            _visible_to(user_id),
        )
    )
    return segment_schema.SegmentRead.model_validate(segment) if segment else None


@core_decorators.handle_db_errors
def list_segments(
    user_id: int,
    db: Session,
    *,
    sport_group: segments_constants.SportGroup | None = None,
    created_by_me: bool = False,
    bbox: core_geo.BoundingBox | None = None,
    query: str | None = None,
    page_number: int = 1,
    num_records: int = 25,
) -> list[segment_schema.SegmentSummary]:
    """
    List segments visible to a user, with optional filters.

    Args:
        user_id: Requesting user ID.
        db: Database session.
        sport_group: Only segments of this sport group.
        created_by_me: Only segments created by the user.
        bbox: Only segments overlapping this bounding box.
        query: Case-insensitive name search.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        Matching segments, newest first.
    """
    stmt = select(segment_models.Segment).where(_visible_to(user_id))
    if created_by_me:
        stmt = stmt.where(segment_models.Segment.user_id == user_id)
    if sport_group is not None:
        stmt = stmt.where(segment_models.Segment.sport_group == sport_group.value)
    if bbox is not None:
        stmt = _bbox_intersects(stmt, bbox)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(segment_models.Segment.name.ilike(f"%{escaped}%", escape="\\"))
    stmt = (
        stmt.order_by(segment_models.Segment.created_at.desc(), segment_models.Segment.id.desc())
        .offset((page_number - 1) * num_records)
        .limit(num_records)
    )
    return [segment_schema.SegmentSummary.model_validate(segment) for segment in db.scalars(stmt).all()]


@core_decorators.handle_db_errors
def get_candidate_segments(
    sport_group: segments_constants.SportGroup,
    bbox: core_geo.BoundingBox,
    owner_id: int,
    db: Session,
) -> list[segment_models.Segment]:
    """
    Segments an activity could match: same sport group, overlapping
    bounding box, not archived, and public or owned by the activity owner.

    Args:
        sport_group: Sport group of the activity.
        bbox: The activity's (padded) bounding box.
        owner_id: Owner of the activity.
        db: Database session.

    Returns:
        Candidate segment ORM instances.
    """
    stmt = select(segment_models.Segment).where(
        segment_models.Segment.sport_group == sport_group.value,
        segment_models.Segment.is_archived.is_(False),
        or_(
            segment_models.Segment.visibility == segments_constants.SEGMENT_VISIBILITY_PUBLIC,
            segment_models.Segment.user_id == owner_id,
        ),
    )
    return list(db.scalars(_bbox_intersects(stmt, bbox)).all())


@core_decorators.handle_db_errors
def get_outdated_segment_ids(db: Session) -> list[int]:
    """
    IDs of segments matched by an older matcher version.

    Args:
        db: Database session.

    Returns:
        Segment IDs to rematch.
    """
    stmt = select(segment_models.Segment.id).where(
        segment_models.Segment.matcher_version < segments_constants.MATCHER_VERSION,
        segment_models.Segment.is_archived.is_(False),
    )
    return list(db.scalars(stmt).all())


def _check_creation_allowed(user_id: int, visibility: int, db: Session) -> None:
    """
    Enforce the server settings for creating or publishing a segment.

    Args:
        user_id: Requesting user ID.
        visibility: Requested segment visibility.
        db: Database session.

    Returns:
        None.

    Raises:
        HTTPException: 403 when segments are disabled, or when only
            admins may create public segments and the user is not one.
    """
    settings = server_settings_crud.get_server_settings(db)
    if settings is None:
        return
    if not settings.segments_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Segments are disabled on this server")
    if visibility != segments_constants.SEGMENT_VISIBILITY_PUBLIC or settings.segments_public_creation != "admins":
        return
    access_type = db.scalar(select(users_models.Users.access_type).where(users_models.Users.id == user_id))
    if access_type != users_schema.UserAccessType.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators may create public segments",
        )


def _slice_geometry(
    user_id: int,
    activity_id: int,
    start_index: int,
    end_index: int,
    db: Session,
) -> tuple[activity_schema.Activity, segments_constants.SportGroup, segment_utils.SegmentGeometry]:
    """
    Build segment geometry from a slice of one of the user's activities.

    Args:
        user_id: Requesting user ID (must own the activity).
        activity_id: Source activity ID.
        start_index: First lat/lon stream index of the slice.
        end_index: Last lat/lon stream index of the slice (inclusive).
        db: Database session.

    Returns:
        Tuple of (activity, sport group, segment geometry).

    Raises:
        HTTPException: 404 if the activity is missing or not owned,
            400 if its sport or GPS slice cannot become a segment.
    """
    activity = activity_crud.get_activity_by_id(activity_id, db)
    if activity is None or activity.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    sport_group = segments_constants.ACTIVITY_TYPE_SPORT_GROUP.get(activity.activity_type)
    if sport_group is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segments are not supported for this activity type",
        )

    map_stream = activity_streams_crud.get_activity_stream_by_type(
        activity_id, activity_streams_constants.STREAM_TYPE_MAP, user_id, db
    )
    if map_stream is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activity has no GPS data")
    elevation_stream = activity_streams_crud.get_activity_stream_by_type(
        activity_id, activity_streams_constants.STREAM_TYPE_ELEVATION, user_id, db
    )

    try:
        geometry = segment_utils.build_segment_geometry(
            map_stream.stream_waypoints,
            elevation_stream.stream_waypoints if elevation_stream else None,
            start_index,
            end_index,
            sport_group,
        )
    except segment_utils.SegmentGeometryError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    return activity, sport_group, geometry


@core_decorators.handle_db_errors
def get_similar_segments(
    user_id: int,
    activity_id: int,
    start_index: int,
    end_index: int,
    db: Session,
) -> list[segment_schema.SegmentSummary]:
    """
    Visible segments that duplicate a proposed activity slice.

    A segment is similar when it has the same sport group and direction,
    its start and end lie within ``SIMILAR_ENDPOINT_M`` of the slice's,
    and its length differs by at most ``SIMILAR_DISTANCE_RATIO``.

    Args:
        user_id: Requesting user ID (must own the activity).
        activity_id: Source activity ID.
        start_index: First lat/lon stream index of the slice.
        end_index: Last lat/lon stream index of the slice (inclusive).
        db: Database session.

    Returns:
        Similar segments, closest length first.
    """
    _, sport_group, geometry = _slice_geometry(user_id, activity_id, start_index, end_index, db)
    (start_lat, start_lon), (end_lat, end_lon) = geometry.start, geometry.end
    near_start = core_geo.BoundingBox(start_lat, start_lon, start_lat, start_lon).padded(
        segments_constants.SIMILAR_ENDPOINT_M
    )
    stmt = select(segment_models.Segment).where(
        _visible_to(user_id),
        segment_models.Segment.sport_group == sport_group.value,
        segment_models.Segment.start_lat.between(near_start.min_lat, near_start.max_lat),
        segment_models.Segment.start_lon.between(near_start.min_lon, near_start.max_lon),
    )
    similar = []
    for candidate in db.scalars(stmt).all():
        start_gap = float(core_geo.haversine_m(start_lat, start_lon, candidate.start_lat, candidate.start_lon))
        end_gap = float(core_geo.haversine_m(end_lat, end_lon, candidate.end_lat, candidate.end_lon))
        length_ratio = abs(float(candidate.distance) - geometry.distance) / geometry.distance
        if (
            start_gap <= segments_constants.SIMILAR_ENDPOINT_M
            and end_gap <= segments_constants.SIMILAR_ENDPOINT_M
            and length_ratio <= segments_constants.SIMILAR_DISTANCE_RATIO
        ):
            similar.append((length_ratio, candidate))
    similar.sort(key=lambda pair: (pair[0], pair[1].id))
    return [segment_schema.SegmentSummary.model_validate(candidate) for _, candidate in similar]


def create_segment(
    user_id: int,
    segment: segment_schema.SegmentCreate,
    db: Session,
) -> segment_schema.SegmentRead:
    """
    Create a segment from a slice of one of the user's activities.

    The new segment is queued for a backfill against existing activities.

    Args:
        user_id: Creator user ID.
        segment: Creation request.
        db: Database session.

    Returns:
        The created segment.

    Raises:
        HTTPException: 403 if the server settings forbid it, 404 if the
            activity is missing or not owned, 400 if its sport or GPS
            slice cannot become a segment.
    """
    _check_creation_allowed(user_id, segment.visibility, db)
    activity, sport_group, geometry = _slice_geometry(
        user_id, segment.activity_id, segment.start_index, segment.end_index, db
    )

    (start_lat, start_lon), (end_lat, end_lon) = geometry.start, geometry.end
    db_segment = segment_models.Segment(
        user_id=user_id,
        name=core_sanitization.sanitize_plain_text(segment.name) or "Segment",
        description=(core_sanitization.sanitize_markdown(segment.description) if segment.description else None),
        sport_group=sport_group.value,
        visibility=segment.visibility,
        geometry=geometry.geometry,
        distance=geometry.distance,
        elevation_gain=geometry.elevation_gain,
        elevation_loss=geometry.elevation_loss,
        average_grade=geometry.average_grade,
        maximum_grade=geometry.maximum_grade,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        bbox_min_lat=geometry.bbox.min_lat,
        bbox_min_lon=geometry.bbox.min_lon,
        bbox_max_lat=geometry.bbox.max_lat,
        bbox_max_lon=geometry.bbox.max_lon,
        city=activity.city,
        town=activity.town,
        country=activity.country,
        source_activity_id=activity.id,
        is_archived=False,
        matcher_version=segments_constants.MATCHER_VERSION,
        effort_count=0,
        athlete_count=0,
    )
    try:
        db.add(db_segment)
        db.flush()
        segments_queue.enqueue_segment(db_segment.id, db, commit=False)
        db.commit()
        db.refresh(db_segment)
    except Exception:
        db.rollback()
        raise
    return segment_schema.SegmentRead.model_validate(db_segment)


def _get_owned_segment(segment_id: int, user_id: int, db: Session) -> segment_models.Segment:
    """
    Get a segment owned by the user, or raise 404.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The segment ORM instance.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    segment = db.scalar(
        select(segment_models.Segment).where(
            segment_models.Segment.id == segment_id,
            segment_models.Segment.user_id == user_id,
        )
    )
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return segment


def edit_segment(
    segment_id: int,
    user_id: int,
    edit: segment_schema.SegmentEdit,
    db: Session,
) -> segment_schema.SegmentRead:
    """
    Edit a segment's name, description or visibility.

    A visibility change requeues a full backfill: going private drops
    other users' efforts, going public picks them up.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID (must own the segment).
        edit: Changes to apply.
        db: Database session.

    Returns:
        The updated segment.

    Raises:
        HTTPException: 404 if missing or not owned, 403 if publishing
            is not allowed.
    """
    segment = _get_owned_segment(segment_id, user_id, db)
    changes = edit.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        segment.name = core_sanitization.sanitize_plain_text(changes["name"]) or "Segment"
    if "description" in changes:
        description = changes["description"]
        segment.description = core_sanitization.sanitize_markdown(description) if description else None
    if changes.get("visibility") is not None and changes["visibility"] != segment.visibility:
        _check_creation_allowed(user_id, changes["visibility"], db)
        segment.visibility = changes["visibility"]
        segments_queue.enqueue_segment(segment.id, db, commit=False)
    try:
        db.commit()
        db.refresh(segment)
    except Exception:
        db.rollback()
        raise
    return segment_schema.SegmentRead.model_validate(segment)


def delete_segment(segment_id: int, user_id: int, db: Session) -> None:
    """
    Delete a segment and, by cascade, its efforts.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID (must own the segment).
        db: Database session.

    Returns:
        None.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    segment = _get_owned_segment(segment_id, user_id, db)
    try:
        # Explicit delete so SQLite-backed tests behave like PostgreSQL's
        # ON DELETE CASCADE.
        db.execute(
            delete(segment_efforts_models.SegmentEffort).where(
                segment_efforts_models.SegmentEffort.segment_id == segment.id
            )
        )
        db.delete(segment)
        db.commit()
    except Exception:
        db.rollback()
        raise


def request_rematch(segment_id: int, user_id: int, db: Session) -> None:
    """
    Queue a full backfill of a segment owned by the user.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID (must own the segment).
        db: Database session.

    Returns:
        None.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    segment = _get_owned_segment(segment_id, user_id, db)
    segments_queue.enqueue_segment(segment.id, db)


def refresh_counts(segment_ids: set[int], db: Session) -> None:
    """
    Recompute effort and athlete counters (caller commits).

    Args:
        segment_ids: Segments whose counters changed.
        db: Database session.

    Returns:
        None.
    """
    for segment_id in segment_ids:
        segment = db.get(segment_models.Segment, segment_id)
        if segment is None:
            continue
        effort_count, athlete_count = db.execute(
            select(
                func.count(segment_efforts_models.SegmentEffort.id),
                func.count(func.distinct(segment_efforts_models.SegmentEffort.user_id)),
            ).where(
                segment_efforts_models.SegmentEffort.segment_id == segment_id,
                segment_efforts_models.SegmentEffort.is_excluded.is_(False),
            )
        ).one()
        segment.effort_count = int(effort_count)
        segment.athlete_count = int(athlete_count)
