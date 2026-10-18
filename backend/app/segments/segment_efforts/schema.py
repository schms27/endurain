"""Segment effort Pydantic schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, StrictInt, field_validator


class SegmentEffortRead(BaseModel):
    """
    A segment effort with its personal ranking.

    Attributes:
        id: Effort ID.
        segment_id: Segment ID.
        segment_name: Segment name.
        activity_id: Activity ID.
        user_id: Owner user ID.
        start_time: Start gate crossing time.
        elapsed_time: Elapsed seconds.
        distance: Distance on the segment in metres.
        start_index: Lat/lon stream start index.
        end_index: Lat/lon stream end index.
        average_hr: Average heart rate (bpm).
        max_hr: Maximum heart rate (bpm).
        average_power: Average power (W).
        normalized_power: Normalized power (W).
        average_cad: Average cadence.
        average_speed: Average speed (m/s).
        is_excluded: Hidden by the owner.
        current_rank: Rank among the owner's efforts on this segment
            (1 = PR); None for excluded efforts.
        historical_rank: Rank among the owner's efforts up to this
            effort's date (the achievement at the time); None for
            excluded efforts.
    """

    id: StrictInt
    segment_id: StrictInt
    segment_name: str | None = None
    activity_id: StrictInt
    user_id: StrictInt
    start_time: datetime
    elapsed_time: float
    distance: float
    start_index: StrictInt
    end_index: StrictInt
    average_hr: StrictInt | None
    max_hr: StrictInt | None
    average_power: StrictInt | None
    normalized_power: StrictInt | None
    average_cad: StrictInt | None
    average_speed: float | None
    is_excluded: bool
    current_rank: StrictInt | None = None
    historical_rank: StrictInt | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("elapsed_time", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> object:
        """Convert ORM ``Decimal`` values to ``float``."""
        if isinstance(value, Decimal):
            return float(value)
        return value


class SegmentEffortEdit(BaseModel):
    """
    Owner-editable effort attributes.

    Attributes:
        is_excluded: Hide (True) or restore (False) the effort.
    """

    is_excluded: bool

    model_config = ConfigDict(extra="forbid")
