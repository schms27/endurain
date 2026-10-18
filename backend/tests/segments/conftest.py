"""Shared fixtures for segment tests: an SQLite session and data builders."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

import activities.activity.models as activity_models
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.models as activity_streams_models
import activities.activity_streams.utils as activity_streams_utils
import segments.constants as segments_constants
import segments.segment.models as segment_models
from tests._helpers import tracks
from tests._helpers.db import create_sqlite_session

# 2024-01-01T08:00:00Z
BASE_TIME = 1_704_096_000.0

# A 1 km eastbound path well past both segment gates, and the segment slice
# indices covering x = 0..1000 m when recorded at 5 m/s, 1 Hz.
THROUGH_PATH = [(-200.0, 0.0), (1200.0, 0.0)]
SLICE = (40, 240)


@pytest.fixture
def sqlite_db():
    """A real in-memory SQLite session with every table created."""
    session = create_sqlite_session()
    try:
        yield session
    finally:
        session.close()
        session.bind.dispose()


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%S")


def add_activity(
    db,
    *,
    user_id: int = 1,
    activity_type: int = 1,
    path=THROUGH_PATH,
    speed_mps: float = 5.0,
    start_time: float = BASE_TIME,
    hr: int | None = 150,
    elevation: bool = True,
    **overrides,
) -> activity_models.Activity:
    """
    Insert an activity with map, HR and elevation streams and a bounding box.

    Args:
        db: Database session.
        user_id: Owner user ID.
        activity_type: Activity type code.
        path: Path vertices in local metres.
        speed_mps: Constant speed.
        start_time: Unix time of the first point.
        hr: Constant heart rate, or None for no HR stream.
        elevation: Whether to add a rising elevation stream.
        **overrides: Extra Activity column values.

    Returns:
        The activity ORM instance.
    """
    lats, lons, times = tracks.track(path, speed_mps=speed_mps, start_time=start_time)
    map_waypoints = [
        {"time": _iso(t), "lat": float(lat), "lon": float(lon)} for lat, lon, t in zip(lats, lons, times, strict=True)
    ]
    fields = {
        "user_id": user_id,
        "name": "Run",
        "distance": 1400,
        "activity_type": activity_type,
        "start_time": datetime.fromtimestamp(start_time, UTC),
        "end_time": datetime.fromtimestamp(float(times[-1]), UTC),
        "created_at": datetime.fromtimestamp(start_time, UTC),
        "total_elapsed_time": Decimal(str(times[-1] - times[0])),
        "total_timer_time": Decimal(str(times[-1] - times[0])),
        "visibility": 0,
        "is_hidden": False,
        "hide_start_time": False,
        "hide_location": False,
        "hide_map": False,
        "hide_hr": False,
        "hide_power": False,
        "hide_cadence": False,
        "hide_elevation": False,
        "hide_speed": False,
        "hide_pace": False,
        "hide_laps": False,
        "hide_workout_sets_steps": False,
        "hide_gear": False,
        "city": "Lisbon",
        "country": "Portugal",
    }
    fields.update(overrides)
    bbox = activity_streams_utils.bounding_box_from_lat_lon_waypoints(map_waypoints)
    activity = activity_models.Activity(
        **fields,
        bbox_min_lat=bbox.min_lat,
        bbox_min_lon=bbox.min_lon,
        bbox_max_lat=bbox.max_lat,
        bbox_max_lon=bbox.max_lon,
    )
    db.add(activity)
    db.flush()

    streams = [(activity_streams_constants.STREAM_TYPE_MAP, map_waypoints)]
    if hr is not None:
        streams.append(
            (activity_streams_constants.STREAM_TYPE_HR, [{"time": wp["time"], "hr": hr} for wp in map_waypoints])
        )
    if elevation:
        streams.append(
            (
                activity_streams_constants.STREAM_TYPE_ELEVATION,
                [{"time": wp["time"], "ele": 10.0 + index * 0.25} for index, wp in enumerate(map_waypoints)],
            )
        )
    for stream_type, waypoints in streams:
        db.add(
            activity_streams_models.ActivityStreams(
                activity_id=activity.id,
                stream_type=stream_type,
                stream_waypoints=waypoints,
            )
        )
    db.commit()
    return activity


def add_segment(
    db,
    *,
    user_id: int | None = 1,
    vertices=((0.0, 0.0), (1000.0, 0.0)),
    sport_group: segments_constants.SportGroup = segments_constants.SportGroup.RUN,
    visibility: int = segments_constants.SEGMENT_VISIBILITY_PUBLIC,
    **overrides,
) -> segment_models.Segment:
    """
    Insert a segment directly (bypassing creation from an activity).

    Args:
        db: Database session.
        user_id: Creator user ID.
        vertices: Segment vertices in local metres.
        sport_group: Sport group.
        visibility: Visibility code.
        **overrides: Extra Segment column values.

    Returns:
        The segment ORM instance.
    """
    lats, lons = tracks.segment(list(vertices))
    fields = {
        "user_id": user_id,
        "name": "River path",
        "sport_group": sport_group.value,
        "visibility": visibility,
        "geometry": [[float(lat), float(lon), None] for lat, lon in zip(lats, lons, strict=True)],
        "distance": 1000.0,
        "start_lat": float(lats[0]),
        "start_lon": float(lons[0]),
        "end_lat": float(lats[-1]),
        "end_lon": float(lons[-1]),
        "bbox_min_lat": float(lats.min()),
        "bbox_min_lon": float(lons.min()),
        "bbox_max_lat": float(lats.max()),
        "bbox_max_lon": float(lons.max()),
        "is_archived": False,
        "matcher_version": segments_constants.MATCHER_VERSION,
        "effort_count": 0,
        "athlete_count": 0,
    }
    fields.update(overrides)
    segment = segment_models.Segment(**fields)
    db.add(segment)
    db.commit()
    return segment
