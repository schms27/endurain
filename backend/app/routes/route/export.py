"""Export routes to device-friendly file formats."""

import gpxpy.gpx
from fastapi import Response

import routes.route.schema as route_schema
import routes.route.utils as route_utils

_CREATOR = "Endurain"


def to_gpx(route: route_schema.RouteRead) -> str:
    """
    Render a route as GPX 1.1.

    The path is written as a track, which bike computers and watches import
    most reliably; points of interest become waypoints.

    Args:
        route: The route as the requester may see it (trimmed for
            non-owners).

    Returns:
        The GPX document as a string.
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = _CREATOR
    gpx.name = route.name
    gpx.description = route.description

    track = gpxpy.gpx.GPXTrack(name=route.name, description=route.description)
    segment = gpxpy.gpx.GPXTrackSegment()
    for lat, lon, ele in route.geometry:
        segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon, elevation=ele))
    track.segments.append(segment)
    gpx.tracks.append(track)

    for poi in route.waypoints:
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(
                poi.lat,
                poi.lon,
                elevation=poi.ele,
                name=poi.name,
                description=poi.description,
                symbol=poi.kind.value,
                type=poi.kind.value,
            )
        )
    return gpx.to_xml(version="1.1")


def gpx_response(route: route_schema.RouteRead) -> Response:
    """
    Serve a route as a GPX attachment.

    Args:
        route: The route as the requester may see it.

    Returns:
        The GPX download response.
    """
    filename = route_utils.export_filename(route.name, "gpx")
    return Response(
        content=to_gpx(route),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
