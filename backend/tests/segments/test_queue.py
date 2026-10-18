"""Tests for the segment match queue on SQLite."""

from sqlalchemy import select

import segments.matching.models as matching_models
import segments.matching.queue as segments_queue
from tests.segments.conftest import add_activity, add_segment


def _items(db):
    return list(db.scalars(select(matching_models.SegmentMatchQueue).order_by(matching_models.SegmentMatchQueue.id)))


def test_enqueue_activity_is_idempotent(sqlite_db):
    """Queuing the same activity twice keeps one item."""
    activity = add_activity(sqlite_db)
    segments_queue.enqueue_activity(activity.id, sqlite_db)
    segments_queue.enqueue_activity(activity.id, sqlite_db)
    assert [item.activity_id for item in _items(sqlite_db)] == [activity.id]


def test_enqueue_segment_restarts_backfill(sqlite_db):
    """Requeuing a segment resets its cursor and attempts."""
    segment = add_segment(sqlite_db)
    segments_queue.enqueue_segment(segment.id, sqlite_db)
    item = _items(sqlite_db)[0]
    segments_queue.save_cursor(item.id, 42, sqlite_db)
    segments_queue.record_failure(item.id, "Boom" * 100, sqlite_db)

    segments_queue.enqueue_segment(segment.id, sqlite_db)

    [item] = _items(sqlite_db)
    assert (item.cursor, item.attempts) == (0, 0)


def test_next_item_skips_exhausted_items(sqlite_db):
    """Items out of attempts are not returned."""
    first = add_activity(sqlite_db)
    second = add_activity(sqlite_db)
    segments_queue.enqueue_activity(first.id, sqlite_db)
    segments_queue.enqueue_activity(second.id, sqlite_db)
    exhausted = _items(sqlite_db)[0]
    for _ in range(3):
        segments_queue.record_failure(exhausted.id, "Boom", sqlite_db)

    assert segments_queue.next_item(sqlite_db, max_attempts=3).activity_id == second.id
    assert len(exhausted.last_error) <= 250


def test_remove_item_and_missing_items(sqlite_db):
    """Removing finishes an item; updating a missing item is a no-op."""
    activity = add_activity(sqlite_db)
    segments_queue.enqueue_activity(activity.id, sqlite_db)
    item = _items(sqlite_db)[0]

    segments_queue.remove_item(item.id, sqlite_db)

    assert segments_queue.next_item(sqlite_db, max_attempts=3) is None
    segments_queue.record_failure(item.id, "Boom", sqlite_db)
    segments_queue.save_cursor(item.id, 1, sqlite_db)
