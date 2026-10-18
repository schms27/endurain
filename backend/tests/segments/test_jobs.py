"""End-to-end tests for segment matching jobs on SQLite."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

import segments.constants as segments_constants
import segments.matching.jobs as jobs
import segments.matching.models as matching_models
import segments.matching.queue as segments_queue
import segments.segment.crud as segment_crud
import segments.segment.schema as segment_schema
import segments.segment_efforts.models as segment_efforts_models
from tests.segments.conftest import SLICE, add_activity, add_segment


def _efforts(db):
    return list(
        db.scalars(select(segment_efforts_models.SegmentEffort).order_by(segment_efforts_models.SegmentEffort.id))
    )


def _queue(db):
    return list(db.scalars(select(matching_models.SegmentMatchQueue)))


def _create_from(db, activity, **overrides):
    request = segment_schema.SegmentCreate(
        activity_id=activity.id,
        start_index=SLICE[0],
        end_index=SLICE[1],
        name="River path",
        **overrides,
    )
    return segment_crud.create_segment(activity.user_id, request, db)


def test_new_segment_backfills_matching_activities(sqlite_db):
    """Creating a segment matches the source and other eligible activities."""
    source = add_activity(sqlite_db, user_id=1)
    other_user = add_activity(sqlite_db, user_id=2, start_time=1_704_200_000.0)
    add_activity(sqlite_db, user_id=3, activity_type=4)  # cycling: other sport group
    add_activity(sqlite_db, user_id=4, is_hidden=True)  # duplicate pending review
    add_activity(sqlite_db, user_id=5, path=[(1200.0, 0.0), (-200.0, 0.0)])  # wrong direction

    segment = _create_from(sqlite_db, source)
    assert [item.segment_id for item in _queue(sqlite_db)] == [segment.id]

    assert jobs.drain_queue(sqlite_db) == 1
    efforts = _efforts(sqlite_db)
    assert sorted(effort.activity_id for effort in efforts) == [source.id, other_user.id]
    assert all(float(effort.elapsed_time) == pytest.approx(200.0, abs=1.0) for effort in efforts)
    assert all(effort.average_hr == 150 for effort in efforts)
    assert all(effort.average_speed == pytest.approx(5.0, rel=0.02) for effort in efforts)
    assert _queue(sqlite_db) == []

    stored = segment_crud.get_segment_model(segment.id, sqlite_db)
    assert (stored.effort_count, stored.athlete_count) == (2, 2)


def test_new_activity_is_matched_against_existing_segment(sqlite_db):
    """An activity queued after creation is matched on the next drain."""
    segment = add_segment(sqlite_db)
    activity = add_activity(sqlite_db, user_id=7)
    segments_queue.enqueue_activity(activity.id, sqlite_db)

    jobs.drain_queue(sqlite_db)

    efforts = _efforts(sqlite_db)
    assert [(effort.segment_id, effort.user_id) for effort in efforts] == [(segment.id, 7)]
    assert efforts[0].start_index < efforts[0].end_index


def test_private_segment_only_matches_owner(sqlite_db):
    """Private segments ignore other users' activities."""
    source = add_activity(sqlite_db, user_id=1)
    add_activity(sqlite_db, user_id=2)
    _create_from(sqlite_db, source, visibility=segments_constants.SEGMENT_VISIBILITY_PRIVATE)

    jobs.drain_queue(sqlite_db)

    assert [effort.user_id for effort in _efforts(sqlite_db)] == [1]


def test_rematch_keeps_owner_exclusions(sqlite_db):
    """An excluded effort stays excluded when the activity is rematched."""
    segment = add_segment(sqlite_db)
    activity = add_activity(sqlite_db)
    jobs.match_activity(activity.id, sqlite_db)
    effort = _efforts(sqlite_db)[0]
    effort.is_excluded = True
    sqlite_db.commit()

    jobs.match_activity(activity.id, sqlite_db)

    rematched = _efforts(sqlite_db)
    assert len(rematched) == 1 and rematched[0].is_excluded
    assert segment_crud.get_segment_model(segment.id, sqlite_db).effort_count == 0


def test_hidden_or_retyped_activity_loses_efforts(sqlite_db):
    """Rematching a now-hidden activity removes its efforts."""
    add_segment(sqlite_db)
    activity = add_activity(sqlite_db)
    jobs.match_activity(activity.id, sqlite_db)
    assert len(_efforts(sqlite_db)) == 1

    activity.is_hidden = True
    sqlite_db.commit()
    jobs.match_activity(activity.id, sqlite_db)
    assert _efforts(sqlite_db) == []


def test_match_missing_activity_is_a_no_op(sqlite_db):
    """Deleted activities are skipped."""
    jobs.match_activity(999, sqlite_db)
    assert _efforts(sqlite_db) == []


