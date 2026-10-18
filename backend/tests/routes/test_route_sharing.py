"""Tests for route sharing: visibility, trimming, share links, copies."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import activities.activity.models as activity_models
import activities.activity_streams.constants as activity_streams_constants
import activities.activity_streams.models as activity_streams_models
import core.geo as core_geo
import followers.models as followers_models
import routes.constants as routes_constants
import routes.route.crud as route_crud
import routes.route.schema as route_schema
import routes.route.utils as route_utils
from tests._helpers.db import create_sqlite_session
from tests.routes.test_route_utils import _points

OWNER, FOLLOWER, PENDING, STRANGER = 1, 2, 3, 4
PUBLIC, FOLLOWERS, PRIVATE = (
    routes_constants.RouteVisibility.PUBLIC,
    routes_constants.RouteVisibility.FOLLOWERS,
    routes_constants.RouteVisibility.PRIVATE,
)
# A 1 km straight line east.
LINE = _points([(0.0, 0.0), (500.0, 0.0), (1000.0, 0.0)], ele_step=10)
SETTINGS = "routes.route.crud.server_settings_utils.get_server_settings_or_404"


def _settings(links=True, user_info=False):
    return SimpleNamespace(public_shareable_links=links, public_shareable_links_user_info=user_info)


@pytest.fixture
def sqlite_db():
    session = create_sqlite_session()
    session.add_all(
        [
            followers_models.Follower(follower_id=FOLLOWER, following_id=OWNER, is_accepted=True),
            followers_models.Follower(follower_id=PENDING, following_id=OWNER, is_accepted=False),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        session.bind.dispose()


def _add_route(db, *, user_id=OWNER, visibility=PRIVATE, hide=0, pois=None):
    route = route_crud._store(
        user_id,
        route_utils.build_route_geometry(LINE),
        db,
        name="Castle loop",
        description="Climb",
        activity_type=1,
        source=routes_constants.RouteSource.IMPORT.value,
        source_activity_id=None,
        original_filename="castle.gpx",
        waypoints=pois or [],
    )
    return route_crud.edit_route(
        route.id, user_id, route_schema.RouteEdit(visibility=visibility, hide_endpoints_m=hide), db
    )


def _poi(name, point):
    return {"name": name, "description": None, "kind": "water", "lat": point[0], "lon": point[1], "ele": None}


def _visible(route_id, user_id, db):
    try:
        return route_crud.get_route(route_id, user_id, db)
    except HTTPException as err:
        assert err.status_code == 404
        return None


class TestVisibility:
    @pytest.mark.parametrize(
        ("visibility", "viewers"),
        [
            (PUBLIC, {OWNER, FOLLOWER, PENDING, STRANGER}),
            (FOLLOWERS, {OWNER, FOLLOWER}),
            (PRIVATE, {OWNER}),
        ],
    )
    def test_access_matrix(self, sqlite_db, visibility, viewers):
        route = _add_route(sqlite_db, visibility=visibility)
        for viewer in (OWNER, FOLLOWER, PENDING, STRANGER):
            assert (_visible(route.id, viewer, sqlite_db) is not None) == (viewer in viewers)

    def test_non_owner_view_hides_owner_fields(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC)
        route_crud.create_share_token(route.id, OWNER, sqlite_db)

        own = route_crud.get_route(route.id, OWNER, sqlite_db)
        assert own.is_owner is True
        assert own.share_token is not None
        assert own.original_filename == "castle.gpx"

        other = route_crud.get_route(route.id, STRANGER, sqlite_db)
        assert other.is_owner is False
        assert (other.share_token, other.original_filename, other.source_activity_id) == (None, None, None)

    def test_owner_only_mutations(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC)
        for action in (
            lambda: route_crud.edit_route(route.id, STRANGER, route_schema.RouteEdit(name="x"), sqlite_db),
            lambda: route_crud.create_share_token(route.id, STRANGER, sqlite_db),
            lambda: route_crud.revoke_share_token(route.id, STRANGER, sqlite_db),
            lambda: route_crud.home_location_warning(route.id, STRANGER, sqlite_db),
        ):
            with pytest.raises(HTTPException) as err:
                action()
            assert err.value.status_code == 404

    def test_profile_list(self, sqlite_db):
        for visibility in (PUBLIC, FOLLOWERS, PRIVATE):
            _add_route(sqlite_db, visibility=visibility, hide=200)
        _add_route(sqlite_db, user_id=STRANGER, visibility=PUBLIC)

        assert route_crud.list_user_routes(OWNER, OWNER, sqlite_db).total == 3
        assert route_crud.list_user_routes(OWNER, FOLLOWER, sqlite_db).total == 2
        page = route_crud.list_user_routes(OWNER, STRANGER, sqlite_db)
        assert page.total == 1
        assert page.records[0].distance == pytest.approx(600.0, rel=0.02)
        assert route_crud.list_user_routes(OWNER, OWNER, sqlite_db).records[0].distance == pytest.approx(1000, rel=0.01)


class TestTrimming:
    def test_non_owner_sees_trimmed_route(self, sqlite_db):
        pois = [_poi("Home tap", LINE[0]), _poi("Fountain", LINE[1]), _poi("Gate", LINE[2])]
        route = _add_route(sqlite_db, visibility=PUBLIC, hide=200, pois=pois)

        own = route_crud.get_route(route.id, OWNER, sqlite_db)
        assert own.distance == pytest.approx(1000.0, rel=0.01)
        assert len(own.waypoints) == 3

        other = route_crud.get_route(route.id, STRANGER, sqlite_db)
        assert other.distance == pytest.approx(600.0, rel=0.01)
        assert [poi.name for poi in other.waypoints] == ["Fountain"]
        start_gap = core_geo.haversine_m(LINE[0][0], LINE[0][1], other.geometry[0][0], other.geometry[0][1])
        assert float(start_gap) == pytest.approx(200.0, rel=0.01)
        assert other.elevation_min is not None and other.elevation_min > 100

    def test_fully_hidden_route(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC, hide=600)
        other = route_crud.get_route(route.id, STRANGER, sqlite_db)
        assert (other.geometry, other.distance, other.elevation_gain) == ([], 0.0, None)
        with pytest.raises(HTTPException) as err:
            route_crud.copy_route(
                route_crud.get_visible_route_model(route.id, STRANGER, sqlite_db), STRANGER, sqlite_db
            )
        assert err.value.status_code == 400


class TestShareLinks:
    def test_create_rotate_revoke(self, sqlite_db):
        route = _add_route(sqlite_db)
        first = route_crud.create_share_token(route.id, OWNER, sqlite_db).share_token
        assert first is not None and len(first) == routes_constants.SHARE_TOKEN_LENGTH
        second = route_crud.create_share_token(route.id, OWNER, sqlite_db).share_token
        assert second != first

        with patch(SETTINGS, return_value=_settings()):
            # A private route is reachable through its link only.
            assert route_crud.get_shared_route_model(second, sqlite_db).id == route.id
            with pytest.raises(HTTPException):
                route_crud.get_shared_route_model(first, sqlite_db)

        assert route_crud.revoke_share_token(route.id, OWNER, sqlite_db).share_token is None
        with patch(SETTINGS, return_value=_settings()), pytest.raises(HTTPException) as err:
            route_crud.get_shared_route_model(second, sqlite_db)
        assert err.value.status_code == 404

    def test_links_need_public_sharing_enabled(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC)
        token = route_crud.create_share_token(route.id, OWNER, sqlite_db).share_token
        with patch(SETTINGS, return_value=_settings(links=False)):
            for action in (
                lambda: route_crud.get_shared_route_model(token, sqlite_db),
                lambda: route_crud.get_public_route_model(route.id, sqlite_db),
            ):
                with pytest.raises(HTTPException) as err:
                    action()
                assert err.value.status_code == 404

    @pytest.mark.parametrize(("visibility", "found"), [(PUBLIC, True), (FOLLOWERS, False), (PRIVATE, False)])
    def test_public_route_by_id(self, sqlite_db, visibility, found):
        route = _add_route(sqlite_db, visibility=visibility)
        with patch(SETTINGS, return_value=_settings()):
            if found:
                assert route_crud.get_public_route_model(route.id, sqlite_db).id == route.id
            else:
                with pytest.raises(HTTPException):
                    route_crud.get_public_route_model(route.id, sqlite_db)

    @pytest.mark.parametrize("user_info", [True, False])
    def test_public_view_creator(self, sqlite_db, monkeypatch, user_info):
        route = _add_route(sqlite_db, visibility=PUBLIC, hide=200)
        token = route_crud.create_share_token(route.id, OWNER, sqlite_db).share_token
        monkeypatch.setattr(
            sqlite_db, "get", lambda _model, user_id: SimpleNamespace(id=user_id, name="Ana", username="ana")
        )
        with patch(SETTINGS, return_value=_settings(user_info=user_info)):
            view = route_crud.present_public_route(route_crud.get_shared_route_model(token, sqlite_db), sqlite_db)
        assert view.share_token is None
        assert view.distance == pytest.approx(600.0, rel=0.01)
        assert (view.owner is not None) == user_info
        if user_info:
            assert view.owner == route_schema.RouteOwner(id=OWNER, name="Ana", username="ana")


class TestCopy:
    def test_copy_is_private_trimmed_and_attributed(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC, hide=200, pois=[_poi("Fountain", LINE[1])])
        source = route_crud.get_visible_route_model(route.id, STRANGER, sqlite_db)
        copy = route_crud.copy_route(source, STRANGER, sqlite_db)
        assert copy.user_id == STRANGER
        assert copy.is_owner is True
        assert copy.visibility == PRIVATE
        assert copy.source == routes_constants.RouteSource.COPY
        assert copy.source_route_id == route.id
        assert copy.distance == pytest.approx(600.0, rel=0.01)
        assert [poi.name for poi in copy.waypoints] == ["Fountain"]
        assert copy.share_token is None and copy.hide_endpoints_m == 0

    def test_owner_copy_keeps_full_route(self, sqlite_db):
        route = _add_route(sqlite_db, hide=200)
        copy = route_crud.copy_route(route_crud.get_visible_route_model(route.id, OWNER, sqlite_db), OWNER, sqlite_db)
        assert copy.distance == pytest.approx(1000.0, rel=0.01)

    def test_copy_survives_source_deletion(self, sqlite_db):
        route = _add_route(sqlite_db, visibility=PUBLIC)
        copy = route_crud.copy_route(
            route_crud.get_visible_route_model(route.id, STRANGER, sqlite_db), STRANGER, sqlite_db
        )
        route_crud.delete_route(route.id, OWNER, sqlite_db)
        assert route_crud.get_route(copy.id, STRANGER, sqlite_db).name == "Castle loop"


def _add_activity_starting_at(db, point, user_id=OWNER):
    activity = activity_models.Activity(
        user_id=user_id,
        name="Run",
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
        bbox_min_lat=point[0] - 0.01,
        bbox_min_lon=point[1] - 0.01,
        bbox_max_lat=point[0] + 0.01,
        bbox_max_lon=point[1] + 0.01,
    )
    db.add(activity)
    db.flush()
    db.add(
        activity_streams_models.ActivityStreams(
            activity_id=activity.id,
            stream_type=activity_streams_constants.STREAM_TYPE_MAP,
            stream_waypoints=[
                {"time": "2024-01-01T00:00:00", "lat": point[0], "lon": point[1]},
                {"time": "2024-01-01T00:00:01", "lat": point[0] + 0.005, "lon": point[1]},
            ],
        )
    )
    db.commit()


class TestHomeWarning:
    def test_flags_frequent_start(self, sqlite_db):
        route = _add_route(sqlite_db)
        for _ in range(routes_constants.HOME_MIN_ACTIVITIES):
            _add_activity_starting_at(sqlite_db, LINE[0])
        # Someone else's activities never count.
        for _ in range(routes_constants.HOME_MIN_ACTIVITIES):
            _add_activity_starting_at(sqlite_db, LINE[-1], user_id=STRANGER)

        warning = route_crud.home_location_warning(route.id, OWNER, sqlite_db)
        assert (warning.start_near_home, warning.end_near_home) == (True, False)

        route_crud.edit_route(route.id, OWNER, route_schema.RouteEdit(hide_endpoints_m=300), sqlite_db)
        warning = route_crud.home_location_warning(route.id, OWNER, sqlite_db)
        assert (warning.start_near_home, warning.end_near_home) == (False, False)

    def test_needs_several_activities(self, sqlite_db):
        route = _add_route(sqlite_db)
        for _ in range(routes_constants.HOME_MIN_ACTIVITIES - 1):
            _add_activity_starting_at(sqlite_db, LINE[0])
        assert route_crud.home_location_warning(route.id, OWNER, sqlite_db).start_near_home is False

    def test_fully_hidden_route_has_no_warning(self, sqlite_db):
        route = _add_route(sqlite_db, hide=600)
        for _ in range(routes_constants.HOME_MIN_ACTIVITIES):
            _add_activity_starting_at(sqlite_db, LINE[0])
        warning = route_crud.home_location_warning(route.id, OWNER, sqlite_db)
        assert (warning.start_near_home, warning.end_near_home) == (False, False)
