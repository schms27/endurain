"""Segment Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

import segments.constants as segments_constants

SegmentVisibility = Literal[0, 2]


class SegmentCreate(BaseModel):
    """
    Request to create a segment from a slice of one of your activities.

    Attributes:
        activity_id: Source activity ID (must be owned by the caller).
        start_index: First lat/lon stream index of the slice.
        end_index: Last lat/lon stream index of the slice (inclusive).
        name: Segment name.
        description: Optional description.
        visibility: 0 - public, 2 - private.
    """

    activity_id: StrictInt = Field(gt=0)
    start_index: StrictInt = Field(ge=0)
    end_index: StrictInt = Field(gt=0)
    name: str = Field(min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=2500)
    visibility: SegmentVisibility = 0

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_range(self) -> "SegmentCreate":
        """Ensure the slice is not empty or reversed."""
        if self.end_index <= self.start_index:
            raise ValueError("end_index must be greater than start_index")
        return self


class SegmentEdit(BaseModel):
    """
    Editable segment attributes. Geometry is immutable.

    Attributes:
        name: New name.
        description: New description (null clears it).
        visibility: New visibility.
    """

    name: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=2500)
    visibility: SegmentVisibility | None = None

    model_config = ConfigDict(extra="forbid")


class SegmentSummary(BaseModel):
    """
    Segment fields for lists (no geometry).

    Attributes:
        id: Segment ID.
        user_id: Creator user ID.
        name: Segment name.
        sport_group: Sport group.
        visibility: 0 - public, 2 - private.
        distance: Length in metres.
        elevation_gain: Elevation gain in metres.
        average_grade: Average grade in percent.
        start_lat: Start latitude.
        start_lon: Start longitude.
        city: City of the start point.
        town: Town of the start point.
        country: Country of the start point.
        is_archived: Whether the segment is archived.
        effort_count: Number of stored efforts.
        athlete_count: Number of distinct users with efforts.
        created_at: Creation timestamp.
    """

    id: StrictInt
    user_id: StrictInt | None
    name: str
    sport_group: segments_constants.SportGroup
    visibility: StrictInt
    distance: float
    elevation_gain: StrictInt | None
    average_grade: float | None
    start_lat: float
    start_lon: float
    city: str | None
    town: str | None
    country: str | None
    is_archived: bool
    effort_count: StrictInt
    athlete_count: StrictInt
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SegmentRead(SegmentSummary):
    """
    Full segment details.

    Attributes:
        description: Description.
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        elevation_loss: Elevation loss in metres.
        maximum_grade: Maximum grade over 100 m windows, in percent.
        end_lat: End latitude.
        end_lon: End longitude.
        source_activity_id: Activity the segment was cut from.
        updated_at: Last update timestamp.
    """

    description: str | None
    geometry: list[list[float | None]]
    elevation_loss: StrictInt | None
    maximum_grade: float | None
    end_lat: float
    end_lon: float
    source_activity_id: StrictInt | None
    updated_at: datetime
