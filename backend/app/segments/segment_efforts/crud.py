"""CRUD operations for segment efforts."""

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity.schema as activity_schema
import core.decorators as core_decorators
import segments.constants as segments_constants
import segments.segment.crud as segment_crud
import segments.segment.models as segment_models
import segments.segment_efforts.models as segment_efforts_models
import segments.segment_efforts.schema as segment_efforts_schema

_Effort = segment_efforts_models.SegmentEffort


def replace_efforts(
    activity_id: int,
    efforts: list[segment_efforts_models.SegmentEffort],
    db: Session,
    *,
    segment_id: int | None = None,
) -> set[int]:
    """
    Replace an activity's efforts (all, or for one segment); caller commits.

    Efforts the owner excluded stay excluded when the same pass is
    matched again.

    Args:
        activity_id: Activity whose efforts are replaced.
        efforts: New effort ORM instances.
        db: Database session.
        segment_id: Restrict the replacement to this segment.

    Returns:
        IDs of segments whose efforts changed.
    """
    scope = [_Effort.activity_id == activity_id]
    if segment_id is not None:
        scope.append(_Effort.segment_id == segment_id)
    existing = db.execute(select(_Effort.segment_id, _Effort.start_index, _Effort.is_excluded).where(*scope)).all()
    excluded = {(row.segment_id, row.start_index) for row in existing if row.is_excluded}
    touched = {row.segment_id for row in existing}

    db.execute(delete(_Effort).where(*scope).execution_options(synchronize_session="fetch"))
    for effort in efforts:
        effort.is_excluded = (effort.segment_id, effort.start_index) in excluded
        touched.add(effort.segment_id)
        db.add(effort)
    db.flush()
    return touched


def delete_segment_efforts(segment_id: int, db: Session) -> None:
    """
    Delete every effort of a segment; caller commits.

    Args:
        segment_id: Segment ID.
        db: Database session.

    Returns:
        None.
    """
    db.execute(delete(_Effort).where(_Effort.segment_id == segment_id).execution_options(synchronize_session="fetch"))


def _ranks(efforts: list[segment_efforts_models.SegmentEffort], db: Session) -> dict[int, tuple[int, int]]:
    """
    Personal ranks for efforts, computed against each owner's efforts.

    Args:
        efforts: Efforts to rank (not excluded).
        db: Database session.

    Returns:
        Map of effort ID to (current rank, historical rank).
    """
    groups = {(effort.segment_id, effort.user_id) for effort in efforts}
    ranks: dict[int, tuple[int, int]] = {}
    for segment_id, user_id in groups:
        history = db.execute(
            select(_Effort.elapsed_time, _Effort.start_time).where(
                _Effort.segment_id == segment_id,
                _Effort.user_id == user_id,
                _Effort.is_excluded.is_(False),
            )
        ).all()
        for effort in efforts:
            if effort.segment_id != segment_id or effort.user_id != user_id:
                continue
            faster = [row for row in history if row.elapsed_time < effort.elapsed_time]
            earlier_faster = [row for row in faster if row.start_time < effort.start_time]
            ranks[effort.id] = (1 + len(faster), 1 + len(earlier_faster))
    return ranks


def _to_read(
    effort: segment_efforts_models.SegmentEffort,
    segment_name: str | None,
    ranks: dict[int, tuple[int, int]],
) -> segment_efforts_schema.SegmentEffortRead:
    read = segment_efforts_schema.SegmentEffortRead.model_validate(effort)
    read.segment_name = segment_name
    if effort.id in ranks:
        read.current_rank, read.historical_rank = ranks[effort.id]
    return read


