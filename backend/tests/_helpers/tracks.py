"""Synthetic GPS track builders for segment matching tests.

Tracks are described in local metres (x east, y north) around a fixed
origin and converted to lat/lon with :func:`core.geo.from_local_xy`, so
tests can reason about geometry in metres.
"""

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

import core.geo as core_geo

ORIGIN_LAT: float = 38.7223
ORIGIN_LON: float = -9.1393


def polyline_xy(vertices: Sequence[tuple[float, float]], spacing_m: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Densify a polyline given by its vertices.

    Args:
        vertices: Polyline vertices in metres.
        spacing_m: Distance between generated points.

    Returns:
        Tuple of (x, y) arrays including every vertex.
    """
    xs: list[float] = [vertices[0][0]]
    ys: list[float] = [vertices[0][1]]
    for (x0, y0), (x1, y1) in pairwise(vertices):
        length = float(np.hypot(x1 - x0, y1 - y0))
        steps = max(1, int(np.ceil(length / spacing_m)))
        for step in range(1, steps + 1):
            fraction = step / steps
            xs.append(x0 + fraction * (x1 - x0))
            ys.append(y0 + fraction * (y1 - y0))
    return np.asarray(xs), np.asarray(ys)


def to_lat_lon(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert local metres to lat/lon around the test origin.

    Args:
        x: Eastings in metres.
        y: Northings in metres.

    Returns:
        Tuple of (lats, lons).
    """
    return core_geo.from_local_xy(x, y, ORIGIN_LAT, ORIGIN_LON)


def segment(vertices: Sequence[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    """
    Build segment geometry from vertices (densified every 5 m).

    Args:
        vertices: Segment vertices in metres.

    Returns:
        Tuple of (lats, lons).
    """
    return to_lat_lon(*polyline_xy(vertices, 5.0))


def track(
    vertices: Sequence[tuple[float, float]],
    speed_mps: float = 5.0,
    interval_s: float | Sequence[float] = 1.0,
    noise_m: float = 0.0,
    seed: int = 0,
    start_time: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate a recording moving along a path at constant speed.

    Args:
        vertices: Path vertices in metres.
        speed_mps: Constant speed in m/s.
        interval_s: Recording interval in seconds, or a sequence of
            intervals cycled through (smart recording).
        noise_m: Standard deviation of Gaussian position noise.
        seed: Random seed for the noise.
        start_time: Timestamp of the first point.

    Returns:
        Tuple of (lats, lons, times).
    """
    dense_x, dense_y = polyline_xy(vertices, 0.5)
    along = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(dense_x), np.diff(dense_y)))))
    duration = along[-1] / speed_mps
    intervals = [interval_s] if isinstance(interval_s, (int, float)) else list(interval_s)
    times = [0.0]
    index = 0
    while times[-1] < duration:
        times.append(min(times[-1] + intervals[index % len(intervals)], duration))
        index += 1
    time_array = np.asarray(times)
    distance = time_array * speed_mps
    x = np.interp(distance, along, dense_x)
    y = np.interp(distance, along, dense_y)
    if noise_m:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0.0, noise_m, x.size)
        y = y + rng.normal(0.0, noise_m, y.size)
    lats, lons = to_lat_lon(x, y)
    return lats, lons, time_array + start_time
