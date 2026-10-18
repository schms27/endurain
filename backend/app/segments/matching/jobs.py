"""Background jobs that turn queued work into segment efforts."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

import activities.activity.models as activity_models
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.models as activity_streams_models
import core.database as core_database
import core.geo as core_geo
import core.logger as core_logger
import segments.constants as segments_constants
import segments.matching.matcher as matcher
import segments.matching.models as matching_models
import segments.matching.queue as segments_queue
import segments.matching.streams as matching_streams
import segments.segment.crud as segment_crud
import segments.segment.models as segment_models
import segments.segment_efforts.crud as segment_efforts_crud
import segments.segment_efforts.models as segment_efforts_models

_METRIC_STREAM_TYPES: dict[int, str] = {
    activity_streams_constants.STREAM_TYPE_HR: "hr",
    activity_streams_constants.STREAM_TYPE_POWER: "power",
    activity_streams_constants.STREAM_TYPE_CADENCE: "cad",
}

_outdated_segments_checked = False


class _ActivityTrack:
    """Lazily loaded GPS track and metric streams of one activity."""

    def __init__(self, activity_id: int, db: Session) -> None:
        stream_types = [activity_streams_constants.STREAM_TYPE_MAP, *_METRIC_STREAM_TYPES]
        rows = db.execute(
            select(
                activity_streams_models.ActivityStreams.stream_type,
                activity_streams_models.ActivityStreams.stream_waypoints,
            ).where(
                activity_streams_models.ActivityStreams.activity_id == activity_id,
                activity_streams_models.ActivityStreams.stream_type.in_(stream_types),
            )
        ).all()
        waypoints = {row.stream_type: row.stream_waypoints for row in rows}
        self.track = matching_streams.track_from_waypoints(waypoints.get(activity_streams_constants.STREAM_TYPE_MAP))
        self.metrics = {
            key: matching_streams.values_by_time(waypoints.get(stream_type), key)
            for stream_type, key in _METRIC_STREAM_TYPES.items()
        }


def _efforts_for(
    activity: activity_models.Activity,
    data: _ActivityTrack,
    segment: segment_models.Segment,
) -> list[segment_efforts_models.SegmentEffort]:
    """
    Match one activity against one segment.

    Args:
        activity: The activity ORM instance.
        data: The activity's track and metric streams.
        segment: The segment ORM instance.

    Returns:
        New (unsaved) effort ORM instances.
    """
    if data.track.size < 2 or len(segment.geometry) < 2:
        return []
    matches = matcher.find_efforts(
        data.track.lats,
        data.track.lons,
        data.track.times,
        [point[0] for point in segment.geometry],
        [point[1] for point in segment.geometry],
    )
    efforts: list[segment_efforts_models.SegmentEffort] = []
    for match in matches:
        metrics = matching_streams.effort_metrics(
            data.metrics["hr"],
            data.metrics["power"],
            data.metrics["cad"],
            match.start_time,
            match.end_time,
        )
        elapsed = match.elapsed_time
        efforts.append(
            segment_efforts_models.SegmentEffort(
                segment_id=segment.id,
                activity_id=activity.id,
                user_id=activity.user_id,
                start_time=datetime.fromtimestamp(match.start_time, UTC),
                elapsed_time=Decimal(f"{elapsed:.3f}"),
                distance=match.distance_m,
                start_index=int(data.track.indices[match.start_index]),
                end_index=int(data.track.indices[match.end_index]),
                average_hr=metrics.average_hr,
                max_hr=metrics.max_hr,
                average_power=metrics.average_power,
                normalized_power=metrics.normalized_power,
                average_cad=metrics.average_cad,
                average_speed=segment.distance / elapsed if elapsed > 0 else None,
                is_excluded=False,
            )
        )
    return efforts


def _activity_bbox(activity: activity_models.Activity) -> core_geo.BoundingBox | None:
    """
    The activity's stored bounding box, if any.

    Args:
        activity: The activity ORM instance.

    Returns:
        The bounding box, or None if not computed yet.
    """
    if None in (activity.bbox_min_lat, activity.bbox_min_lon, activity.bbox_max_lat, activity.bbox_max_lon):
        return None
    return core_geo.BoundingBox(
        activity.bbox_min_lat,  # type: ignore[arg-type]
        activity.bbox_min_lon,  # type: ignore[arg-type]
        activity.bbox_max_lat,  # type: ignore[arg-type]
        activity.bbox_max_lon,  # type: ignore[arg-type]
    )


def match_activity(activity_id: int, db: Session) -> None:
    """
    Recompute every effort of one activity and commit.

    Existing efforts are replaced. Hidden activities, activities without
    GPS and unsupported sports end up with no efforts.

    Args:
        activity_id: Activity ID.
        db: Database session.

    Returns:
        None.
    """
    activity = db.get(activity_models.Activity, activity_id)
    if activity is None:
        return

    efforts: list[segment_efforts_models.SegmentEffort] = []
    sport_group = segments_constants.ACTIVITY_TYPE_SPORT_GROUP.get(activity.activity_type)
    bbox = _activity_bbox(activity)
    if sport_group is not None and bbox is not None and not activity.is_hidden:
        candidates = segment_crud.get_candidate_segments(
            sport_group,
            bbox.padded(segments_constants.GATE_RADIUS_M),
            activity.user_id,
            db,
        )
        if candidates:
            data = _ActivityTrack(activity.id, db)
            for segment in candidates:
                efforts.extend(_efforts_for(activity, data, segment))

    touched = segment_efforts_crud.replace_efforts(activity.id, efforts, db)
    segment_crud.refresh_counts(touched, db)
    db.commit()


def _candidate_activities(
    segment: segment_models.Segment,
    after_id: int,
    db: Session,
) -> list[activity_models.Activity]:
    """
    Next batch of activities that could match a segment.

    Args:
        segment: The segment ORM instance.
        after_id: Only activities with a higher ID.
        db: Database session.

    Returns:
        Activities ordered by ID, at most BACKFILL_BATCH_SIZE.
    """
    bbox = core_geo.BoundingBox(
        segment.bbox_min_lat, segment.bbox_min_lon, segment.bbox_max_lat, segment.bbox_max_lon
    ).padded(segments_constants.GATE_RADIUS_M)
    activity_types = segments_constants.SPORT_GROUP_ACTIVITY_TYPES[segments_constants.SportGroup(segment.sport_group)]
    stmt = select(activity_models.Activity).where(
        activity_models.Activity.id > after_id,
        activity_models.Activity.activity_type.in_(activity_types),
        activity_models.Activity.is_hidden.is_(False),
        activity_models.Activity.bbox_min_lat <= bbox.max_lat,
        activity_models.Activity.bbox_max_lat >= bbox.min_lat,
        activity_models.Activity.bbox_min_lon <= bbox.max_lon,
        activity_models.Activity.bbox_max_lon >= bbox.min_lon,
    )
    if segment.visibility != segments_constants.SEGMENT_VISIBILITY_PUBLIC:
        stmt = stmt.where(activity_models.Activity.user_id == segment.user_id)
    stmt = stmt.order_by(activity_models.Activity.id).limit(segments_constants.BACKFILL_BATCH_SIZE)
    return list(db.scalars(stmt).all())


def backfill_segment(
    item: matching_models.SegmentMatchQueue,
    deadline: float,
    db: Session,
) -> bool:
    """
    Match a segment against existing activities, resumably.

    A backfill starting at cursor 0 first drops all stored efforts of the
    segment, so it is a full recompute. Progress is saved after every
    batch; when the time budget runs out the item stays queued.

    Args:
        item: The queue item (``segment_id`` set).
        deadline: ``time.monotonic()`` value at which to stop.
        db: Database session.

    Returns:
        True when the backfill is complete.
    """
    segment = db.get(segment_models.Segment, item.segment_id)
    if segment is None:
        return True
    if item.cursor == 0:
        segment_efforts_crud.delete_segment_efforts(segment.id, db)
        db.commit()
    if segment.is_archived:
        segment_crud.refresh_counts({segment.id}, db)
        db.commit()
        return True

    cursor = item.cursor
    while True:
        batch = _candidate_activities(segment, cursor, db)
        for activity in batch:
            efforts = _efforts_for(activity, _ActivityTrack(activity.id, db), segment)
            segment_efforts_crud.replace_efforts(activity.id, efforts, db, segment_id=segment.id)
            cursor = activity.id
        db.commit()
        if batch:
            segments_queue.save_cursor(item.id, cursor, db)
        if len(batch) < segments_constants.BACKFILL_BATCH_SIZE:
            break
        if time.monotonic() >= deadline:
            return False

    segment_crud.refresh_counts({segment.id}, db)
    segment.matcher_version = segments_constants.MATCHER_VERSION
    db.commit()
    return True


def _enqueue_outdated_segments(db: Session) -> None:
    """
    Once per process, queue segments matched by an older matcher.

    Args:
        db: Database session.

    Returns:
        None.
    """
    global _outdated_segments_checked
    if _outdated_segments_checked:
        return
    for segment_id in segment_crud.get_outdated_segment_ids(db):
        segments_queue.enqueue_segment(segment_id, db, commit=False)
    db.commit()
    _outdated_segments_checked = True


@contextmanager
def _queue_lock() -> Iterator[bool]:
    """
    Hold a PostgreSQL advisory lock so only one worker drains the queue.

    The lock lives on a dedicated connection for the whole drain, since
    session-level advisory locks belong to a connection and a Session may
    switch connections between transactions. Other databases (tests) are
    always granted the lock.

    Yields:
        True if this process holds the lock.
    """
    if core_database.engine.dialect.name != "postgresql":
        yield True
        return
    with core_database.engine.connect() as connection:
        key = {"key": segments_constants.QUEUE_ADVISORY_LOCK_KEY}
        acquired = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), key).scalar())
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), key)
            connection.commit()


def drain_queue(db: Session, time_budget_s: float = segments_constants.QUEUE_DRAIN_TIME_BUDGET_S) -> int:
    """
    Process queue items until the queue is empty or time runs out.

    Args:
        db: Database session.
        time_budget_s: Seconds to spend before yielding.

    Returns:
        Number of queue items completed.
    """
    deadline = time.monotonic() + time_budget_s
    completed = 0
    while time.monotonic() < deadline:
        item = segments_queue.next_item(db, segments_constants.QUEUE_MAX_ATTEMPTS)
        if item is None:
            break
        item_id = item.id
        try:
            if item.activity_id is not None:
                match_activity(item.activity_id, db)
                finished = True
            else:
                finished = backfill_segment(item, deadline, db)
            if finished:
                segments_queue.remove_item(item_id, db)
                completed += 1
        except Exception as err:
            db.rollback()
            core_logger.print_to_log(
                f"Segment matching failed for queue item {item_id}: {type(err).__name__}",
                "error",
                exc=err,
            )
            segments_queue.record_failure(item_id, type(err).__name__, db)
    return completed


def process_segment_match_queue() -> None:
    """
    Scheduler entry point: drain the segment match queue.

    Args:
        None.

    Returns:
        None.
    """
    with _queue_lock() as acquired:
        if not acquired:
            return
        with core_database.SessionLocal() as db:
            try:
                _enqueue_outdated_segments(db)
                completed = drain_queue(db)
                if completed:
                    core_logger.print_to_log(f"Segment matching processed {completed} queue items")
            except Exception as err:
                db.rollback()
                core_logger.print_to_log(
                    f"Segment match queue processing failed: {type(err).__name__}",
                    "error",
                    exc=err,
                )
