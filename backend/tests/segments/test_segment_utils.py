"""Tests for building segment geometry from an activity slice."""

import numpy as np
import pytest

import segments.constants as segments_constants
import segments.segment.utils as segment_utils
from tests._helpers import tracks

RUN = segments_constants.SportGroup.RUN


def _waypoints(path, speed=5.0):
    lats, lons, times = tracks.track(path, speed_mps=speed)
    return [
        {"time": f"t{index}", "lat": float(lat), "lon": float(lon)}
        for index, (lat, lon, _) in enumerate(zip(lats, lons, times, strict=True))
    ]


def _elevations(waypoints, step):
    return [{"time": waypoint["time"], "ele": 100.0 + index * step} for index, waypoint in enumerate(waypoints)]


def test_builds_simplified_geometry_with_grades():
    """A straight climbing slice keeps its ends, distance and grades."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    geometry = segment_utils.build_segment_geometry(waypoints, _elevations(waypoints, 0.5), 0, 100, RUN)

    assert geometry.distance == pytest.approx(500.0, rel=0.01)
    assert len(geometry.geometry) == 2
    assert geometry.geometry[0][2] == 100.0
    assert geometry.average_grade == pytest.approx(10.0, abs=0.1)
    assert geometry.maximum_grade == pytest.approx(10.0, abs=0.1)
    assert geometry.elevation_gain == pytest.approx(50, abs=3)
    assert geometry.elevation_loss == 0
    assert geometry.start == (waypoints[0]["lat"], waypoints[0]["lon"])
    assert geometry.end == (waypoints[100]["lat"], waypoints[100]["lon"])
    assert geometry.bbox.min_lon == pytest.approx(waypoints[0]["lon"])


def test_corner_is_kept_by_simplification():
    """Turns survive simplification."""
    waypoints = _waypoints([(0.0, 0.0), (300.0, 0.0), (300.0, 300.0)])
    geometry = segment_utils.build_segment_geometry(waypoints, None, 0, len(waypoints) - 1, RUN)
    assert len(geometry.geometry) == 3


def test_without_elevation():
    """No elevation stream means no elevation stats."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    geometry = segment_utils.build_segment_geometry(waypoints, None, 0, 100, RUN)
    assert (geometry.elevation_gain, geometry.average_grade, geometry.maximum_grade) == (None, None, None)
    assert geometry.geometry[0][2] is None


def test_partial_elevation_skips_maximum_grade():
    """Gaps in the elevation stream disable the windowed maximum grade."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    elevations = _elevations(waypoints, 0.5)[::2]
    geometry = segment_utils.build_segment_geometry(waypoints, elevations, 0, 100, RUN)
    assert geometry.average_grade is not None
    assert geometry.maximum_grade is None


def test_maximum_grade_needs_a_full_window():
    """Tracks shorter than the grade window have no maximum grade."""
    cumulative = np.asarray([0.0, 40.0, 80.0])
    assert segment_utils._maximum_grade(cumulative, np.asarray([0.0, 4.0, 8.0])) is None
    longer = np.asarray([0.0, 50.0, 100.0, 150.0])
    assert segment_utils._maximum_grade(longer, np.asarray([0.0, 1.0, 12.0, 13.0])) == pytest.approx(12.0)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (-1, 50, "outside"),
        (0, 10_000, "outside"),
        (50, 50, "outside"),
        (0, 5, "at least"),
        (0, 20, "shorter"),
    ],
)
def test_rejects_bad_slices(start, end, message):
    """Out-of-range, tiny and short slices are rejected."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    with pytest.raises(segment_utils.SegmentGeometryError, match=message):
        segment_utils.build_segment_geometry(waypoints, None, start, end, RUN)


def test_rejects_too_long(monkeypatch):
    """Slices above the maximum length are rejected."""
    monkeypatch.setattr(segments_constants, "MAX_SEGMENT_DISTANCE_M", 300.0)
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    with pytest.raises(segment_utils.SegmentGeometryError, match="longer"):
        segment_utils.build_segment_geometry(waypoints, None, 0, 100, RUN)


def test_rejects_gps_gap():
    """A jump larger than the gap limit is rejected."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    lat, lon = tracks.to_lat_lon(np.asarray([1500.0]), np.asarray([0.0]))
    waypoints[60] = {"time": "t60", "lat": float(lat[0]), "lon": float(lon[0])}
    with pytest.raises(segment_utils.SegmentGeometryError, match="gap"):
        segment_utils.build_segment_geometry(waypoints, None, 0, 100, RUN)


def test_skips_points_without_coordinates():
    """Points missing lat/lon are ignored."""
    waypoints = _waypoints([(0.0, 0.0), (500.0, 0.0)])
    waypoints[10] = {"time": "t10", "lat": None, "lon": None}
    geometry = segment_utils.build_segment_geometry(waypoints, None, 0, 100, RUN)
    assert geometry.distance == pytest.approx(500.0, rel=0.01)
