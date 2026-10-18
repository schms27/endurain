"""Tests for segment records: leaderboards, PR deltas, duplicates and creation policy."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

import followers.models as followers_models
import segments.constants as segments_constants
import segments.segment.crud as segment_crud
import segments.segment.schema as segment_schema
import segments.segment_efforts.crud as segment_efforts_crud
import segments.segment_efforts.models as segment_efforts_models
import server_settings.models as server_settings_models
import users.users.models as users_models
import users.users_privacy_settings.models as users_privacy_settings_models
from tests.segments.conftest import SLICE, add_activity, add_segment

NOW = datetime(2024, 6, 1, tzinfo=UTC)
Scope = segment_efforts_crud.LeaderboardScope
Period = segment_efforts_crud.LeaderboardPeriod


def _user(db, user_id: int, *, access_type: str = "regular", opt_out: bool | None = None) -> None:
    db.add(
        users_models.Users(
            id=user_id,
            name=f"User {user_id}",
            username=f"user{user_id}",
            email=f"user{user_id}@example.com",
            preferred_language="en",
            access_type=access_type,
        )
    )
    if opt_out is not None:
        db.add(
            users_privacy_settings_models.UsersPrivacySettings(
                user_id=user_id,
                hide_from_segment_leaderboards=opt_out,
            )
        )
    db.commit()


def _effort(db, segment, activity, elapsed: float, *, day: int = 1, start_index: int = 0, **overrides):
    fields = {
        "segment_id": segment.id,
        "activity_id": activity.id,
        "user_id": activity.user_id,
        "start_time": datetime(2024, 5, day, tzinfo=UTC),
        "elapsed_time": Decimal(str(elapsed)),
        "distance": 1000.0,
        "start_index": start_index,
        "end_index": start_index + 10,
        "average_hr": 150,
        "average_power": 200,
        "average_speed": 4.0,
        "is_excluded": False,
    }
    fields.update(overrides)
    effort = segment_efforts_models.SegmentEffort(**fields)
    db.add(effort)
    db.commit()
    return effort


def _board(db, viewer_id: int = 1, **kwargs):
    return segment_efforts_crud.get_segment_leaderboard(1, viewer_id, db, now=NOW, **kwargs)


@pytest.fixture
def three_users(sqlite_db):
    for user_id in (1, 2, 3):
        _user(sqlite_db, user_id)
    return add_segment(sqlite_db)


class TestLeaderboard:
    def test_ranks_best_effort_per_athlete(self, sqlite_db, three_users):
        segment = three_users
        mine = add_activity(sqlite_db, user_id=1)
        _effort(sqlite_db, segment, mine, 300)
        _effort(sqlite_db, segment, mine, 250, start_index=50)
        _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=2), 200)
        _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=3), 250)

        board = _board(sqlite_db)
        assert [(e.rank, e.user_id, e.elapsed_time) for e in board.entries] == [
            (1, 2, 200.0),
            (2, 1, 250.0),
            (2, 3, 250.0),
        ]
        assert board.total == 3
        assert board.viewer_entry is not None and board.viewer_entry.rank == 2
        assert board.entries[0].user_name == "User 2"

    def test_pagination_keeps_viewer_entry(self, sqlite_db, three_users):
        segment = three_users
        _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=1), 300)
        _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=2), 200)

        board = _board(sqlite_db, num_records=1)
        assert [e.user_id for e in board.entries] == [2]
        assert board.viewer_entry is not None and board.viewer_entry.rank == 2

    @pytest.mark.parametrize(
        "overrides",
        [
            {"visibility": 2},
            {"visibility": 1},
            {"hide_map": True},
            {"is_hidden": True},
            {"strava_activity_id": 123},
        ],
    )
    def test_other_athletes_need_a_visible_activity(self, sqlite_db, three_users, overrides):
        _effort(sqlite_db, three_users, add_activity(sqlite_db, user_id=2, **overrides), 200)
        assert _board(sqlite_db).entries == []

    def test_followers_only_visible_to_accepted_followers(self, sqlite_db, three_users):
        _effort(sqlite_db, three_users, add_activity(sqlite_db, user_id=2, visibility=1), 200)
        sqlite_db.add(followers_models.Follower(follower_id=1, following_id=2, is_accepted=True))
        sqlite_db.commit()
        assert [e.user_id for e in _board(sqlite_db).entries] == [2]

    def test_own_efforts_always_count(self, sqlite_db, three_users):
        _effort(sqlite_db, three_users, add_activity(sqlite_db, user_id=1, visibility=2, hide_map=True), 200)
        assert [e.user_id for e in _board(sqlite_db).entries] == [1]

    def test_excluded_efforts_never_count(self, sqlite_db, three_users):
        _effort(sqlite_db, three_users, add_activity(sqlite_db, user_id=1), 200, is_excluded=True)
        board = _board(sqlite_db)
        assert board.entries == [] and board.viewer_entry is None

    def test_opt_out_hides_from_others_only(self, sqlite_db):
        _user(sqlite_db, 1)
        _user(sqlite_db, 2, opt_out=True)
        segment = add_segment(sqlite_db)
        _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=2), 200)

        assert _board(sqlite_db, viewer_id=1).entries == []
        assert [e.user_id for e in _board(sqlite_db, viewer_id=2).entries] == [2]

    def test_following_and_me_scopes(self, sqlite_db, three_users):
        segment = three_users
        for user_id, elapsed in ((1, 300), (2, 200), (3, 100)):
            _effort(sqlite_db, segment, add_activity(sqlite_db, user_id=user_id), elapsed)
        sqlite_db.add(followers_models.Follower(follower_id=1, following_id=2, is_accepted=True))
        sqlite_db.add(followers_models.Follower(follower_id=1, following_id=3, is_accepted=False))
        sqlite_db.commit()

        assert [e.user_id for e in _board(sqlite_db, scope=Scope.FOLLOWING).entries] == [2, 1]
        assert [e.user_id for e in _board(sqlite_db, scope=Scope.ME).entries] == [1]

    def test_period_filters(self, sqlite_db, three_users):
        segment = three_users
        mine = add_activity(sqlite_db, user_id=1)
        _effort(sqlite_db, segment, mine, 100, start_time=datetime(2023, 12, 31, tzinfo=UTC))
        _effort(sqlite_db, segment, mine, 200, start_index=50, start_time=datetime(2024, 1, 15, tzinfo=UTC))
        _effort(sqlite_db, segment, mine, 300, start_index=90, start_time=datetime(2024, 5, 1, tzinfo=UTC))

        assert _board(sqlite_db).entries[0].elapsed_time == 100.0
        assert _board(sqlite_db, period=Period.THIS_YEAR).entries[0].elapsed_time == 200.0
        assert _board(sqlite_db, period=Period.LAST_90_DAYS).entries[0].elapsed_time == 300.0

    def test_masks_hidden_metrics_of_others(self, sqlite_db, three_users):
        segment = three_users
        other = add_activity(sqlite_db, user_id=2, hide_hr=True, hide_power=True, hide_pace=True, hide_start_time=True)
        _effort(sqlite_db, segment, other, 200)
        mine = add_activity(sqlite_db, user_id=1, hide_hr=True, hide_start_time=True)
        _effort(sqlite_db, segment, mine, 300)

        theirs, own = _board(sqlite_db).entries
        assert (theirs.average_hr, theirs.average_power, theirs.average_speed, theirs.start_time) == (
            None,
            None,
            None,
            None,
        )
        assert own.average_hr == 150 and own.start_time is not None


class TestPersonalRecordDelta:
    def test_owner_gets_pr_elapsed_time(self, sqlite_db):
        segment = add_segment(sqlite_db)
        slow = add_activity(sqlite_db)
        fast = add_activity(sqlite_db)
        _effort(sqlite_db, segment, slow, 300, day=2)
        _effort(sqlite_db, segment, fast, 250, day=1)

        [effort] = segment_efforts_crud.get_activity_efforts(slow.id, 1, sqlite_db)
        assert effort.pr_elapsed_time == 250.0
        assert effort.current_rank == 2

    def test_others_get_no_pr(self, sqlite_db):
        segment = add_segment(sqlite_db)
        activity = add_activity(sqlite_db)
        _effort(sqlite_db, segment, activity, 300)
        [effort] = segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db)
        assert effort.pr_elapsed_time is None


class TestSimilarSegments:
    def test_finds_duplicate_of_same_slice(self, sqlite_db):
        activity = add_activity(sqlite_db)
        start, end = SLICE
        created = segment_crud.create_segment(
            1,
            segment_schema.SegmentCreate(activity_id=activity.id, start_index=start, end_index=end, name="River"),
            sqlite_db,
        )
        similar = segment_crud.get_similar_segments(1, activity.id, start, end, sqlite_db)
        assert [segment.id for segment in similar] == [created.id]

    def test_matches_same_path_only_within_sport_group(self, sqlite_db):
        activity = add_activity(sqlite_db)
        start, end = SLICE
        create = segment_schema.SegmentCreate(activity_id=activity.id, start_index=start, end_index=end, name="River")
        segment_crud.create_segment(1, create, sqlite_db)
        other_user = add_activity(sqlite_db, user_id=2)

        # Half the slice: same start, different end and length.
        assert segment_crud.get_similar_segments(1, activity.id, start, start + 100, sqlite_db) == []
        # Another user's run over the same path sees the public segment.
        assert len(segment_crud.get_similar_segments(2, other_user.id, start, end, sqlite_db)) == 1
        # A ride over the same path does not.
        ride = add_activity(sqlite_db, activity_type=4)
        assert segment_crud.get_similar_segments(1, ride.id, 0, 280, sqlite_db) == []

    def test_private_segment_hidden_from_others(self, sqlite_db):
        activity = add_activity(sqlite_db)
        start, end = SLICE
        segment_crud.create_segment(
            1,
            segment_schema.SegmentCreate(
                activity_id=activity.id, start_index=start, end_index=end, name="Mine", visibility=2
            ),
            sqlite_db,
        )
        other_user = add_activity(sqlite_db, user_id=2)
        assert segment_crud.get_similar_segments(2, other_user.id, start, end, sqlite_db) == []

    def test_requires_own_activity(self, sqlite_db):
        activity = add_activity(sqlite_db)
        with pytest.raises(HTTPException) as err:
            segment_crud.get_similar_segments(2, activity.id, *SLICE, sqlite_db)
        assert err.value.status_code == 404


class TestCreationPolicy:
    def _settings(self, db, **overrides):
        fields = {
            "id": 1,
            "units": "metric",
            "public_shareable_links": False,
            "public_shareable_links_user_info": False,
            "login_photo_set": False,
            "currency": "euro",
            "num_records_per_page": 25,
            "signup_enabled": False,
            "signup_require_admin_approval": False,
            "signup_require_email_verification": False,
            "sso_enabled": False,
            "local_login_enabled": True,
            "sso_auto_redirect": False,
            "tileserver_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "tileserver_attribution": "OSM",
            "map_background_color": "#dddddd",
            "password_type": "strict",
            "password_length_regular_users": 8,
            "password_length_admin_users": 12,
            "segments_enabled": True,
            "segments_public_creation": "all",
        }
        fields.update(overrides)
        db.add(server_settings_models.ServerSettings(**fields))
        db.commit()

    def _create(self, db, user_id: int, visibility: int):
        activity = add_activity(db, user_id=user_id)
        start, end = SLICE
        return segment_crud.create_segment(
            user_id,
            segment_schema.SegmentCreate(
                activity_id=activity.id, start_index=start, end_index=end, name="S", visibility=visibility
            ),
            db,
        )

    def test_disabled_segments_forbid_creation(self, sqlite_db):
        self._settings(sqlite_db, segments_enabled=False)
        with pytest.raises(HTTPException) as err:
            self._create(sqlite_db, 1, segments_constants.SEGMENT_VISIBILITY_PRIVATE)
        assert err.value.status_code == 403

    def test_admins_only_public_creation(self, sqlite_db):
        self._settings(sqlite_db, segments_public_creation="admins")
        _user(sqlite_db, 1)
        _user(sqlite_db, 2, access_type="admin")

        with pytest.raises(HTTPException) as err:
            self._create(sqlite_db, 1, segments_constants.SEGMENT_VISIBILITY_PUBLIC)
        assert err.value.status_code == 403

        private = self._create(sqlite_db, 1, segments_constants.SEGMENT_VISIBILITY_PRIVATE)
        assert private.visibility == segments_constants.SEGMENT_VISIBILITY_PRIVATE
        assert self._create(sqlite_db, 2, segments_constants.SEGMENT_VISIBILITY_PUBLIC).visibility == 0

        with pytest.raises(HTTPException) as err:
            segment_crud.edit_segment(private.id, 1, segment_schema.SegmentEdit(visibility=0), sqlite_db)
        assert err.value.status_code == 403
