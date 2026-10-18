"""Geometry helpers for GPS tracks.

Pure numpy functions with no database access, shared by segment
matching and anything else that needs to reason about tracks.

Distances between points use either the haversine formula
(:func:`haversine_m`, :func:`cumulative_distance_m`) or a local
equirectangular projection to metres around a reference point
(:func:`to_local_xy`). The projection is accurate to well under 1 %
for extents of a few tens of kilometres and is far cheaper than
per-point geodesic calls, which makes it the right tool for the
point-to-polyline work in segment matching.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

EARTH_RADIUS_M: float = 6_371_008.8

# Upper bound on the number of point/edge pairs evaluated at once by
# distances_to_polyline, to keep memory flat on long tracks.
_MAX_PAIRS_PER_CHUNK: int = 2_000_000

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class BoundingBox:
    """
    Latitude/longitude bounding box in decimal degrees.

    Attributes:
        min_lat: Southern edge.
        min_lon: Western edge.
        max_lat: Northern edge.
        max_lon: Eastern edge.
    """

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def padded(self, meters: float) -> "BoundingBox":
        """
        Return a copy grown by ``meters`` on every side.

        Args:
            meters: Padding distance in metres.

        Returns:
            The padded bounding box, clamped to valid coordinates.
        """
        delta_lat = math.degrees(meters / EARTH_RADIUS_M)
        mid_lat = math.radians((self.min_lat + self.max_lat) / 2)
        cos_lat = max(math.cos(mid_lat), 1e-6)
        delta_lon = math.degrees(meters / (EARTH_RADIUS_M * cos_lat))
        return BoundingBox(
            min_lat=max(self.min_lat - delta_lat, -90.0),
            min_lon=max(self.min_lon - delta_lon, -180.0),
            max_lat=min(self.max_lat + delta_lat, 90.0),
            max_lon=min(self.max_lon + delta_lon, 180.0),
        )

    def intersects(self, other: "BoundingBox") -> bool:
        """
        Check whether two boxes overlap (edges touching counts).

        Args:
            other: The box to test against.

        Returns:
            True if the boxes overlap.
        """
        return not (
            other.min_lat > self.max_lat
            or other.max_lat < self.min_lat
            or other.min_lon > self.max_lon
            or other.max_lon < self.min_lon
        )


def as_float_array(values: ArrayLike) -> FloatArray:
    """
    Convert a sequence of numbers to a 1-D float64 array.

    Args:
        values: Numbers to convert.

    Returns:
        A float64 numpy array.
    """
    return np.asarray(values, dtype=np.float64).reshape(-1)


def bounding_box(lats: ArrayLike, lons: ArrayLike) -> BoundingBox | None:
    """
    Compute the bounding box of a set of coordinates.

    Args:
        lats: Latitudes in decimal degrees.
        lons: Longitudes in decimal degrees.

    Returns:
        The bounding box, or None when there are no points.
    """
    lat_array = as_float_array(lats)
    lon_array = as_float_array(lons)
    if lat_array.size == 0 or lon_array.size == 0:
        return None
    return BoundingBox(
        min_lat=float(lat_array.min()),
        min_lon=float(lon_array.min()),
        max_lat=float(lat_array.max()),
        max_lon=float(lon_array.max()),
    )


def haversine_m(
    lat1: ArrayLike,
    lon1: ArrayLike,
    lat2: ArrayLike,
    lon2: ArrayLike,
) -> FloatArray:
    """
    Great-circle distance in metres, element-wise.

    Args:
        lat1: Latitudes of the first points.
        lon1: Longitudes of the first points.
        lat2: Latitudes of the second points.
        lon2: Longitudes of the second points.

    Returns:
        Distances in metres, broadcast over the inputs.
    """
    phi1 = np.radians(np.asarray(lat1, dtype=np.float64))
    phi2 = np.radians(np.asarray(lat2, dtype=np.float64))
    delta_phi = phi2 - phi1
    delta_lambda = np.radians(np.asarray(lon2, dtype=np.float64) - np.asarray(lon1, dtype=np.float64))
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def cumulative_distance_m(lats: ArrayLike, lons: ArrayLike) -> FloatArray:
    """
    Distance travelled along a track up to each point.

    Args:
        lats: Track latitudes.
        lons: Track longitudes.

    Returns:
        Array of the same length; the first element is 0.
    """
    lat_array = as_float_array(lats)
    lon_array = as_float_array(lons)
    if lat_array.size == 0:
        return np.zeros(0, dtype=np.float64)
    steps = haversine_m(lat_array[:-1], lon_array[:-1], lat_array[1:], lon_array[1:])
    return np.concatenate(([0.0], np.cumsum(steps)))


def to_local_xy(
    lats: ArrayLike,
    lons: ArrayLike,
    ref_lat: float,
    ref_lon: float,
) -> tuple[FloatArray, FloatArray]:
    """
    Project coordinates to metres around a reference point.

    Uses an equirectangular projection: x grows east, y grows north.

    Args:
        lats: Latitudes in decimal degrees.
        lons: Longitudes in decimal degrees.
        ref_lat: Reference latitude (projection origin).
        ref_lon: Reference longitude (projection origin).

    Returns:
        Tuple of (x, y) arrays in metres.
    """
    cos_ref = math.cos(math.radians(ref_lat))
    x = np.radians(as_float_array(lons) - ref_lon) * EARTH_RADIUS_M * cos_ref
    y = np.radians(as_float_array(lats) - ref_lat) * EARTH_RADIUS_M
    return x, y


def from_local_xy(
    x: ArrayLike,
    y: ArrayLike,
    ref_lat: float,
    ref_lon: float,
) -> tuple[FloatArray, FloatArray]:
    """
    Inverse of :func:`to_local_xy`.

    Args:
        x: Eastings in metres.
        y: Northings in metres.
        ref_lat: Reference latitude used for the projection.
        ref_lon: Reference longitude used for the projection.

    Returns:
        Tuple of (lats, lons) in decimal degrees.
    """
    cos_ref = math.cos(math.radians(ref_lat))
    lats = ref_lat + np.degrees(as_float_array(y) / EARTH_RADIUS_M)
    lons = ref_lon + np.degrees(as_float_array(x) / (EARTH_RADIUS_M * cos_ref))
    return lats, lons


def simplify_indices(x: ArrayLike, y: ArrayLike, tolerance_m: float) -> NDArray[np.intp]:
    """
    Douglas-Peucker simplification of a projected polyline.

    Args:
        x: Eastings in metres.
        y: Northings in metres.
        tolerance_m: Maximum allowed deviation in metres.

    Returns:
        Sorted indices of the points to keep (always includes the
        first and last point).
    """
    x_array = as_float_array(x)
    y_array = as_float_array(y)
    count = x_array.size
    if count <= 2:
        return np.arange(count, dtype=np.intp)

    keep = np.zeros(count, dtype=bool)
    keep[0] = keep[-1] = True
    stack: list[tuple[int, int]] = [(0, count - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        distances, _ = point_segment_distance(
            x_array[first + 1 : last],
            y_array[first + 1 : last],
            x_array[first],
            y_array[first],
            x_array[last],
            y_array[last],
        )
        farthest = int(np.argmax(distances))
        if distances[farthest] > tolerance_m:
            split = first + 1 + farthest
            keep[split] = True
            stack.append((first, split))
            stack.append((split, last))
    return np.flatnonzero(keep)


def point_segment_distance(
    px: ArrayLike,
    py: ArrayLike,
    ax: ArrayLike,
    ay: ArrayLike,
    bx: ArrayLike,
    by: ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    """
    Distance from points to line segments AB, with broadcasting.

    Args:
        px: Point x coordinates.
        py: Point y coordinates.
        ax: Segment start x coordinates.
        ay: Segment start y coordinates.
        bx: Segment end x coordinates.
        by: Segment end y coordinates.

    Returns:
        Tuple of (distance, t) where t in [0, 1] is the position of
        the closest point along AB.
    """
    px_a = np.asarray(px, dtype=np.float64)
    py_a = np.asarray(py, dtype=np.float64)
    ax_a = np.asarray(ax, dtype=np.float64)
    ay_a = np.asarray(ay, dtype=np.float64)
    dx = np.asarray(bx, dtype=np.float64) - ax_a
    dy = np.asarray(by, dtype=np.float64) - ay_a
    length_sq = dx * dx + dy * dy
    with np.errstate(invalid="ignore", divide="ignore"):
        t = ((px_a - ax_a) * dx + (py_a - ay_a) * dy) / length_sq
    t = np.where(length_sq > 0, np.clip(t, 0.0, 1.0), 0.0)
    closest_x = ax_a + t * dx
    closest_y = ay_a + t * dy
    return np.hypot(px_a - closest_x, py_a - closest_y), t


def distances_to_polyline(
    px: ArrayLike,
    py: ArrayLike,
    line_x: ArrayLike,
    line_y: ArrayLike,
) -> FloatArray:
    """
    Minimum distance from each point to a polyline.

    Args:
        px: Point x coordinates.
        py: Point y coordinates.
        line_x: Polyline vertex x coordinates.
        line_y: Polyline vertex y coordinates.

    Returns:
        Distance in the same unit as the inputs, one per point.
    """
    px_a = as_float_array(px)
    py_a = as_float_array(py)
    lx = as_float_array(line_x)
    ly = as_float_array(line_y)
    if lx.size == 0:
        return np.full(px_a.size, np.inf)
    if lx.size == 1:
        return np.hypot(px_a - lx[0], py_a - ly[0])

    ax, ay, bx, by = lx[:-1], ly[:-1], lx[1:], ly[1:]
    edges = ax.size
    chunk = max(1, _MAX_PAIRS_PER_CHUNK // edges)
    result = np.empty(px_a.size, dtype=np.float64)
    for start in range(0, px_a.size, chunk):
        stop = start + chunk
        distances, _ = point_segment_distance(
            px_a[start:stop, None],
            py_a[start:stop, None],
            ax[None, :],
            ay[None, :],
            bx[None, :],
            by[None, :],
        )
        result[start:stop] = distances.min(axis=1)
    return result


def project_onto_polyline(
    px: float,
    py: float,
    line_x: ArrayLike,
    line_y: ArrayLike,
) -> tuple[int, float, float]:
    """
    Find the closest point on a polyline to a single point.

    Args:
        px: Point x coordinate.
        py: Point y coordinate.
        line_x: Polyline vertex x coordinates (at least two).
        line_y: Polyline vertex y coordinates (at least two).

    Returns:
        Tuple of (edge_index, t, distance): the closest point lies on
        the edge from vertex ``edge_index`` to ``edge_index + 1`` at
        fraction ``t``.

    Raises:
        ValueError: If the polyline has fewer than two vertices.
    """
    lx = as_float_array(line_x)
    ly = as_float_array(line_y)
    if lx.size < 2:
        raise ValueError("A polyline needs at least two vertices")
    distances, t = point_segment_distance(px, py, lx[:-1], ly[:-1], lx[1:], ly[1:])
    edge = int(np.argmin(distances))
    return edge, float(t[edge]), float(distances[edge])


def resample_by_distance(
    cumulative: ArrayLike,
    values: ArrayLike,
    step_m: float,
) -> tuple[FloatArray, FloatArray]:
    """
    Resample values onto an evenly spaced distance grid.

    Args:
        cumulative: Non-decreasing distance at each sample.
        values: Values at each sample.
        step_m: Grid spacing in metres.

    Returns:
        Tuple of (grid, resampled values). The grid starts at the
        first distance and always includes the last one.

    Raises:
        ValueError: If step_m is not positive.
    """
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    distance = as_float_array(cumulative)
    value_array = as_float_array(values)
    if distance.size == 0:
        return distance, value_array
    grid = np.arange(distance[0], distance[-1], step_m, dtype=np.float64)
    if grid.size == 0 or grid[-1] < distance[-1]:
        grid = np.append(grid, distance[-1])
    return grid, np.interp(grid, distance, value_array)


def max_step_m(cumulative: ArrayLike) -> float:
    """
    Largest gap between consecutive points of a track.

    Args:
        cumulative: Cumulative distance array.

    Returns:
        The largest step in metres, or 0 for fewer than two points.
    """
    distance = as_float_array(cumulative)
    if distance.size < 2:
        return 0.0
    return float(np.max(np.diff(distance)))
