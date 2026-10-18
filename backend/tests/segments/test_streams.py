"""Tests for stream waypoint parsing used by segment matching."""

from datetime import UTC, datetime

import numpy as np
import pytest

import segments.matching.streams as streams


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-01-01T00:00:00", 1_704_067_200.0),
        ("2024-01-01T01:00:00+01:00", 1_704_067_200.0),
        ("2024-01-01T00:00:00Z", 1_704_067_200.0),
        (datetime(2024, 1, 1, tzinfo=UTC), 1_704_067_200.0),
        (datetime(2024, 1, 1), 1_704_067_200.0),
        ("not a time", None),
        ("", None),
        (None, None),
        (12, None),
    ],
)
def test_parse_waypoint_time(value, expected):
    """ISO strings and datetimes parse to Unix seconds; naive means UTC."""
    assert streams.parse_waypoint_time(value) == expected


def test_track_from_waypoints_drops_unusable_points():
    """Missing coordinates, bad times and non-increasing times are dropped."""
    waypoints = [
        {"time": "2024-01-01T00:00:00", "lat": 1.0, "lon": 2.0},
        {"time": "2024-01-01T00:00:01", "lat": None, "lon": 2.0},
        "garbage",
        {"time": "bad", "lat": 1.0, "lon": 2.0},
        {"time": "2024-01-01T00:00:00", "lat": 1.1, "lon": 2.1},
        {"time": "2024-01-01T00:00:02", "lat": 1.2, "lon": 2.2},
    ]
    track = streams.track_from_waypoints(waypoints)
    assert track.size == 2
    assert track.indices.tolist() == [0, 5]
    assert track.lats.tolist() == [1.0, 1.2]
    assert track.times[1] - track.times[0] == 2.0


def test_track_from_no_waypoints():
    """None or empty input yields an empty track."""
    assert streams.track_from_waypoints(None).size == 0


def test_values_by_time():
    """Values are extracted with their timestamps, skipping bad entries."""
    waypoints = [
        {"time": "2024-01-01T00:00:00", "hr": 100},
        {"time": "2024-01-01T00:00:01", "hr": None},
        {"time": "2024-01-01T00:00:02", "hr": "x"},
        {"time": "bad", "hr": 120},
        "garbage",
        {"time": "2024-01-01T00:00:03", "hr": "130"},
    ]
    times, values = streams.values_by_time(waypoints, "hr")
    assert values.tolist() == [100.0, 130.0]
    assert (times[1] - times[0]) == 3.0
    empty_times, empty_values = streams.values_by_time(None, "hr")
    assert empty_times.size == empty_values.size == 0


def _series(values, start=0.0):
    return np.arange(start, start + len(values), dtype=np.float64), np.asarray(values, dtype=np.float64)


def test_effort_metrics_over_window():
    """Averages and maxima cover only the effort window; zeros are ignored."""
    hr = _series([90, 0, 150, 160, 200])
    power = _series([100, 200, 300, 400, 500])
    cadence = _series([0, 80, 90, 0, 100])
    metrics = streams.effort_metrics(hr, power, cadence, start=1.0, end=3.0)
    assert (metrics.average_hr, metrics.max_hr) == (155, 160)
    assert metrics.average_power == 300
    assert metrics.normalized_power == 329
    assert metrics.average_cad == 85


def test_effort_metrics_without_data():
    """Missing streams give empty metrics."""
    empty = (np.zeros(0), np.zeros(0))
    assert streams.effort_metrics(empty, empty, empty, 0.0, 10.0) == streams.EffortMetrics()
