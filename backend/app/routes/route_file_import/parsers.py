"""Parse route files (GPX, TCX, FIT) into a time-free path.

Kept separate from the activity importers: routes need no timestamps, read
GPX ``<rte>`` and ``<wpt>`` elements, and accept TCX/FIT *course* files.
"""

import io
import math

# The stdlib parser never resolves external entities, and the bundled expat
# (>= 2.4.1) rejects entity-expansion bombs, so it is safe on uploads here.
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field

import fitdecode
import gpxpy
import gpxpy.gpx

import core.sanitization as core_sanitization
import routes.constants as routes_constants

RoutePoint = tuple[float, float, float | None]


class RouteFileError(ValueError):
    """Raised when a file cannot be read as a route."""


@dataclass
class Poi:
    """
    A point of interest along a route.

    Attributes:
        name: Display name.
        description: Optional description.
        kind: POI category.
        lat: Latitude.
        lon: Longitude.
        ele: Elevation in metres, if known.
    """

    name: str
    description: str | None
    kind: routes_constants.PoiKind
    lat: float
    lon: float
    ele: float | None = None

    def to_dict(self) -> dict:
        """Serialise for the JSON ``waypoints`` column."""
        return {
            "name": self.name,
            "description": self.description,
            "kind": self.kind.value,
            "lat": self.lat,
            "lon": self.lon,
            "ele": self.ele,
        }


@dataclass
class ParsedRoute:
    """
    A route read from a file.

    Attributes:
        name: Name found in the file, if any.
        description: Description found in the file, if any.
        points: Ordered ``(lat, lon, ele)`` points.
        pois: Points of interest.
    """

    name: str | None = None
    description: str | None = None
    points: list[RoutePoint] = field(default_factory=list)
    pois: list[Poi] = field(default_factory=list)


def valid_point(lat: object, lon: object, ele: object = None) -> RoutePoint | None:
    """
    Normalise a coordinate, rejecting out-of-range or non-numeric values.

    Args:
        lat: Latitude candidate.
        lon: Longitude candidate.
        ele: Elevation candidate.

    Returns:
        The point, or None if the coordinate is unusable.
    """
    try:
        lat_f, lon_f = float(lat), float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lon_f) and -90 <= lat_f <= 90 and -180 <= lon_f <= 180):
        return None
    ele_f: float | None = None
    if ele is not None:
        try:
            ele_f = float(ele)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            ele_f = None
        if ele_f is not None and not (math.isfinite(ele_f) and -500 <= ele_f <= 9000):
            ele_f = None
    return lat_f, lon_f, ele_f


def poi_kind(*labels: str | None) -> routes_constants.PoiKind:
    """
    Map free-text POI labels (symbol, type) to a POI kind.

    Args:
        *labels: Labels from the file, any of which may be None.

    Returns:
        The best matching kind, or GENERIC.
    """
    text = " ".join(label.lower() for label in labels if label)
    for kind, keywords in routes_constants.POI_KIND_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return kind
    return routes_constants.PoiKind.GENERIC


def _clean(value: str | None, max_length: int) -> str | None:
    """
    Strip HTML and trim a free-text value from a file.

    Args:
        value: Raw text.
        max_length: Maximum length to keep.

    Returns:
        The cleaned text, or None when empty.
    """
    cleaned = core_sanitization.sanitize_plain_text(value) if value else None
    cleaned = cleaned.strip() if cleaned else None
    return cleaned[:max_length] if cleaned else None


def _add_poi(
    route: ParsedRoute,
    name: str | None,
    description: str | None,
    kind: routes_constants.PoiKind,
    point: RoutePoint | None,
) -> None:
    """
    Append a POI if its position is valid and the limit is not reached.

    Args:
        route: Route being built.
        name: POI name.
        description: POI description.
        kind: POI kind.
        point: POI position.

    Returns:
        None.
    """
    if point is None or len(route.pois) >= routes_constants.MAX_POIS:
        return
    route.pois.append(
        Poi(
            name=_clean(name, routes_constants.MAX_POI_NAME_LENGTH) or kind.value.capitalize(),
            description=_clean(description, routes_constants.MAX_POI_DESCRIPTION_LENGTH),
            kind=kind,
            lat=point[0],
            lon=point[1],
            ele=point[2],
        )
    )


def _extend(route: ParsedRoute, points: Iterable[RoutePoint | None]) -> None:
    """
    Append valid points, enforcing the raw point limit.

    Args:
        route: Route being built.
        points: Candidate points.

    Returns:
        None.

    Raises:
        RouteFileError: If the file has too many points.
    """
    for point in points:
        if point is None:
            continue
        if len(route.points) >= routes_constants.MAX_RAW_POINTS:
            raise RouteFileError("Route file has too many points")
        route.points.append(point)


