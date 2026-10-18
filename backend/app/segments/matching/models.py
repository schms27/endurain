"""Durable work queue for segment matching."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SegmentMatchQueue(Base):
    """
    Pending segment matching work.

    Exactly one of ``activity_id`` (match one activity against all
    candidate segments) or ``segment_id`` (backfill one segment against
    all candidate activities) is set. Rows live in the database so work
    survives restarts and bulk imports.

    Attributes:
        id: Primary key.
        activity_id: Activity to match.
        segment_id: Segment to backfill.
        cursor: Last activity ID processed by a segment backfill.
        attempts: Number of failed processing attempts.
        last_error: Last error class name, for diagnostics.
        enqueued_at: When the item was queued.
    """

    __tablename__ = "segment_match_queue"
    __table_args__ = (
        CheckConstraint(
            "(activity_id IS NULL) <> (segment_id IS NULL)",
            name="ck_segment_match_queue_one_target",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Activity to match against candidate segments",
    )
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Segment to backfill against candidate activities",
    )
    cursor: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Last activity ID processed by a segment backfill",
    )
    attempts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of failed processing attempts",
    )
    last_error: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
        comment="Last processing error",
    )
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When the item was queued",
    )
