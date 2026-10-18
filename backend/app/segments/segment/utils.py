"""Build segment geometry from a slice of an activity's GPS stream."""

from dataclasses import dataclass

import numpy as np

import activities.activity.utils as activities_utils
import core.geo as core_geo
import segments.constants as segments_constants


class SegmentGeometryError(ValueError):
    """Raised when an activity slice cannot become a segment."""


@dataclass(frozen=True)
class SegmentGeometry:
    """
    Derived geometry and statistics of a new segment.

    Attributes:
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        distance: Length in metres (from the unsimplified points).
        elevation_gain: Elevation gain in metres.
        elevation_loss: Elevation loss in metres.
        average_grade: Average grade in percent.
        maximum_grade: Maximum grade over GRADE_WINDOW_M, in percent.
        bbox: Bounding box of the polyline.
    """

    geometry: list[list[float | None]]
    distance: float
    elevation_gain: int | None
    elevation_loss: int | None
    average_grade: float | None
    maximum_grade: float | None
    bbox: core_geo.BoundingBox

    @property
    def start(self) -> tuple[float, float]:
        """Start point as (lat, lon)."""
        return float(self.geometry[0][0]), float(self.geometry[0][1])  # type: ignore[arg-type]

    @property
    def end(self) -> tuple[float, float]:
        """End point as (lat, lon)."""
        return float(self.geometry[-1][0]), float(self.geometry[-1][1])  # type: ignore[arg-type]


def _maximum_grade(cumulative: np.ndarray, elevations: np.ndarray) -> float | None:
    """
    Steepest grade over windows of at least GRADE_WINDOW_M.

    Args:
        cumulative: Cumulative distance per point.
        elevations: Elevation per point (no missing values).

    Returns:
        Maximum grade in percent, or None if the slice is too short.
    """
    window = segments_constants.GRADE_WINDOW_M
    ends = np.searchsorted(cumulative, cumulative + window)
    valid = ends < cumulative.size
    if not valid.any():
        return None
    starts = np.flatnonzero(valid)
    ends = ends[valid]
    grades = (elevations[ends] - elevations[starts]) / (cumulative[ends] - cumulative[starts]) * 100
    return float(grades.max())


def build_segment_geometry(
    lat_lon_waypoints: list[dict],
    ele_waypoints: list[dict] | None,
    start_index: int,
    end_index: int,
    sport_group: segments_constants.SportGroup,
) -> SegmentGeometry:
    """
    Validate an activity slice and derive the segment geometry.

    Args:
        lat_lon_waypoints: The activity's map stream.
        ele_waypoints: The activity's elevation stream, if any.
        start_index: First stream index of the slice.
        end_index: Last stream index of the slice (inclusive).
        sport_group: Sport group of the source activity.

    Returns:
        The segment geometry.

    Raises:
        SegmentGeometryError: If the slice is out of range, too short,
            too long, or has a GPS gap.
    """
    if start_index < 0 or end_index >= len(lat_lon_waypoints) or end_index <= start_index:
        raise SegmentGeometryError("Slice is outside the activity's GPS stream")

    points = [
        waypoint
        for waypoint in lat_lon_waypoints[start_index : end_index + 1]
        if waypoint.get("lat") is not None and waypoint.get("lon") is not None
    ]
    if len(points) < segments_constants.MIN_SEGMENT_POINTS:
        raise SegmentGeometryError(f"A segment needs at least {segments_constants.MIN_SEGMENT_POINTS} GPS points")

    lats = np.asarray([float(point["lat"]) for point in points])
    lons = np.asarray([float(point["lon"]) for point in points])
    cumulative = core_geo.cumulative_distance_m(lats, lons)
    distance = float(cumulative[-1])

    minimum = segments_constants.MIN_SEGMENT_DISTANCE_M[sport_group]
    if distance < minimum:
        raise SegmentGeometryError(f"Segment is shorter than {minimum:.0f} m")
    if distance > segments_constants.MAX_SEGMENT_DISTANCE_M:
        raise SegmentGeometryError(f"Segment is longer than {segments_constants.MAX_SEGMENT_DISTANCE_M:.0f} m")
    if core_geo.max_step_m(cumulative) > segments_constants.MAX_GAP_M:
        raise SegmentGeometryError("Segment contains a GPS gap")

    elevation_by_time = {
        waypoint.get("time"): waypoint.get("ele")
        for waypoint in ele_waypoints or []
        if isinstance(waypoint, dict) and waypoint.get("ele") is not None
    }
    elevations: list[float | None] = []
    for point in points:
        elevation = elevation_by_time.get(point.get("time"))
        elevations.append(float(elevation) if elevation is not None else None)
    known = [value for value in elevations if value is not None]

    elevation_gain: int | None = None
    elevation_loss: int | None = None
    average_grade: float | None = None
    if len(known) >= 2:
        gain, loss = activities_utils.compute_elevation_gain_and_loss([{"ele": value} for value in known])
        elevation_gain, elevation_loss = round(gain), round(loss)
        average_grade = (known[-1] - known[0]) / distance * 100
    maximum_grade = (
        _maximum_grade(cumulative, np.asarray(elevations, dtype=np.float64)) if len(known) == len(points) else None
    )

    x, y = core_geo.to_local_xy(lats, lons, float(lats[0]), float(lons[0]))
    keep = core_geo.simplify_indices(x, y, segments_constants.SEGMENT_SIMPLIFY_TOLERANCE_M)
    geometry: list[list[float | None]] = [[float(lats[i]), float(lons[i]), elevations[i]] for i in keep.tolist()]

    bbox = core_geo.bounding_box(lats, lons)
    if bbox is None:  # pragma: no cover - guarded by MIN_SEGMENT_POINTS
        raise SegmentGeometryError("Segment has no GPS points")
    return SegmentGeometry(
        geometry=geometry,
        distance=distance,
        elevation_gain=elevation_gain,
        elevation_loss=elevation_loss,
        average_grade=average_grade,
        maximum_grade=maximum_grade,
        bbox=bbox,
    )
