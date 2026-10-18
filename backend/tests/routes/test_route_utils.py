"""Tests for route geometry, naming and GPX export."""

from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest

import core.geo as core_geo
import routes.constants as routes_constants
import routes.route.export as route_export
import routes.route.schema as route_schema
import routes.route.utils as route_utils
import routes.route_file_import.parsers as parsers

ORIGIN = (38.7223, -9.1393)


def _points(xy, ele_step=None):
    x = np.asarray([p[0] for p in xy], dtype=float)
    y = np.asarray([p[1] for p in xy], dtype=float)
    lats, lons = core_geo.from_local_xy(x, y, *ORIGIN)
    return [
        (float(lat), float(lon), None if ele_step is None else 100.0 + index * ele_step)
        for index, (lat, lon) in enumerate(zip(lats, lons, strict=True))
    ]


def test_build_geometry_stats():
    line = [(float(i * 10), 0.0) for i in range(101)]  # 1 km east
    geometry = route_utils.build_route_geometry(_points(line, ele_step=0.5))
    assert geometry.distance == pytest.approx(1000.0, rel=0.01)
    assert len(geometry.geometry) == 2
    assert (geometry.elevation_min, geometry.elevation_max) == (100, 150)
    assert geometry.elevation_gain == pytest.approx(50, abs=3)
    assert geometry.is_loop is False


def test_loop_detection_and_dedup():
    square = [(0.0, 0.0), (500.0, 0.0), (500.0, 500.0), (0.0, 500.0), (0.0, 20.0)]
    points = _points(square)
    points.insert(1, points[0])
    geometry = route_utils.build_route_geometry(points)
    assert geometry.is_loop is True
    assert geometry.elevation_gain is None
    assert len(geometry.geometry) == 5


def test_rejects_degenerate_routes():
    point = _points([(0.0, 0.0)])[0]
    with pytest.raises(route_utils.RouteGeometryError):
        route_utils.build_route_geometry([point, point])


def test_simplification_coarsens_to_fit_limit(monkeypatch):
    monkeypatch.setattr(routes_constants, "MAX_STORED_POINTS", 10)
    zigzag = [(float(i * 10), 0.0 if i % 2 else 5.0) for i in range(200)]
    geometry = route_utils.build_route_geometry(_points(zigzag))
    assert len(geometry.geometry) <= 10


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Morning_ride-2024.gpx", "Morning ride 2024"),
        ("C:\\Users\\me\\loop.fit", "loop"),
        ("dir/sub/course.tcx", "course"),
        (".gpx", "Route"),
        (None, "Route"),
    ],
)
def test_default_route_name(filename, expected):
    assert route_utils.default_route_name(filename) == expected


def test_export_filename():
    assert route_utils.export_filename("Castle Loop! (v2)", "gpx") == "castle-loop-v2.gpx"
    assert route_utils.export_filename("日本", "gpx") == "route.gpx"


def test_gpx_export_round_trip():
    route = SimpleNamespace(
        name="Castle loop",
        description="Climb",
        geometry=[[38.7, -9.1, 10.0], [38.71, -9.1, None]],
        waypoints=[route_schema.RoutePoi(name="Water", kind="water", lat=38.705, lon=-9.1, ele=12.0)],
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    parsed = parsers.parse_gpx(route_export.to_gpx(route).encode())
    assert parsed.name == "Castle loop"
    assert parsed.points == [(38.7, -9.1, 10.0), (38.71, -9.1, None)]
    [poi] = parsed.pois
    assert (poi.name, poi.kind, poi.ele) == ("Water", routes_constants.PoiKind.WATER, 12.0)


def _as_geometry(points):
    return [list(point) for point in points]


def test_trim_endpoints_cuts_both_ends():
    geometry = _as_geometry(_points([(0.0, 0.0), (500.0, 0.0), (1000.0, 0.0)], ele_step=10))
    trimmed = route_utils.trim_endpoints(geometry, 200)
    lats = [point[0] for point in trimmed]
    lons = [point[1] for point in trimmed]
    cumulative = core_geo.cumulative_distance_m(lats, lons)
    assert float(cumulative[-1]) == pytest.approx(600.0, rel=0.01)
    assert float(core_geo.haversine_m(*geometry[0][:2], *trimmed[0][:2])) == pytest.approx(200.0, rel=0.01)
    assert float(core_geo.haversine_m(*geometry[-1][:2], *trimmed[-1][:2])) == pytest.approx(200.0, rel=0.01)
    # The cut points interpolate elevation; the middle vertex is kept as is.
    assert trimmed[0][2] == pytest.approx(104.0, abs=0.1)
    assert trimmed[1] == geometry[1]


def test_trim_endpoints_edge_cases():
    geometry = _as_geometry(_points([(0.0, 0.0), (300.0, 0.0)]))
    assert route_utils.trim_endpoints(geometry, 0) == geometry
    assert route_utils.trim_endpoints(geometry, 150) == []
    trimmed = route_utils.trim_endpoints(geometry, 100)
    assert len(trimmed) == 2
    assert trimmed[0][2] is None


def test_near_any():
    (lat, lon, _), (far_lat, far_lon, _) = _points([(0.0, 0.0), (500.0, 0.0)])
    assert route_utils.near_any(lat, lon, [(far_lat, far_lon), (lat, lon)], 10)
    assert not route_utils.near_any(lat, lon, [(far_lat, far_lon)], 400)
