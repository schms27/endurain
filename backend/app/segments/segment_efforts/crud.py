"""CRUD operations for segment efforts."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy import Row, delete, false, func, or_, select
from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity.models as activity_models
import activities.activity.schema as activity_schema
import core.decorators as core_decorators
import followers.models as followers_models
import segments.constants as segments_constants
import segments.segment.crud as segment_crud
import segments.segment.models as segment_models
import segments.segment_efforts.models as segment_efforts_models
import segments.segment_efforts.schema as segment_efforts_schema
import users.users.models as users_models
import users.users_privacy_settings.models as users_privacy_settings_models

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


_Ranks = dict[int, tuple[int, int, float]]


def _ranks(efforts: list[segment_efforts_models.SegmentEffort], db: Session) -> _Ranks:
    """
    Personal ranks for efforts, computed against each owner's efforts.

    Args:
        efforts: Efforts to rank (not excluded).
        db: Database session.

    Returns:
        Map of effort ID to (current rank, historical rank, PR elapsed
        seconds).
    """
    groups = {(effort.segment_id, effort.user_id) for effort in efforts}
    ranks: _Ranks = {}
    for segment_id, user_id in groups:
        history = db.execute(
            select(_Effort.elapsed_time, _Effort.start_time).where(
                _Effort.segment_id == segment_id,
                _Effort.user_id == user_id,
                _Effort.is_excluded.is_(False),
            )
        ).all()
        personal_record = float(min(row.elapsed_time for row in history))
        for effort in efforts:
            if effort.segment_id != segment_id or effort.user_id != user_id:
                continue
            faster = [row for row in history if row.elapsed_time < effort.elapsed_time]
            earlier_faster = [row for row in faster if row.start_time < effort.start_time]
            ranks[effort.id] = (1 + len(faster), 1 + len(earlier_faster), personal_record)
    return ranks


def _to_read(
    effort: segment_efforts_models.SegmentEffort,
    segment_name: str | None,
    ranks: _Ranks,
) -> segment_efforts_schema.SegmentEffortRead:
    read = segment_efforts_schema.SegmentEffortRead.model_validate(effort)
    read.segment_name = segment_name
    if effort.id in ranks:
        read.current_rank, read.historical_rank, read.pr_elapsed_time = ranks[effort.id]
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

    ranks: _Ranks = {}
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


class LeaderboardScope(StrEnum):
    """
    Whose efforts a leaderboard ranks.

    Members:
        EVERYONE: Every athlete visible to the viewer.
        FOLLOWING: The viewer and the athletes they follow.
        ME: Only the viewer.
    """

    EVERYONE = "everyone"
    FOLLOWING = "following"
    ME = "me"


class LeaderboardPeriod(StrEnum):
    """
    Time window of a leaderboard.

    Members:
        ALL: All time.
        THIS_YEAR: Since 1 January of the current year (UTC).
        LAST_90_DAYS: The last 90 days.
    """

    ALL = "all"
    THIS_YEAR = "this_year"
    LAST_90_DAYS = "last_90_days"


def _period_start(period: LeaderboardPeriod, now: datetime) -> datetime | None:
    """
    First moment included in a leaderboard period.

    Args:
        period: Leaderboard period.
        now: Current time (timezone-aware).

    Returns:
        The period start, or None for all time.
    """
    if period == LeaderboardPeriod.THIS_YEAR:
        return datetime(now.year, 1, 1, tzinfo=UTC)
    if period == LeaderboardPeriod.LAST_90_DAYS:
        return now - timedelta(days=segments_constants.LEADERBOARD_RECENT_DAYS)
    return None


def _leaderboard_entry(row: Row, viewer_id: int) -> segment_efforts_schema.SegmentLeaderboardEntry:
    """
    Build a leaderboard entry, masking what the athlete keeps private.

    Args:
        row: Ranked leaderboard row.
        viewer_id: Requesting user ID.

    Returns:
        The entry; the viewer's own entry is never masked.
    """
    is_viewer = row.user_id == viewer_id
    return segment_efforts_schema.SegmentLeaderboardEntry(
        rank=int(row.rank),
        user_id=row.user_id,
        user_name=row.user_name,
        username=row.username,
        user_photo_path=row.user_photo_path,
        effort_id=row.effort_id,
        activity_id=row.activity_id,
        start_time=row.start_time if is_viewer or not row.hide_start_time else None,
        elapsed_time=row.elapsed_time,
        average_hr=row.average_hr if is_viewer or not row.hide_hr else None,
        average_power=row.average_power if is_viewer or not row.hide_power else None,
        average_speed=(row.average_speed if is_viewer or not (row.hide_speed or row.hide_pace) else None),
    )


@core_decorators.handle_db_errors
def get_segment_leaderboard(
    segment_id: int,
    viewer_id: int,
    db: Session,
    *,
    scope: LeaderboardScope = LeaderboardScope.EVERYONE,
    period: LeaderboardPeriod = LeaderboardPeriod.ALL,
    page_number: int = 1,
    num_records: int = 25,
    now: datetime | None = None,
) -> segment_efforts_schema.SegmentLeaderboard:
    """
    Rank athletes by their best effort on a segment.

    The viewer always sees their own efforts. Other athletes' efforts
    count only when the viewer may see the activity, its map is not
    hidden, the effort is not excluded, and the athlete has not opted
    out of segment leaderboards. The caller checks segment visibility.

    Args:
        segment_id: Segment ID.
        viewer_id: Requesting user ID.
        db: Database session.
        scope: Whose efforts to rank.
        period: Time window.
        page_number: 1-based page number.
        num_records: Page size.
        now: Current time, for tests.

    Returns:
        The requested page, the athlete count and the viewer's entry.
    """
    activity = activity_models.Activity
    privacy = users_privacy_settings_models.UsersPrivacySettings
    others_visible = (
        activity.hide_map.is_(False)
        & func.coalesce(privacy.hide_from_segment_leaderboards, false()).is_(False)
        & activity_crud.visible_to_requester_condition(viewer_id)
    )
    visible = (
        select(
            _Effort.id.label("effort_id"),
            _Effort.user_id,
            _Effort.activity_id,
            _Effort.start_time,
            _Effort.elapsed_time,
            _Effort.average_hr,
            _Effort.average_power,
            _Effort.average_speed,
            activity.hide_start_time,
            activity.hide_hr,
            activity.hide_power,
            activity.hide_speed,
            activity.hide_pace,
            users_models.Users.name.label("user_name"),
            users_models.Users.username,
            users_models.Users.photo_path.label("user_photo_path"),
            func.row_number()
            .over(
                partition_by=_Effort.user_id,
                order_by=(_Effort.elapsed_time, _Effort.start_time, _Effort.id),
            )
            .label("personal_rank"),
        )
        .join(activity, activity.id == _Effort.activity_id)
        .join(users_models.Users, users_models.Users.id == _Effort.user_id)
        .outerjoin(privacy, privacy.user_id == _Effort.user_id)
        .where(
            _Effort.segment_id == segment_id,
            _Effort.is_excluded.is_(False),
            or_(_Effort.user_id == viewer_id, others_visible),
        )
    )
    if scope == LeaderboardScope.ME:
        visible = visible.where(_Effort.user_id == viewer_id)
    elif scope == LeaderboardScope.FOLLOWING:
        following = select(followers_models.Follower.following_id).where(
            followers_models.Follower.follower_id == viewer_id,
            followers_models.Follower.is_accepted.is_(True),
        )
        visible = visible.where(or_(_Effort.user_id == viewer_id, _Effort.user_id.in_(following)))
    period_start = _period_start(period, now or datetime.now(UTC))
    if period_start is not None:
        visible = visible.where(_Effort.start_time >= period_start)

    personal = visible.subquery("personal")
    best = (
        select(
            *[column for column in personal.c if column.name != "personal_rank"],
            func.rank().over(order_by=personal.c.elapsed_time).label("rank"),
        )
        .where(personal.c.personal_rank == 1)
        .subquery("best")
    )

    rows = db.execute(
        select(best)
        .order_by(best.c.rank, best.c.start_time, best.c.effort_id)
        .offset((page_number - 1) * num_records)
        .limit(num_records)
    ).all()
    total = db.scalar(select(func.count()).select_from(best)) or 0
    viewer_row = db.execute(select(best).where(best.c.user_id == viewer_id)).first()

    return segment_efforts_schema.SegmentLeaderboard(
        entries=[_leaderboard_entry(row, viewer_id) for row in rows],
        total=int(total),
        viewer_entry=_leaderboard_entry(viewer_row, viewer_id) if viewer_row else None,
    )
