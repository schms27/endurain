"""Segment match queue operations.

Kept free of activity and segment imports so the activity write path can
enqueue work without import cycles.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import segments.matching.models as matching_models


def enqueue_activity(activity_id: int, db: Session, *, commit: bool = True) -> None:
    """
    Queue an activity for matching against candidate segments.

    Does nothing if the activity is already queued.

    Args:
        activity_id: Activity to match.
        db: Database session.
        commit: Whether to commit the change.

    Returns:
        None.
    """
    pending = db.scalar(
        select(matching_models.SegmentMatchQueue.id).where(
            matching_models.SegmentMatchQueue.activity_id == activity_id,
        )
    )
    if pending is None:
        db.add(matching_models.SegmentMatchQueue(activity_id=activity_id, cursor=0, attempts=0))
    if commit:
        db.commit()


def enqueue_segment(segment_id: int, db: Session, *, commit: bool = True) -> None:
    """
    Queue a segment for a backfill against candidate activities.

    A segment already queued restarts from the beginning.

    Args:
        segment_id: Segment to backfill.
        db: Database session.
        commit: Whether to commit the change.

    Returns:
        None.
    """
    item = db.scalar(
        select(matching_models.SegmentMatchQueue).where(
            matching_models.SegmentMatchQueue.segment_id == segment_id,
        )
    )
    if item is None:
        db.add(matching_models.SegmentMatchQueue(segment_id=segment_id, cursor=0, attempts=0))
    else:
        item.cursor = 0
        item.attempts = 0
    if commit:
        db.commit()


def next_item(db: Session, max_attempts: int) -> matching_models.SegmentMatchQueue | None:
    """
    Return the oldest queue item that has attempts left.

    Args:
        db: Database session.
        max_attempts: Items with this many failed attempts are skipped.

    Returns:
        The queue item, or None when the queue is empty.
    """
    return db.scalar(
        select(matching_models.SegmentMatchQueue)
        .where(matching_models.SegmentMatchQueue.attempts < max_attempts)
        .order_by(matching_models.SegmentMatchQueue.id)
        .limit(1)
    )


def remove_item(item_id: int, db: Session) -> None:
    """
    Delete a finished queue item and commit.

    Args:
        item_id: Queue item ID.
        db: Database session.

    Returns:
        None.
    """
    db.execute(delete(matching_models.SegmentMatchQueue).where(matching_models.SegmentMatchQueue.id == item_id))
    db.commit()


def record_failure(item_id: int, error: str, db: Session) -> None:
    """
    Count a failed attempt on a queue item and commit.

    Args:
        item_id: Queue item ID.
        error: Short error description.
        db: Database session.

    Returns:
        None.
    """
    item = db.get(matching_models.SegmentMatchQueue, item_id)
    if item is None:
        return
    item.attempts += 1
    item.last_error = error[:250]
    db.commit()


def save_cursor(item_id: int, cursor: int, db: Session) -> None:
    """
    Persist backfill progress and commit.

    Args:
        item_id: Queue item ID.
        cursor: Last activity ID processed.
        db: Database session.

    Returns:
        None.
    """
    item = db.get(matching_models.SegmentMatchQueue, item_id)
    if item is None:
        return
    item.cursor = cursor
    db.commit()