def _mask_for_viewer(
    read: segment_efforts_schema.SegmentEffortRead,
    activity: activity_schema.Activity,
) -> segment_efforts_schema.SegmentEffortRead:
    """
    Hide metrics the activity owner keeps private.

    Args:
        read: Effort schema (mutated).
        activity: The effort's activity.

    Returns:
        The masked effort.
    """
    if activity.hide_hr:
        read.average_hr = read.max_hr = None
    if activity.hide_power:
        read.average_power = read.normalized_power = None
    if activity.hide_cadence:
        read.average_cad = None
    if activity.hide_speed or activity.hide_pace:
        read.average_speed = None
    return read


@core_decorators.handle_db_errors
def get_activity_efforts(
    activity_id: int,
    viewer_id: int,
    db: Session,
) -> list[segment_efforts_schema.SegmentEffortRead]:
    """
    Efforts of an activity, as the viewer may see them.

    The owner sees every effort, with personal ranks. Other users only
    see efforts of activities visible to them, never when the map is
    hidden, only on public segments (or segments they own), without
    excluded efforts, ranks, or metrics the owner hides.

    Args:
        activity_id: Activity ID.
        viewer_id: Requesting user ID.
        db: Database session.

    Returns:
        Efforts ordered by start time.
    """
    activity = activity_crud.get_activity_by_id_from_user_id_or_has_visibility(activity_id, viewer_id, db)
    if activity is None:
        return []
    is_owner = activity.user_id == viewer_id
    if not is_owner and activity.hide_map:
        return []

    stmt = (
        select(_Effort, segment_models.Segment.name)
        .join(segment_models.Segment, segment_models.Segment.id == _Effort.segment_id)
        .where(_Effort.activity_id == activity_id)
        .order_by(_Effort.start_time, _Effort.id)
    )
    if not is_owner:
        stmt = stmt.where(
            _Effort.is_excluded.is_(False),
            or_(
                segment_models.Segment.visibility == segments_constants.SEGMENT_VISIBILITY_PUBLIC,
                segment_models.Segment.user_id == viewer_id,
            ),
        )
    rows = db.execute(stmt).all()

    ranks: dict[int, tuple[int, int]] = {}
    if is_owner:
        ranks = _ranks([effort for effort, _ in rows if not effort.is_excluded], db)
    results = [_to_read(effort, name, ranks) for effort, name in rows]
    if not is_owner:
        results = [_mask_for_viewer(read, activity) for read in results]
    return results


@core_decorators.handle_db_errors
def get_user_segment_efforts(
    segment_id: int,
    user_id: int,
    db: Session,
) -> list[segment_efforts_schema.SegmentEffortRead]:
    """
    A user's own efforts on a segment, fastest first, with ranks.

    Args:
        segment_id: Segment ID.
        user_id: Requesting user ID.
        db: Database session.

    Returns:
        The user's efforts.
    """
    efforts = list(
        db.scalars(
            select(_Effort)
            .where(_Effort.segment_id == segment_id, _Effort.user_id == user_id)
            .order_by(_Effort.is_excluded, _Effort.elapsed_time, _Effort.start_time)
        ).all()
    )
    ranks = _ranks([effort for effort in efforts if not effort.is_excluded], db)
    return [_to_read(effort, None, ranks) for effort in efforts]


def set_effort_excluded(
    effort_id: int,
    user_id: int,
    is_excluded: bool,
    db: Session,
) -> segment_efforts_schema.SegmentEffortRead:
    """
    Exclude or restore one of the user's efforts.

    Args:
        effort_id: Effort ID.
        user_id: Requesting user ID (must own the effort).
        is_excluded: New exclusion state.
        db: Database session.

    Returns:
        The updated effort.

    Raises:
        HTTPException: 404 if missing or not owned.
    """
    effort = db.scalar(select(_Effort).where(_Effort.id == effort_id, _Effort.user_id == user_id))
    if effort is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment effort not found")
    effort.is_excluded = is_excluded
    try:
        segment_crud.refresh_counts({effort.segment_id}, db)
        db.commit()
        db.refresh(effort)
    except Exception:
        db.rollback()
        raise
    return _to_read(effort, None, {})