def test_backfill_resumes_from_cursor(sqlite_db, monkeypatch):
    """A backfill that runs out of time keeps its cursor and finishes later."""
    monkeypatch.setattr(segments_constants, "BACKFILL_BATCH_SIZE", 1)
    first = add_activity(sqlite_db, user_id=1)
    second = add_activity(sqlite_db, user_id=2)
    segment = add_segment(sqlite_db, matcher_version=0)
    segments_queue.enqueue_segment(segment.id, sqlite_db)
    item = _queue(sqlite_db)[0]

    assert jobs.backfill_segment(item, deadline=0.0, db=sqlite_db) is False
    assert item.cursor == first.id
    assert [effort.activity_id for effort in _efforts(sqlite_db)] == [first.id]

    assert jobs.backfill_segment(item, deadline=float("inf"), db=sqlite_db) is True
    assert sorted(effort.activity_id for effort in _efforts(sqlite_db)) == [first.id, second.id]
    assert segment_crud.get_segment_model(segment.id, sqlite_db).matcher_version == (segments_constants.MATCHER_VERSION)


def test_backfill_of_archived_segment_clears_efforts(sqlite_db):
    """Archiving and backfilling drops all efforts."""
    segment = add_segment(sqlite_db)
    activity = add_activity(sqlite_db)
    jobs.match_activity(activity.id, sqlite_db)
    segment.is_archived = True
    sqlite_db.commit()
    segments_queue.enqueue_segment(segment.id, sqlite_db)

    jobs.drain_queue(sqlite_db)

    assert _efforts(sqlite_db) == []
    assert segment_crud.get_segment_model(segment.id, sqlite_db).effort_count == 0


def test_backfill_of_deleted_segment_finishes(sqlite_db):
    """A queue item whose segment is gone is simply completed."""
    item = MagicMock(segment_id=12345, cursor=0)
    assert jobs.backfill_segment(item, deadline=float("inf"), db=sqlite_db) is True


def test_failures_are_counted_and_retried_up_to_the_limit(sqlite_db):
    """A failing item is retried until it runs out of attempts."""
    activity = add_activity(sqlite_db)
    segments_queue.enqueue_activity(activity.id, sqlite_db)

    with patch("segments.matching.jobs.match_activity", side_effect=RuntimeError("boom")):
        assert jobs.drain_queue(sqlite_db) == 0

    item = _queue(sqlite_db)[0]
    assert item.attempts == segments_constants.QUEUE_MAX_ATTEMPTS
    assert item.last_error == "RuntimeError"


def test_outdated_segments_are_requeued_once(sqlite_db, monkeypatch):
    """Segments from an older matcher are queued once per process."""
    monkeypatch.setattr(jobs, "_outdated_segments_checked", False)
    segment = add_segment(sqlite_db, matcher_version=0)

    jobs._enqueue_outdated_segments(sqlite_db)
    assert [item.segment_id for item in _queue(sqlite_db)] == [segment.id]

    segments_queue.remove_item(_queue(sqlite_db)[0].id, sqlite_db)
    jobs._enqueue_outdated_segments(sqlite_db)
    assert _queue(sqlite_db) == []


def test_process_queue_uses_its_own_session(sqlite_db, monkeypatch):
    """The scheduler entry point drains the queue with a fresh session."""
    monkeypatch.setattr(jobs, "_outdated_segments_checked", True)
    add_segment(sqlite_db)
    activity = add_activity(sqlite_db)
    segments_queue.enqueue_activity(activity.id, sqlite_db)

    @contextmanager
    def _session():
        yield sqlite_db

    with (
        patch("segments.matching.jobs.core_database.SessionLocal", _session),
        patch("segments.matching.jobs.core_database.engine", MagicMock(dialect=MagicMock())) as engine,
    ):
        engine.dialect.name = "sqlite"
        jobs.process_segment_match_queue()

    assert len(_efforts(sqlite_db)) == 1


def test_process_queue_skips_when_lock_is_held():
    """Another worker holding the lock means nothing runs."""

    @contextmanager
    def _not_acquired():
        yield False

    with (
        patch("segments.matching.jobs._queue_lock", _not_acquired),
        patch("segments.matching.jobs.core_database.SessionLocal") as session_local,
    ):
        jobs.process_segment_match_queue()
    session_local.assert_not_called()


def test_process_queue_logs_unexpected_errors():
    """Errors outside a queue item are logged, not raised."""
    session = MagicMock()

    @contextmanager
    def _session():
        yield session

    @contextmanager
    def _acquired():
        yield True

    with (
        patch("segments.matching.jobs._queue_lock", _acquired),
        patch("segments.matching.jobs.core_database.SessionLocal", _session),
        patch("segments.matching.jobs.server_settings_crud.get_server_settings", return_value=None),
        patch("segments.matching.jobs._enqueue_outdated_segments", side_effect=RuntimeError("db down")),
        patch("segments.matching.jobs.core_logger.print_to_log") as log,
    ):
        jobs.process_segment_match_queue()
    session.rollback.assert_called_once()
    assert "RuntimeError" in log.call_args.args[0]


@pytest.mark.parametrize("acquired", [True, False])
def test_queue_lock_on_postgresql(acquired):
    """The advisory lock is taken and released on a dedicated connection."""
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = acquired
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.connect.return_value.__enter__.return_value = connection

    with patch("segments.matching.jobs.core_database.engine", engine), jobs._queue_lock() as got:
        assert got is acquired

    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert "pg_try_advisory_lock" in statements[0]
    assert any("pg_advisory_unlock" in statement for statement in statements) is acquired
