"""Tests for segment effort CRUD on SQLite."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

import followers.models as followers_models
import segments.constants as segments_constants
import segments.matching.jobs as jobs
import segments.segment.crud as segment_crud
import segments.segment_efforts.crud as segment_efforts_crud
import segments.segment_efforts.models as segment_efforts_models
from tests.segments.conftest import add_activity, add_segment

DAY = 86_400.0


def _effort(segment_id, activity_id, user_id, elapsed, day, **overrides):
    fields = {
        "segment_id": segment_id,
        "activity_id": activity_id,
        "user_id": user_id,
        "start_time": datetime(2024, 1, 1 + day, tzinfo=UTC),
        "elapsed_time": Decimal(str(elapsed)),
        "distance": 1000.0,
        "start_index": 0,
        "end_index": 10,
        "is_excluded": False,
    }
    fields.update(overrides)
    return segment_efforts_models.SegmentEffort(**fields)


class TestActivityEfforts:
    def test_owner_sees_efforts_with_ranks(self, sqlite_db):
        segment = add_segment(sqlite_db)
        first = add_activity(sqlite_db, speed_mps=4.0)
        faster = add_activity(sqlite_db, speed_mps=5.0, start_time=1_704_096_000.0 + DAY)
        slower = add_activity(sqlite_db, speed_mps=3.0, start_time=1_704_096_000.0 + 2 * DAY)
        for activity in (first, faster, slower):
            jobs.match_activity(activity.id, sqlite_db)

        [latest] = segment_efforts_crud.get_activity_efforts(slower.id, 1, sqlite_db)
        assert latest.segment_name == "River path"
        assert (latest.current_rank, latest.historical_rank) == (3, 3)

        [best] = segment_efforts_crud.get_activity_efforts(faster.id, 1, sqlite_db)
        assert (best.current_rank, best.historical_rank) == (1, 1)

        [oldest] = segment_efforts_crud.get_activity_efforts(first.id, 1, sqlite_db)
        # Was a PR when recorded, now second.
        assert (oldest.current_rank, oldest.historical_rank) == (2, 1)
        assert segment.id == oldest.segment_id

    def test_other_users_see_masked_efforts_without_ranks(self, sqlite_db):
        add_segment(sqlite_db)
        activity = add_activity(sqlite_db, hide_hr=True, hide_speed=True)
        jobs.match_activity(activity.id, sqlite_db)

        [effort] = segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db)
        assert effort.average_hr is None and effort.max_hr is None
        assert effort.average_speed is None
        assert effort.current_rank is None

    def test_power_and_cadence_masked(self, sqlite_db):
        segment = add_segment(sqlite_db)
        activity = add_activity(sqlite_db, hide_power=True, hide_cadence=True)
        sqlite_db.add(_effort(segment.id, activity.id, 1, 100, 0, average_power=200, average_cad=90))
        sqlite_db.commit()

        [effort] = segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db)
        assert (effort.average_power, effort.normalized_power, effort.average_cad) == (None, None, None)

    def test_hidden_map_hides_efforts_from_others(self, sqlite_db):
        add_segment(sqlite_db)
        activity = add_activity(sqlite_db, hide_map=True)
        jobs.match_activity(activity.id, sqlite_db)

        assert segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db) == []
        assert len(segment_efforts_crud.get_activity_efforts(activity.id, 1, sqlite_db)) == 1

    def test_private_activity_hidden_from_others(self, sqlite_db):
        add_segment(sqlite_db)
        activity = add_activity(sqlite_db, visibility=2)
        jobs.match_activity(activity.id, sqlite_db)
        assert segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db) == []

    def test_followers_activity_visible_to_accepted_follower(self, sqlite_db):
        add_segment(sqlite_db)
        activity = add_activity(sqlite_db, visibility=1)
        jobs.match_activity(activity.id, sqlite_db)
        sqlite_db.add(followers_models.Follower(follower_id=2, following_id=1, is_accepted=True))
        sqlite_db.commit()

        assert len(segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db)) == 1
        assert segment_efforts_crud.get_activity_efforts(activity.id, 3, sqlite_db) == []

    def test_private_segments_and_excluded_efforts_hidden_from_others(self, sqlite_db):
        private = add_segment(sqlite_db, user_id=1, visibility=segments_constants.SEGMENT_VISIBILITY_PRIVATE)
        public = add_segment(sqlite_db, user_id=2)
        activity = add_activity(sqlite_db)
        sqlite_db.add_all(
            [
                _effort(private.id, activity.id, 1, 100, 0),
                _effort(public.id, activity.id, 1, 100, 0, is_excluded=True),
            ]
        )
        sqlite_db.commit()

        assert segment_efforts_crud.get_activity_efforts(activity.id, 2, sqlite_db) == []
        owner_view = segment_efforts_crud.get_activity_efforts(activity.id, 1, sqlite_db)
        assert len(owner_view) == 2
        excluded = next(effort for effort in owner_view if effort.is_excluded)
        assert excluded.current_rank is None

    def test_invisible_activity_returns_nothing(self, sqlite_db):
        assert segment_efforts_crud.get_activity_efforts(999, 1, sqlite_db) == []


def test_user_segment_efforts_fastest_first(sqlite_db):
    """History lists non-excluded efforts by elapsed time, excluded last."""
    segment = add_segment(sqlite_db)
    activity = add_activity(sqlite_db)
    sqlite_db.add_all(
        [
            _effort(segment.id, activity.id, 1, 120, 0, start_index=0),
            _effort(segment.id, activity.id, 1, 90, 1, start_index=1, is_excluded=True),
            _effort(segment.id, activity.id, 1, 100, 2, start_index=2),
            _effort(segment.id, activity.id, 2, 80, 2, start_index=3),
        ]
    )
    sqlite_db.commit()

    efforts = segment_efforts_crud.get_user_segment_efforts(segment.id, 1, sqlite_db)

    assert [effort.elapsed_time for effort in efforts] == [100.0, 120.0, 90.0]
    assert [effort.current_rank for effort in efforts] == [1, 2, None]
    assert [effort.historical_rank for effort in efforts] == [1, 1, None]


class TestSetEffortExcluded:
    def test_owner_can_exclude_and_counts_update(self, sqlite_db):
        segment = add_segment(sqlite_db)
        activity = add_activity(sqlite_db)
        jobs.match_activity(activity.id, sqlite_db)
        [effort] = segment_efforts_crud.get_activity_efforts(activity.id, 1, sqlite_db)
        assert segment_crud.get_segment_model(segment.id, sqlite_db).effort_count == 1

        updated = segment_efforts_crud.set_effort_excluded(effort.id, 1, True, sqlite_db)

        assert updated.is_excluded
        assert segment_crud.get_segment_model(segment.id, sqlite_db).effort_count == 0

    def test_other_user_gets_404(self, sqlite_db):
        add_segment(sqlite_db)
        activity = add_activity(sqlite_db)
        jobs.match_activity(activity.id, sqlite_db)
        [effort] = segment_efforts_crud.get_activity_efforts(activity.id, 1, sqlite_db)

        with pytest.raises(HTTPException) as err:
            segment_efforts_crud.set_effort_excluded(effort.id, 2, True, sqlite_db)
        assert err.value.status_code == 404
