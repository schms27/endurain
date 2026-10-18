"""Tests for route CRUD on SQLite."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

import activities.activity.models as activity_models
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.models as activity_streams_models
import routes.constants as routes_constants
import routes.route.crud as route_crud
import routes.route.schema as route_schema
from tests._helpers.db import create_sqlite_session
from tests.routes.test_parsers import GPX_ROUTE_ONLY, GPX_TRACK


@pytest.fixture
def sqlite_db():
    session = create_sqlite_session()
    try:
        yield session
    finally:
        session.close()
        session.bind.dispose()


def _add_activity(db, *, user_id=1, points=60, with_map=True):
    activity = activity_models.Activity(
        user_id=user_id,
        name="Morning run",
        distance=1000,
        activity_type=1,
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=datetime(2024, 1, 1, 1, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        total_elapsed_time=Decimal(3600),
        total_timer_time=Decimal(3600),
        visibility=0,
        is_hidden=False,
        hide_start_time=False,
        hide_map=False,
        hide_power=False,
        hide_cadence=False,
        hide_elevation=False,
        hide_speed=False,
        hide_pace=False,
        hide_laps=False,
        hide_workout_sets_steps=False,
        hide_gear=False,
        city="Lisbon",
        country="Portugal",
    )
    db.add(activity)
    db.flush()
    times = [f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}" for i in range(points)]
    if with_map:
        db.add(
            activity_streams_models.ActivityStreams(
                activity_id=activity.id,
                stream_type=activity_streams_constants.STREAM_TYPE_MAP,
                stream_waypoints=[{"time": t, "lat": 38.7 + i * 0.0001, "lon": -9.1} for i, t in enumerate(times)],
            )
        )
        db.add(
            activity_streams_models.ActivityStreams(
                activity_id=activity.id,
                stream_type=activity_streams_constants.STREAM_TYPE_ELEVATION,
                stream_waypoints=[{"time": t, "ele": 10.0 + i} for i, t in enumerate(times[::2])],
            )
        )
    db.commit()
    return activity


class TestImport:
    def test_gpx_import(self, sqlite_db):
        route = route_crud.import_route(1, GPX_TRACK, "castle.gpx", "gpx", sqlite_db)
        assert route.name == "Castle loop"
        assert route.description == "Nice climb"
        assert route.source == routes_constants.RouteSource.IMPORT
        assert route.original_filename == "castle.gpx"
        assert len(route.waypoints) == 3
        assert route.distance > 0

    def test_default_name_from_filename(self, sqlite_db):
        route = route_crud.import_route(
            1, GPX_ROUTE_ONLY.replace(b"<name>Planned</name>", b""), "my_tour.gpx", "gpx", sqlite_db
        )
        assert route.name == "my tour"

    def test_invalid_file_is_400(self, sqlite_db):
        with pytest.raises(HTTPException) as err:
            route_crud.import_route(1, b"<gpx>", "x.gpx", "gpx", sqlite_db)
        assert err.value.status_code == 400


class TestFromActivity:
    def test_whole_activity(self, sqlite_db):
        activity = _add_activity(sqlite_db)
        route = route_crud.create_route_from_activity(1, activity.id, route_schema.RouteFromActivity(), sqlite_db)
        assert route.name == "Morning run"
        assert route.source == routes_constants.RouteSource.ACTIVITY
        assert route.source_activity_id == activity.id
        assert route.activity_type == 1
        assert route.city == "Lisbon"
        assert route.geometry[0][2] == 10.0
        # Points without a matching elevation sample keep a null elevation.
        assert route.distance == pytest.approx(59 * 11.12, rel=0.02)

    def test_slice_and_name(self, sqlite_db):
        activity = _add_activity(sqlite_db)
        request = route_schema.RouteFromActivity(name="Hill <b>bit</b>", start_index=10, end_index=20)
        route = route_crud.create_route_from_activity(1, activity.id, request, sqlite_db)
        assert route.name == "Hill bit"
        assert route.distance == pytest.approx(10 * 11.12, rel=0.02)

    @pytest.mark.parametrize(
        ("kwargs", "status"),
        [
            ({"user_id": 2}, 404),
            ({"with_map": False}, 400),
        ],
    )
    def test_activity_errors(self, sqlite_db, kwargs, status):
        activity = _add_activity(sqlite_db, **kwargs)
        with pytest.raises(HTTPException) as err:
            route_crud.create_route_from_activity(1, activity.id, route_schema.RouteFromActivity(), sqlite_db)
        assert err.value.status_code == status

    def test_slice_out_of_range(self, sqlite_db):
        activity = _add_activity(sqlite_db)
        with pytest.raises(HTTPException) as err:
            route_crud.create_route_from_activity(
                1, activity.id, route_schema.RouteFromActivity(start_index=0, end_index=500), sqlite_db
            )
        assert err.value.status_code == 400

    def test_degenerate_slice(self, sqlite_db):
        activity = _add_activity(sqlite_db, points=2)
        sqlite_db.query(activity_streams_models.ActivityStreams).filter_by(
            stream_type=activity_streams_constants.STREAM_TYPE_MAP
        ).update({"stream_waypoints": [{"time": "a", "lat": 1.0, "lon": 1.0}, {"time": "b", "lat": 1.0, "lon": 1.0}]})
        sqlite_db.commit()
        with pytest.raises(HTTPException) as err:
            route_crud.create_route_from_activity(1, activity.id, route_schema.RouteFromActivity(), sqlite_db)
        assert err.value.status_code == 400


class TestLibrary:
    def test_list_filters_and_paginates(self, sqlite_db):
        first = route_crud.import_route(1, GPX_TRACK, "a.gpx", "gpx", sqlite_db)
        planned = route_crud.import_route(1, GPX_ROUTE_ONLY, "b.gpx", "gpx", sqlite_db)
        route_crud.import_route(2, GPX_TRACK, "c.gpx", "gpx", sqlite_db)
        route_crud.edit_route(planned.id, 1, route_schema.RouteEdit(activity_type=4), sqlite_db)

        page = route_crud.list_routes(1, sqlite_db)
        assert page.total == 2
        assert {route.id for route in page.records} == {first.id, planned.id}
        assert [r.id for r in route_crud.list_routes(1, sqlite_db, query="castle").records] == [first.id]
        assert route_crud.list_routes(1, sqlite_db, query="50%").total == 0
        assert [r.id for r in route_crud.list_routes(1, sqlite_db, activity_type=4).records] == [planned.id]
        second_page = route_crud.list_routes(1, sqlite_db, page_number=2, num_records=1)
        assert (second_page.total, len(second_page.records)) == (2, 1)

    def test_owner_only_access(self, sqlite_db):
        route = route_crud.import_route(1, GPX_TRACK, "a.gpx", "gpx", sqlite_db)
        assert route_crud.get_route(route.id, 1, sqlite_db).id == route.id
        for action in (
            lambda: route_crud.get_route(route.id, 2, sqlite_db),
            lambda: route_crud.edit_route(route.id, 2, route_schema.RouteEdit(name="x"), sqlite_db),
            lambda: route_crud.delete_route(route.id, 2, sqlite_db),
        ):
            with pytest.raises(HTTPException) as err:
                action()
            assert err.value.status_code == 404

    def test_edit_and_delete(self, sqlite_db):
        route = route_crud.import_route(1, GPX_TRACK, "a.gpx", "gpx", sqlite_db)
        edited = route_crud.edit_route(
            route.id, 1, route_schema.RouteEdit(name="<i>New</i>", description=None, activity_type=None), sqlite_db
        )
        assert (edited.name, edited.description, edited.activity_type) == ("New", None, None)
        edited = route_crud.edit_route(route.id, 1, route_schema.RouteEdit(description="**Hi**"), sqlite_db)
        assert edited.description == "**Hi**"

        route_crud.delete_route(route.id, 1, sqlite_db)
        assert route_crud.list_routes(1, sqlite_db).total == 0
