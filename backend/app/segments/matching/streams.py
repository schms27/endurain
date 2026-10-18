"""Convert activity stream waypoints into arrays for segment work."""

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray

import activities.activity.utils as activities_utils


@dataclass(frozen=True)
class TrackArrays:
    """
    GPS track as parallel arrays.

    Attributes:
        indices: Index of each point in the original lat/lon stream.
        lats: Latitudes.
        lons: Longitudes.
        times: Unix timestamps in seconds.
    """

    indices: NDArray[np.intp]
    lats: NDArray[np.float64]
    lons: NDArray[np.float64]
    times: NDArray[np.float64]

    @property
    def size(self) -> int:
        """Number of points."""
        return int(self.lats.size)


def parse_waypoint_time(value: object) -> float | None:
    """
    Parse a waypoint timestamp into Unix seconds.

    Naive timestamps are treated as UTC, matching how importers store them.

    Args:
        value: ISO 8601 string or datetime.

    Returns:
        Unix seconds, or None when the value cannot be parsed.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def track_from_waypoints(waypoints: list[dict] | None) -> TrackArrays:
    """
    Build track arrays from a lat/lon stream.

    Points without coordinates or a parsable time are dropped, and so is
    any point whose time is not after the previous kept point (the
    matcher needs strictly increasing times). ``indices`` keeps the
    position of each kept point in the original stream.

    Args:
        waypoints: Map stream waypoints (``time``, ``lat``, ``lon``).

    Returns:
        The track arrays (possibly empty).
    """
    indices: list[int] = []
    lats: list[float] = []
    lons: list[float] = []
    times: list[float] = []
    for index, waypoint in enumerate(waypoints or []):
        if not isinstance(waypoint, dict):
            continue
        lat, lon = waypoint.get("lat"), waypoint.get("lon")
        time = parse_waypoint_time(waypoint.get("time"))
        if lat is None or lon is None or time is None:
            continue
        if times and time <= times[-1]:
            continue
        indices.append(index)
        lats.append(float(lat))
        lons.append(float(lon))
        times.append(time)
    return TrackArrays(
        indices=np.asarray(indices, dtype=np.intp),
        lats=np.asarray(lats, dtype=np.float64),
        lons=np.asarray(lons, dtype=np.float64),
        times=np.asarray(times, dtype=np.float64),
    )


def values_by_time(waypoints: list[dict] | None, key: str) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    Extract a metric stream as (times, values) arrays.

    Args:
        waypoints: Stream waypoints (``time`` plus ``key``).
        key: Value key, e.g. ``hr``, ``power``, ``cad``, ``ele``.

    Returns:
        Tuple of (Unix seconds, values), skipping unusable points.
    """
    times: list[float] = []
    values: list[float] = []
    for waypoint in waypoints or []:
        if not isinstance(waypoint, dict):
            continue
        value = waypoint.get(key)
        time = parse_waypoint_time(waypoint.get("time"))
        if value is None or time is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
        times.append(time)
    return np.asarray(times, dtype=np.float64), np.asarray(values, dtype=np.float64)


@dataclass(frozen=True)
class EffortMetrics:
    """
    Summary metrics over an effort's time window.

    Attributes:
        average_hr: Average heart rate, zeros excluded.
        max_hr: Maximum heart rate.
        average_power: Average power.
        normalized_power: Normalized power.
        average_cad: Average cadence, zeros excluded.
    """

    average_hr: int | None = None
    max_hr: int | None = None
    average_power: int | None = None
    normalized_power: int | None = None
    average_cad: int | None = None


def _window(
    series: tuple[NDArray[np.float64], NDArray[np.float64]],
    start: float,
    end: float,
) -> NDArray[np.float64]:
    times, values = series
    if times.size == 0:
        return values
    return values[(times >= start) & (times <= end)]


def effort_metrics(
    hr: tuple[NDArray[np.float64], NDArray[np.float64]],
    power: tuple[NDArray[np.float64], NDArray[np.float64]],
    cadence: tuple[NDArray[np.float64], NDArray[np.float64]],
    start: float,
    end: float,
) -> EffortMetrics:
    """
    Compute summary metrics for one effort.

    Args:
        hr: Heart rate (times, values).
        power: Power (times, values).
        cadence: Cadence (times, values).
        start: Effort start (Unix seconds).
        end: Effort end (Unix seconds).

    Returns:
        The effort metrics; fields are None without data.
    """
    hr_values = _window(hr, start, end)
    hr_values = hr_values[hr_values > 0]
    power_values = _window(power, start, end)
    cad_values = _window(cadence, start, end)
    cad_values = cad_values[cad_values > 0]

    normalized_power: int | None = None
    if power_values.size:
        normalized = activities_utils.calculate_np([{"power": float(v)} for v in power_values])
        normalized_power = round(normalized) if normalized else None

    return EffortMetrics(
        average_hr=round(float(hr_values.mean())) if hr_values.size else None,
        max_hr=round(float(hr_values.max())) if hr_values.size else None,
        average_power=round(float(power_values.mean())) if power_values.size else None,
        normalized_power=normalized_power,
        average_cad=round(float(cad_values.mean())) if cad_values.size else None,
    )
