"""Planned route Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

import routes.constants as routes_constants


class RouteFromActivity(BaseModel):
    """
    Request to save (part of) an activity as a route.

    Attributes:
        name: Route name; defaults to the activity name.
        start_index: First lat/lon stream index to keep.
        end_index: Last lat/lon stream index to keep (inclusive).
    """

    name: str | None = Field(default=None, min_length=1, max_length=250)
    start_index: StrictInt | None = Field(default=None, ge=0)
    end_index: StrictInt | None = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_range(self) -> "RouteFromActivity":
        """Ensure an explicit slice is not empty or reversed."""
        if self.start_index is not None and self.end_index is not None and self.end_index <= self.start_index:
            raise ValueError("end_index must be greater than start_index")
        return self


class RouteEdit(BaseModel):
    """
    Editable route attributes.

    Attributes:
        name: New name.
        description: New description (null clears it).
        activity_type: New intended sport (null clears it).
    """

    name: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=2500)
    activity_type: StrictInt | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")


class RoutePoi(BaseModel):
    """
    A point of interest.

    Attributes:
        name: Display name.
        description: Optional description.
        kind: POI category.
        lat: Latitude.
        lon: Longitude.
        ele: Elevation in metres.
    """

    name: str
    description: str | None = None
    kind: routes_constants.PoiKind
    lat: float
    lon: float
    ele: float | None = None


class RouteSummary(BaseModel):
    """
    Route fields for lists (no geometry).

    Attributes:
        id: Route ID.
        user_id: Owner user ID.
        name: Route name.
        activity_type: Intended sport.
        source: How the route was created.
        distance: Length in metres.
        elevation_gain: Elevation gain in metres.
        elevation_loss: Elevation loss in metres.
        is_loop: Whether the route is a loop.
        city: City of the start point.
        country: Country of the start point.
        created_at: Creation timestamp.
    """

    id: StrictInt
    user_id: StrictInt
    name: str
    activity_type: StrictInt | None
    source: routes_constants.RouteSource
    distance: float
    elevation_gain: StrictInt | None
    elevation_loss: StrictInt | None
    is_loop: bool
    city: str | None
    country: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RouteRead(RouteSummary):
    """
    Full route details.

    Attributes:
        description: Description.
        source_activity_id: Activity the route was saved from.
        original_filename: Name of the imported file.
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        waypoints: Points of interest.
        elevation_min: Lowest elevation in metres.
        elevation_max: Highest elevation in metres.
        updated_at: Last update timestamp.
    """

    description: str | None
    source_activity_id: StrictInt | None
    original_filename: str | None
    geometry: list[list[float | None]]
    waypoints: list[RoutePoi]
    elevation_min: StrictInt | None
    elevation_max: StrictInt | None
    updated_at: datetime


class RoutesPage(BaseModel):
    """
    One page of routes.

    Attributes:
        records: Routes on this page.
        total: Total routes matching the filters.
    """

    records: list[RouteSummary]
    total: StrictInt
