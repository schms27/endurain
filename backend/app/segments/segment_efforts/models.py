"""Segment effort database models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    DateTime,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SegmentEffort(Base):
    """
    One pass of an activity over a segment, from start gate to end gate.

    Attributes:
        id: Primary key.
        segment_id: Segment the effort belongs to.
        activity_id: Activity that produced the effort.
        user_id: Owner of the activity (denormalised for rankings).
        start_time: Interpolated start-gate crossing time.
        elapsed_time: Elapsed seconds from start gate to end gate.
        distance: Length of the activity sub-track in metres.
        start_index: Lat/lon stream index where the effort starts.
        end_index: Lat/lon stream index where the effort ends.
        average_hr: Average heart rate (bpm).
        max_hr: Maximum heart rate (bpm).
        average_power: Average power (W).
        normalized_power: Normalized power (W).
        average_cad: Average cadence.
        average_speed: Average speed (m/s).
        is_excluded: Hidden by the owner (e.g. a GPS glitch).
        created_at: Creation timestamp.
    """

    __tablename__ = "segment_efforts"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "segment_id",
            "start_index",
            name="uq_segment_efforts_activity_segment_start",
        ),
        Index(
            "ix_segment_efforts_segment_elapsed",
            "segment_id",
            "elapsed_time",
        ),
        Index(
            "ix_segment_efforts_segment_user_elapsed",
            "segment_id",
            "user_id",
            "elapsed_time",
        ),
        Index(
            "ix_segment_efforts_segment_start_time",
            "segment_id",
            "start_time",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"),
        nullable=False,
        comment="Segment ID that the effort belongs to",
    )
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Activity ID that produced the effort",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID that owns the activity",
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Start gate crossing time",
    )
    elapsed_time: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=10),
        nullable=False,
        comment="Elapsed time from start to end gate (s)",
    )
    distance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Distance travelled on the segment (m)",
    )
    start_index: Mapped[int] = mapped_column(
        nullable=False,
        comment="Lat/lon stream index where the effort starts",
    )
    end_index: Mapped[int] = mapped_column(
        nullable=False,
        comment="Lat/lon stream index where the effort ends",
    )
    average_hr: Mapped[int | None] = mapped_column(nullable=True, comment="Average heart rate (bpm)")
    max_hr: Mapped[int | None] = mapped_column(nullable=True, comment="Max heart rate (bpm)")
    average_power: Mapped[int | None] = mapped_column(nullable=True, comment="Average power (watts)")
    normalized_power: Mapped[int | None] = mapped_column(nullable=True, comment="Normalized power (watts)")
    average_cad: Mapped[int | None] = mapped_column(nullable=True, comment="Average cadence (rpm)")
    average_speed: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average speed (m/s)",
    )
    is_excluded: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Effort hidden by its owner",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Effort creation date",
    )
