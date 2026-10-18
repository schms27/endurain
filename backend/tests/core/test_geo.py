"""Tests for the GPS geometry helpers."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import core.geo as core_geo

LISBON = (38.7223, -9.1393)


def test_haversine_one_degree_of_latitude():
    """One degree of latitude is roughly 111.2 km."""
    distance = core_geo.haversine_m(0.0, 0.0, 1.0, 0.0)
    assert distance == pytest.approx(111_195, rel=1e-3)


def test_haversine_zero_for_same_point():
    """Distance from a point to itself is zero."""
    assert core_geo.haversine_m(*LISBON, *LISBON) == pytest.approx(0.0)


def test_cumulative_distance_starts_at_zero_and_grows():
    """Cumulative distance is monotonic and starts at zero."""
    lats = [0.0, 0.001, 0.002, 0.003]
    lons = [0.0, 0.0, 0.0, 0.0]
    cumulative = core_geo.cumulative_distance_m(lats, lons)
    assert cumulative[0] == 0.0
    assert np.all(np.diff(cumulative) > 0)
    assert cumulative[-1] == pytest.approx(333.6, rel=1e-3)


def test_cumulative_distance_empty():
    """An empty track has an empty cumulative distance."""
    assert core_geo.cumulative_distance_m([], []).size == 0


def test_bounding_box_and_padding():
    """Bounding box covers all points and padding grows it."""
    box = core_geo.bounding_box([1.0, 2.0, 1.5], [10.0, 11.0, 10.5])
    assert box == core_geo.BoundingBox(1.0, 10.0, 2.0, 11.0)
    padded = box.padded(1000)
    assert padded.min_lat < box.min_lat
    assert padded.max_lon > box.max_lon
    assert (box.min_lat - padded.min_lat) == pytest.approx(math.degrees(1000 / core_geo.EARTH_RADIUS_M))


def test_bounding_box_empty():
    """No points means no bounding box."""
    assert core_geo.bounding_box([], []) is None


def test_bounding_box_padding_clamps_to_valid_range():
    """Padding never leaves valid coordinate ranges."""
    box = core_geo.BoundingBox(89.99, 179.99, 89.999, 179.999).padded(10_000)
    assert box.max_lat == 90.0
    assert box.max_lon == 180.0


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (core_geo.BoundingBox(0.5, 0.5, 1.5, 1.5), True),
        (core_geo.BoundingBox(1.0, 1.0, 2.0, 2.0), True),
        (core_geo.BoundingBox(1.1, 0.0, 2.0, 1.0), False),
        (core_geo.BoundingBox(0.0, -2.0, 1.0, -1.1), False),
    ],
)
def test_bounding_box_intersects(other, expected):
    """Overlapping and touching boxes intersect; disjoint ones do not."""
    box = core_geo.BoundingBox(0.0, 0.0, 1.0, 1.0)
    assert box.intersects(other) is expected
    assert other.intersects(box) is expected


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.floats(min_value=-60, max_value=60),
    st.floats(min_value=-170, max_value=170),
    st.floats(min_value=-20_000, max_value=20_000),
    st.floats(min_value=-20_000, max_value=20_000),
)
def test_local_projection_round_trip(ref_lat, ref_lon, x, y):
    """Projecting to metres and back returns the original point."""
    lats, lons = core_geo.from_local_xy([x], [y], ref_lat, ref_lon)
    x2, y2 = core_geo.to_local_xy(lats, lons, ref_lat, ref_lon)
    assert x2[0] == pytest.approx(x, abs=1e-6)
    assert y2[0] == pytest.approx(y, abs=1e-6)


def test_local_projection_matches_haversine():
    """Projected distances agree with haversine at segment scale."""
    lats, lons = core_geo.from_local_xy([0.0, 3000.0], [0.0, 4000.0], *LISBON)
    x, y = core_geo.to_local_xy(lats, lons, *LISBON)
    projected = math.hypot(x[1] - x[0], y[1] - y[0])
    true = core_geo.haversine_m(lats[0], lons[0], lats[1], lons[1])
    assert projected == pytest.approx(5000.0)
    assert projected == pytest.approx(float(true), rel=5e-3)


def test_simplify_keeps_corners_and_drops_collinear_points():
    """Collinear points vanish, corners stay."""
    x = [0, 1, 2, 3, 4, 4, 4, 4]
    y = [0, 0, 0, 0, 0, 1, 2, 3]
    assert core_geo.simplify_indices(x, y, 0.1).tolist() == [0, 4, 7]


def test_simplify_short_inputs():
    """Two or fewer points are kept as-is."""
    assert core_geo.simplify_indices([0, 1], [0, 1], 1.0).tolist() == [0, 1]
    assert core_geo.simplify_indices([], [], 1.0).tolist() == []


def test_simplify_respects_tolerance():
    """A small bump below the tolerance is removed, above it is kept."""
    x = [0, 5, 10]
    y = [0, 0.5, 0]
    assert core_geo.simplify_indices(x, y, 1.0).tolist() == [0, 2]
    assert core_geo.simplify_indices(x, y, 0.1).tolist() == [0, 1, 2]


def test_point_segment_distance_inside_and_beyond_ends():
    """Distance uses the perpendicular foot or the nearest endpoint."""
    distance, t = core_geo.point_segment_distance([5, -3, 14], [2, 0, 3], 0, 0, 10, 0)
    assert distance.tolist() == pytest.approx([2.0, 3.0, 5.0])
    assert t.tolist() == pytest.approx([0.5, 0.0, 1.0])


def test_point_segment_distance_degenerate_segment():
    """A zero-length segment behaves like a point."""
    distance, t = core_geo.point_segment_distance(3, 4, 0, 0, 0, 0)
    assert float(distance) == pytest.approx(5.0)
    assert float(t) == 0.0


def test_distances_to_polyline():
    """Each point gets its distance to the nearest edge."""
    distances = core_geo.distances_to_polyline([5, 12, -1], [1, 5, 0], [0, 10, 10], [0, 0, 10])
    assert distances.tolist() == pytest.approx([1.0, 2.0, 1.0])


def test_distances_to_polyline_chunking(monkeypatch):
    """Chunked evaluation gives the same result as a single pass."""
    rng = np.random.default_rng(1)
    px, py = rng.uniform(-50, 50, 200), rng.uniform(-50, 50, 200)
    lx, ly = rng.uniform(-50, 50, 30), rng.uniform(-50, 50, 30)
    expected = core_geo.distances_to_polyline(px, py, lx, ly)
    monkeypatch.setattr(core_geo, "_MAX_PAIRS_PER_CHUNK", 50)
    assert core_geo.distances_to_polyline(px, py, lx, ly).tolist() == pytest.approx(expected.tolist())


def test_distances_to_degenerate_polylines():
    """Empty and single-vertex polylines are handled."""
    assert np.isinf(core_geo.distances_to_polyline([0], [0], [], [])).all()
    assert core_geo.distances_to_polyline([3], [4], [0], [0]).tolist() == pytest.approx([5.0])


def test_project_onto_polyline():
    """Projection returns the edge, fraction and distance."""
    edge, t, distance = core_geo.project_onto_polyline(10, 7.5, [0, 10, 10], [0, 0, 10])
    assert edge == 1
    assert t == pytest.approx(0.75)
    assert distance == pytest.approx(0.0)


def test_project_onto_polyline_requires_two_vertices():
    """A single vertex is not a polyline."""
    with pytest.raises(ValueError):
        core_geo.project_onto_polyline(0, 0, [0], [0])


def test_resample_by_distance():
    """Resampling interpolates onto an even grid ending at the last point."""
    grid, values = core_geo.resample_by_distance([0, 10, 25], [0, 100, 250], 10)
    assert grid.tolist() == [0, 10, 20, 25]
    assert values.tolist() == pytest.approx([0, 100, 200, 250])


def test_resample_by_distance_edge_cases():
    """Empty input and invalid steps."""
    grid, values = core_geo.resample_by_distance([], [], 5)
    assert grid.size == 0 and values.size == 0
    grid, values = core_geo.resample_by_distance([7], [3], 5)
    assert grid.tolist() == [7] and values.tolist() == [3]
    with pytest.raises(ValueError):
        core_geo.resample_by_distance([0, 1], [0, 1], 0)


def test_max_step():
    """Largest gap between consecutive points."""
    assert core_geo.max_step_m([0, 5, 30, 32]) == 25
    assert core_geo.max_step_m([0]) == 0.0
