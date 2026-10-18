"""Derive stored route geometry and statistics from raw points."""

import re
from dataclasses import dataclass

import numpy as np

import activities.activity.utils as activities_utils
import core.geo as core_geo
import routes.constants as routes_constants

RoutePoint = tuple[float, float, float | None]


class RouteGeometryError(ValueError):
    """Raised when points cannot form a route."""


@dataclass(frozen=True)
class RouteGeometry:
    """
    Stored geometry and statistics of a route.

    Attributes:
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        distance: Length in metres (from the unsimplified points).
        elevation_gain: Elevation gain in metres.
        elevation_loss: Elevation loss in metres.
        elevation_min: Lowest elevation in metres.
        elevation_max: Highest elevation in metres.
        is_loop: Whether start and end are close together.
        bbox: Bounding box.
    """

    geometry: list[list[float | None]]
    distance: float
    elevation_gain: int | None
    elevation_loss: int | None
    elevation_min: int | None
    elevation_max: int | None
    is_loop: bool
    bbox: core_geo.BoundingBox


def _simplify(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Simplify a polyline, coarsening until it fits the storage limit.

    Args:
        x: Eastings in metres.
        y: Northings in metres.

    Returns:
        Indices of the points to keep.
    """
    tolerance = routes_constants.SIMPLIFY_TOLERANCE_M
    keep = core_geo.simplify_indices(x, y, tolerance)
    while keep.size > routes_constants.MAX_STORED_POINTS:
        tolerance *= 2
        keep = core_geo.simplify_indices(x, y, tolerance)
    return keep


def build_route_geometry(points: list[RoutePoint]) -> RouteGeometry:
    """
    Compute stored geometry and statistics for a route.

    Consecutive duplicate points are dropped before simplification.

    Args:
        points: Ordered ``(lat, lon, ele)`` points.

    Returns:
        The route geometry.

    Raises:
        RouteGeometryError: With fewer than two distinct points.
    """
    deduplicated: list[RoutePoint] = []
    for point in points:
        if not deduplicated or point[:2] != deduplicated[-1][:2]:
            deduplicated.append(point)
    if len(deduplicated) < 2:
        raise RouteGeometryError("A route needs at least two distinct points")

    lats = np.asarray([point[0] for point in deduplicated])
    lons = np.asarray([point[1] for point in deduplicated])
    elevations = [point[2] for point in deduplicated]
    cumulative = core_geo.cumulative_distance_m(lats, lons)

    known = [value for value in elevations if value is not None]
    gain = loss = elevation_min = elevation_max = None
    if len(known) >= 2:
        gain_m, loss_m = activities_utils.compute_elevation_gain_and_loss([{"ele": value} for value in known])
        gain, loss = round(gain_m), round(loss_m)
        elevation_min, elevation_max = round(min(known)), round(max(known))

    x, y = core_geo.to_local_xy(lats, lons, float(lats[0]), float(lons[0]))
    keep = _simplify(x, y)
    geometry: list[list[float | None]] = [[float(lats[i]), float(lons[i]), elevations[i]] for i in keep.tolist()]

    loop_gap = float(core_geo.haversine_m(lats[0], lons[0], lats[-1], lons[-1]))
    bbox = core_geo.bounding_box(lats, lons)
    if bbox is None:  # pragma: no cover - guarded by the length check
        raise RouteGeometryError("A route needs at least two distinct points")
    return RouteGeometry(
        geometry=geometry,
        distance=float(cumulative[-1]),
        elevation_gain=gain,
        elevation_loss=loss,
        elevation_min=elevation_min,
        elevation_max=elevation_max,
        is_loop=loop_gap <= routes_constants.LOOP_THRESHOLD_M and float(cumulative[-1]) > 2 * loop_gap,
        bbox=bbox,
    )


def _interpolate(
    geometry: list[list[float | None]],
    cumulative: np.ndarray,
    distance: float,
) -> list[float | None]:
    """
    Point at a given distance along a polyline.

    Args:
        geometry: ``[[lat, lon, ele | None], ...]`` polyline.
        cumulative: Distance along the polyline at each vertex.
        distance: Distance of the wanted point, within the polyline.

    Returns:
        The interpolated ``[lat, lon, ele | None]`` point.
    """
    index = min(max(int(np.searchsorted(cumulative, distance)), 1), len(geometry) - 1)
    before, after = geometry[index - 1], geometry[index]
    span = float(cumulative[index] - cumulative[index - 1])
    fraction = (distance - float(cumulative[index - 1])) / span if span > 0 else 0.0
    lat = before[0] + (after[0] - before[0]) * fraction
    lon = before[1] + (after[1] - before[1]) * fraction
    if before[2] is not None and after[2] is not None:
        ele: float | None = before[2] + (after[2] - before[2]) * fraction
    else:
        ele = before[2] if fraction < 0.5 else after[2]
    return [lat, lon, ele]


def trim_endpoints(geometry: list[list[float | None]], meters: float) -> list[list[float | None]]:
    """
    Remove the first and last ``meters`` of a polyline.

    The cut points are interpolated so the trimmed line starts and ends
    exactly ``meters`` from the original ends.

    Args:
        geometry: ``[[lat, lon, ele | None], ...]`` polyline.
        meters: Length to remove at each end.

    Returns:
        The trimmed polyline; empty when the route is not longer than
        twice ``meters``.
    """
    if meters <= 0 or len(geometry) < 2:
        return [list(point) for point in geometry]
    cumulative = core_geo.cumulative_distance_m([point[0] for point in geometry], [point[1] for point in geometry])
    total = float(cumulative[-1])
    if total <= 2 * meters:
        return []
    start, end = meters, total - meters
    middle = [list(point) for point, at in zip(geometry, cumulative.tolist(), strict=True) if start < at < end]
    return [_interpolate(geometry, cumulative, start), *middle, _interpolate(geometry, cumulative, end)]


def near_any(lat: float, lon: float, points: list[tuple[float, float]], meters: float) -> bool:
    """
    Check whether a coordinate lies within ``meters`` of any of the points.

    Args:
        lat: Latitude.
        lon: Longitude.
        points: ``(lat, lon)`` points to test against.
        meters: Radius in metres.

    Returns:
        True if any point is within the radius.
    """
    return any(float(core_geo.haversine_m(lat, lon, p_lat, p_lon)) <= meters for p_lat, p_lon in points)


def default_route_name(filename: str | None) -> str:
    """
    Turn an uploaded file name into a readable route name.

    Args:
        filename: Original file name.

    Returns:
        The file stem with separators replaced, or "Route".
    """
    if not filename:
        return "Route"
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem[:250] or "Route"


def export_filename(name: str, extension: str) -> str:
    """
    Safe download file name for a route.

    Args:
        name: Route name.
        extension: File extension without the dot.

    Returns:
        An ASCII slug plus extension, e.g. ``castle-loop.gpx``.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()[:80]
    return f"{slug or 'route'}.{extension}"
