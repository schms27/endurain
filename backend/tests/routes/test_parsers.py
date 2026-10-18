"""Tests for route file parsers."""

from unittest.mock import MagicMock, patch

import fitdecode
import pytest

import routes.constants as routes_constants
import routes.route_file_import.parsers as parsers

GPX_TRACK = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>Castle loop</name><desc>Nice &lt;b&gt;climb&lt;/b&gt;</desc></metadata>
  <wpt lat="38.70" lon="-9.10"><ele>50</ele><name>Fountain</name><sym>Drinking Water</sym></wpt>
  <wpt lat="38.71" lon="-9.11"><name>Top</name><type>Summit</type></wpt>
  <wpt lat="38.72" lon="-9.12"><name>Bench</name></wpt>
  <trk><name>Track name</name>
    <trkseg>
      <trkpt lat="38.700" lon="-9.100"><ele>10</ele></trkpt>
      <trkpt lat="38.701" lon="-9.100"><ele>12</ele></trkpt>
    </trkseg>
    <trkseg>
      <trkpt lat="38.702" lon="-9.100"/>
      <trkpt lat="91.0" lon="-9.100"/>
    </trkseg>
  </trk>
</gpx>"""

GPX_ROUTE_ONLY = b"""<?xml version="1.0"?>
<gpx version="1.1" creator="planner" xmlns="http://www.topografix.com/GPX/1/1">
  <rte><name>Planned</name>
    <rtept lat="1.0" lon="2.0"/><rtept lat="1.1" lon="2.1"/><rtept lat="1.2" lon="2.2"/>
  </rte>
