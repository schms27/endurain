"""Export routes to device-friendly file formats."""

import gpxpy.gpx

import routes.route.models as route_models

_CREATOR = "Endurain"


def to_gpx(route: route_models.Route) -> str:
    """
    Render a route as GPX 1.1.

    The path is written as a track, which bike computers and watches import
    most reliably; points of interest become waypoints.

    Args:
        route: The route ORM instance.

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

    for poi in route.waypoints or []:
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(
                poi["lat"],
                poi["lon"],
                elevation=poi.get("ele"),
                name=poi.get("name"),
                description=poi.get("description"),
                symbol=poi.get("kind"),
                type=poi.get("kind"),
            )
        )
    return gpx.to_xml(version="1.1")
