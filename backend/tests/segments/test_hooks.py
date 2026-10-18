"""Tests for the activity-side hooks that feed segment matching."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import activities.activity.crud as activity_crud
import activities.activity.schema as activity_schema
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.crud as activity_streams_crud
import activities.activity_streams.models as activity_streams_models
import activities.activity_streams.schema as activity_streams_schema
import activities.activity_streams.utils as activity_streams_utils
import core.geo as core_geo
import migrations.migration_8 as migration_8
import migrations.models as migrations_models
import segments.matching.models as matching_models
from tests.segments.conftest import add_activity


def _queued_activities(db):
    return [item.activity_id for item in db.scalars(select(matching_models.SegmentMatchQueue))]


def _clear_bbox(db, activity):
    activity_crud.set_activity_bounding_box(activity.id, None, db)
    db.refresh(activity)


@pytest.mark.parametrize(
    ("waypoints", "expected"),
    [
        (None, None),
        ([], None),
        ([{"lat": None, "lon": 1.0}, "garbage"], None),
        ([{"lat": 1.0, "lon": 3.0}, {"lat": 2.0, "lon": 1.0}], core_geo.BoundingBox(1.0, 1.0, 2.0, 3.0)),
    ],
)
def test_bounding_box_from_waypoints(waypoints, expected):
    """Only waypoints with coordinates count."""
    assert activity_streams_utils.bounding_box_from_lat_lon_waypoints(waypoints) == expected


class TestCreateActivityStreams:
    @patch("activities.activity_streams.crud.users_crud.get_user_by_id", return_value=MagicMock(max_heart_rate=200))
    async def test_map_stream_sets_bbox_and_queues_matching(self, _user, sqlite_db):
        activity = add_activity(sqlite_db)
        _clear_bbox(sqlite_db, activity)
        stream = activity_streams_schema.ActivityStreamsCreate(
            activity_id=activity.id,
            stream_type=activity_streams_constants.STREAM_TYPE_MAP,
            stream_waypoints=[
                {"time": "2024-01-01T00:00:00", "lat": 1.0, "lon": 2.0},
                {"time": "2024-01-01T00:00:01", "lat": 1.5, "lon": 2.5},
            ],
            strava_activity_stream_id=None,
        )

        await activity_streams_crud.create_activity_streams([stream], activity, sqlite_db)

        sqlite_db.refresh(activity)
        assert (activity.bbox_min_lat, activity.bbox_max_lon) == (1.0, 2.5)
        assert _queued_activities(sqlite_db) == [activity.id]

    @patch("activities.activity_streams.crud.users_crud.get_user_by_id", return_value=MagicMock(max_heart_rate=200))
    async def test_without_map_stream_nothing_is_queued(self, _user, sqlite_db):
        activity = add_activity(sqlite_db)
        stream = activity_streams_schema.ActivityStreamsCreate(
            activity_id=activity.id,
            stream_type=activity_streams_constants.STREAM_TYPE_CADENCE,
            stream_waypoints=[{"time": "2024-01-01T00:00:00", "cad": 80}],
            strava_activity_stream_id=None,
        )

        await activity_streams_crud.create_activity_streams([stream], activity, sqlite_db)

        assert _queued_activities(sqlite_db) == []


class TestEditActivityRequeues:
    def _edit(self, activity, **changes):
        return activity_schema.ActivityEdit(
            id=activity.id,
            name=changes.pop("name", activity.name),
            activity_type=changes.pop("activity_type", activity.activity_type),
            **changes,
        )

    def test_type_change_requeues(self, sqlite_db):
        activity = add_activity(sqlite_db)
        activity_crud.edit_activity(1, self._edit(activity, activity_type=4), sqlite_db)
        assert _queued_activities(sqlite_db) == [activity.id]

    def test_unhide_requeues(self, sqlite_db):
        activity = add_activity(sqlite_db, is_hidden=True)
        activity_crud.edit_activity(1, self._edit(activity, is_hidden=False), sqlite_db)
        assert _queued_activities(sqlite_db) == [activity.id]

    def test_other_edits_do_not_requeue(self, sqlite_db):
        activity = add_activity(sqlite_db)
        activity_crud.edit_activity(1, self._edit(activity, name="Renamed"), sqlite_db)
        assert _queued_activities(sqlite_db) == []

    def test_activity_without_gps_is_not_queued(self, sqlite_db):
        activity = add_activity(sqlite_db)
        _clear_bbox(sqlite_db, activity)
        activity_crud.edit_activity(1, self._edit(activity, activity_type=4), sqlite_db)
        assert _queued_activities(sqlite_db) == []


def test_set_bounding_box_db_error(mock_db):
    """Database errors roll back and surface as 500."""
    mock_db.execute.side_effect = SQLAlchemyError("boom")
    with pytest.raises(HTTPException) as err:
        activity_crud.set_activity_bounding_box(1, core_geo.BoundingBox(0, 0, 1, 1), mock_db)
    assert err.value.status_code == 500
    mock_db.rollback.assert_called_once()


class TestMigration8:
    def _register(self, db):
        db.add(migrations_models.Migration(id=8, name="v0.20.0", description="bbox backfill", executed=False))
        db.commit()

    def test_backfills_bounding_boxes(self, sqlite_db, monkeypatch):
        self._register(sqlite_db)
        first = add_activity(sqlite_db)
        second = add_activity(sqlite_db)
        empty = add_activity(sqlite_db)
        for activity in (first, second, empty):
            _clear_bbox(sqlite_db, activity)
        map_stream = sqlite_db.scalar(
            select(activity_streams_models.ActivityStreams).where(
                activity_streams_models.ActivityStreams.activity_id == empty.id,
                activity_streams_models.ActivityStreams.stream_type == activity_streams_constants.STREAM_TYPE_MAP,
            )
        )
        map_stream.stream_waypoints = [{"time": "x", "lat": None, "lon": None}]
        sqlite_db.commit()

        original = activity_streams_crud.get_map_streams_without_activity_bounding_box
        monkeypatch.setattr(
            activity_streams_crud,
            "get_map_streams_without_activity_bounding_box",
            lambda db, after_id: original(db, after_id=after_id, batch_size=1),
        )

        migration_8.process_migration_8(sqlite_db)

        for activity in (first, second, empty):
            sqlite_db.refresh(activity)
        assert first.bbox_min_lat is not None and second.bbox_min_lat is not None
        assert empty.bbox_min_lat is None
        assert sqlite_db.get(migrations_models.Migration, 8).executed is True

    def test_errors_leave_migration_pending(self, sqlite_db):
        self._register(sqlite_db)
        with patch(
            "migrations.migration_8.activity_streams_crud.get_map_streams_without_activity_bounding_box",
            side_effect=RuntimeError("boom"),
        ):
            migration_8.process_migration_8(sqlite_db)
        assert sqlite_db.get(migrations_models.Migration, 8).executed is False

    def test_mark_executed_failure_is_logged(self, sqlite_db):
        with patch("migrations.migration_8.core_logger.print_to_log_and_console") as log:
            migration_8.process_migration_8(sqlite_db)
        assert any("Failed to set migration" in call.args[0] for call in log.call_args_list)