</gpx>"""

TCX_COURSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Courses><Course><Name>Coast ride</Name>
    <Track>
      <Trackpoint><Position><LatitudeDegrees>1.0</LatitudeDegrees><LongitudeDegrees>2.0</LongitudeDegrees></Position>
        <AltitudeMeters>5.5</AltitudeMeters></Trackpoint>
      <Trackpoint><Position><LatitudeDegrees>1.1</LatitudeDegrees><LongitudeDegrees>2.1</LongitudeDegrees></Position>
      </Trackpoint>
      <Trackpoint><AltitudeMeters>7</AltitudeMeters></Trackpoint>
    </Track>
    <CoursePoint><Name>Cafe</Name><Position><LatitudeDegrees>1.05</LatitudeDegrees>
      <LongitudeDegrees>2.05</LongitudeDegrees></Position><PointType>Food</PointType><Notes>Coffee</Notes></CoursePoint>
  </Course></Courses>
</TrainingCenterDatabase>"""

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
<!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
<!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
<!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
<!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
<!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">]>
<TrainingCenterDatabase><Name>&lol9;</Name></TrainingCenterDatabase>"""


class TestGpx:
    def test_tracks_pois_and_metadata(self):
        route = parsers.parse_gpx(GPX_TRACK)
        assert route.name == "Castle loop"
        assert route.description == "Nice <b>climb</b>"
        # The out-of-range point is dropped; segments are concatenated.
        assert route.points == [(38.7, -9.1, 10.0), (38.701, -9.1, 12.0), (38.702, -9.1, None)]
        assert [(poi.name, poi.kind) for poi in route.pois] == [
            ("Fountain", routes_constants.PoiKind.WATER),
            ("Top", routes_constants.PoiKind.SUMMIT),
            ("Bench", routes_constants.PoiKind.GENERIC),
        ]
        assert route.pois[0].to_dict()["ele"] == 50.0

    def test_route_elements_when_no_track(self):
        route = parsers.parse_gpx(GPX_ROUTE_ONLY)
        assert route.name == "Planned"
        assert len(route.points) == 3

    def test_invalid_gpx(self):
        with pytest.raises(parsers.RouteFileError):
            parsers.parse_gpx(b"<gpx><trk>")


class TestTcx:
    def test_course(self):
        route = parsers.parse_tcx(TCX_COURSE)
        assert route.name == "Coast ride"
        assert route.points == [(1.0, 2.0, 5.5), (1.1, 2.1, None)]
        [poi] = route.pois
        assert (poi.name, poi.kind, poi.description) == ("Cafe", routes_constants.PoiKind.FOOD, "Coffee")

    def test_invalid_tcx(self):
        with pytest.raises(parsers.RouteFileError):
            parsers.parse_tcx(b"not xml")

    def test_entity_expansion_is_rejected(self):
        with pytest.raises(parsers.RouteFileError):
            parsers.parse_tcx(BILLION_LAUGHS)


def _fit_message(message_name, **fields):
    message = MagicMock(spec=fitdecode.FitDataMessage)
    message.name = message_name

    def get_value(key):
        if key not in fields:
            raise KeyError(key)
        return fields[key]

    message.get_value.side_effect = get_value
    return message


SEMI = 2**31 / 180.0


class TestFit:
    def test_course_records_and_points(self):
        frames = [
            MagicMock(),  # non-data frame (header)
            _fit_message("course", name="Morning ride"),
            _fit_message("record", position_lat=1.0 * SEMI, position_long=2.0 * SEMI, enhanced_altitude=100.0),
            _fit_message("record", position_lat=1.1 * SEMI, position_long=2.1 * SEMI, altitude=101.0),
            _fit_message("record", heart_rate=120),
            _fit_message("course_point", position_lat=1.05 * SEMI, position_long=2.05 * SEMI, type="water"),
            _fit_message("course_point", type="summit"),
        ]
        with patch("routes.route_file_import.parsers.fitdecode.FitReader", return_value=frames):
            route = parsers.parse_fit(b"fit")
        assert route.name == "Morning ride"
        assert [(round(lat, 6), round(lon, 6), ele) for lat, lon, ele in route.points] == [
            (1.0, 2.0, 100.0),
            (1.1, 2.1, 101.0),
        ]
        [poi] = route.pois
        assert (poi.kind, poi.name) == (routes_constants.PoiKind.WATER, "Water")

    def test_invalid_fit(self):
        with (
            patch("routes.route_file_import.parsers.fitdecode.FitReader", side_effect=fitdecode.FitError("bad")),
            pytest.raises(parsers.RouteFileError, match="Invalid FIT"),
        ):
            parsers.parse_fit(b"fit")


@pytest.mark.parametrize(
    ("lat", "lon", "ele", "expected"),
    [
        (1, 2, 3, (1.0, 2.0, 3.0)),
        ("1.5", "2.5", None, (1.5, 2.5, None)),
        (1, 2, "high", (1.0, 2.0, None)),
        (1, 2, 20_000, (1.0, 2.0, None)),
        (95, 2, None, None),
        (1, 200, None, None),
        (float("nan"), 2, None, None),
        (None, 2, None, None),
    ],
)
def test_valid_point(lat, lon, ele, expected):
    assert parsers.valid_point(lat, lon, ele) == expected


def test_parse_route_file_dispatch_and_errors(monkeypatch):
    assert len(parsers.parse_route_file(GPX_ROUTE_ONLY, "gpx").points) == 3
    with pytest.raises(parsers.RouteFileError, match="Unsupported"):
        parsers.parse_route_file(GPX_ROUTE_ONLY, "kml")
    with pytest.raises(parsers.RouteFileError, match="no usable path"):
        parsers.parse_route_file(b'<gpx version="1.1" creator="x"></gpx>', "gpx")
    monkeypatch.setattr(routes_constants, "MAX_RAW_POINTS", 2)
    with pytest.raises(parsers.RouteFileError, match="too many points"):
        parsers.parse_route_file(GPX_ROUTE_ONLY, "gpx")


def test_poi_limit(monkeypatch):
    monkeypatch.setattr(routes_constants, "MAX_POIS", 1)
    assert len(parsers.parse_gpx(GPX_TRACK).pois) == 1