def parse_gpx(data: bytes) -> ParsedRoute:
    """
    Read a GPX file: tracks first, then routes; waypoints become POIs.

    Timestamps are ignored, so untimed exports (planners, OsmAnd) work.

    Args:
        data: File contents.

    Returns:
        The parsed route.

    Raises:
        RouteFileError: If the GPX is malformed.
    """
    try:
        gpx = gpxpy.parse(data.decode("utf-8-sig", errors="replace"))
    except (gpxpy.gpx.GPXException, ValueError, ET.ParseError) as err:
        raise RouteFileError("Invalid GPX file") from err

    route = ParsedRoute(
        name=gpx.name or next((track.name for track in gpx.tracks if track.name), None),
        description=gpx.description,
    )
    for track in gpx.tracks:
        for segment in track.segments:
            _extend(route, (valid_point(p.latitude, p.longitude, p.elevation) for p in segment.points))
    if not route.points:
        for gpx_route in gpx.routes:
            route.name = route.name or gpx_route.name
            _extend(route, (valid_point(p.latitude, p.longitude, p.elevation) for p in gpx_route.points))
    for waypoint in gpx.waypoints:
        _add_poi(
            route,
            waypoint.name,
            waypoint.description or waypoint.comment,
            poi_kind(waypoint.symbol, waypoint.type, waypoint.name),
            valid_point(waypoint.latitude, waypoint.longitude, waypoint.elevation),
        )
    return route


def _fit_value(frame: fitdecode.FitDataMessage, key: str) -> object:
    """
    Read a field from a FIT message, or None when absent.

    Args:
        frame: FIT data message.
        key: Field name.

    Returns:
        The field value or None.
    """
    try:
        return frame.get_value(key)
    except KeyError:
        return None


def _fit_point(frame: fitdecode.FitDataMessage) -> RoutePoint | None:
    """
    Position of a FIT record or course point.

    Args:
        frame: FIT data message.

    Returns:
        The point, or None without a position.
    """
    lat, lon = _fit_value(frame, "position_lat"), _fit_value(frame, "position_long")
    if lat is None or lon is None:
        return None
    ele = _fit_value(frame, "enhanced_altitude")
    if ele is None:
        ele = _fit_value(frame, "altitude")
    scale = routes_constants.FIT_SEMICIRCLES_TO_DEGREES
    return valid_point(float(lat) * scale, float(lon) * scale, ele)  # type: ignore[arg-type]


def parse_fit(data: bytes) -> ParsedRoute:
    """
    Read a FIT course (or activity) file.

    ``record`` messages give the path, ``course_point`` messages the POIs
    and the ``course`` message the name.

    Args:
        data: File contents.

    Returns:
        The parsed route.

    Raises:
        RouteFileError: If the FIT file is malformed.
    """
    route = ParsedRoute()
    try:
        for frame in fitdecode.FitReader(io.BytesIO(data)):
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            if frame.name == "record":
                _extend(route, [_fit_point(frame)])
            elif frame.name == "course":
                name = _fit_value(frame, "name")
                route.name = str(name) if name else route.name
            elif frame.name == "course_point":
                kind_label = _fit_value(frame, "type")
                name = _fit_value(frame, "name")
                _add_poi(
                    route,
                    str(name) if name else None,
                    None,
                    poi_kind(str(kind_label) if kind_label else None, str(name) if name else None),
                    _fit_point(frame),
                )
    except RouteFileError:
        raise
    except Exception as err:
        raise RouteFileError("Invalid FIT file") from err
    return route


def _local(tag: str) -> str:
    """Tag name without its XML namespace."""
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    """First direct child with the given local name."""
    return next((child for child in element if _local(child.tag) == name), None)


def _child_text(element: ET.Element, name: str) -> str | None:
    """Text of the first direct child with the given local name."""
    child = _child(element, name)
    return child.text.strip() if child is not None and child.text else None


def _tcx_point(element: ET.Element) -> RoutePoint | None:
    """Position of a TCX Trackpoint or CoursePoint."""
    position = _child(element, "Position")
    if position is None:
        return None
    return valid_point(
        _child_text(position, "LatitudeDegrees"),
        _child_text(position, "LongitudeDegrees"),
        _child_text(element, "AltitudeMeters"),
    )


def parse_tcx(data: bytes) -> ParsedRoute:
    """
    Read a TCX course or activity.

    Args:
        data: File contents.

    Returns:
        The parsed route.

    Raises:
        RouteFileError: If the TCX is malformed.
    """
    try:
        root = ET.fromstring(data)  # noqa: S314 - see the import note above
    except ET.ParseError as err:
        raise RouteFileError("Invalid TCX file") from err

    route = ParsedRoute()
    for element in root.iter():
        name = _local(element.tag)
        if name == "Course" and route.name is None:
            route.name = _child_text(element, "Name")
        elif name == "Trackpoint":
            _extend(route, [_tcx_point(element)])
        elif name == "CoursePoint":
            _add_poi(
                route,
                _child_text(element, "Name"),
                _child_text(element, "Notes"),
                poi_kind(_child_text(element, "PointType"), _child_text(element, "Name")),
                _tcx_point(element),
            )
    return route


def parse_route_file(data: bytes, extension: str) -> ParsedRoute:
    """
    Parse a route file by extension.

    Args:
        data: File contents.
        extension: Lowercase extension without the dot.

    Returns:
        The parsed route.

    Raises:
        RouteFileError: For unsupported types, unreadable files, or files
            with fewer than two usable points.
    """
    parsers = {"gpx": parse_gpx, "fit": parse_fit, "tcx": parse_tcx}
    parser = parsers.get(extension)
    if parser is None:
        raise RouteFileError("Unsupported route file type")
    route = parser(data)
    if len(route.points) < 2:
        raise RouteFileError("Route file contains no usable path")
    return route
