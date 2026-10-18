"""Tests for segment CRUD on SQLite."""

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

import activities.activity_streams.models as activity_streams_models
import core.geo as core_geo
import segments.constants as segments_constants
import segments.matching.jobs as jobs
import segments.matching.models as matching_models
import segments.segment.crud as segment_crud
import segments.segment.schema as segment_schema
import segments.segment_efforts.models as segment_efforts_models
from tests._helpers import tracks
from tests.segments.conftest import SLICE, add_activity, add_segment

PRIVATE = segments_constants.SEGMENT_VISIBILITY_PRIVATE


def _request(activity_id, start=SLICE[0], end=SLICE[1], **overrides):
    return segment_schema.SegmentCreate(
        activity_id=activity_id, start_index=start, end_index=end, name="River <b>path</b>", **overrides
    )


def _queued_segments(db):
    return [item.segment_id for item in db.scalars(select(matching_models.SegmentMatchQueue))]


class TestCreateSegment:
    def test_creates_segment_with_derived_stats(self, sqlite_db):
        activity = add_activity(sqlite_db)
        segment = segment_crud.create_segment(1, _request(activity.id, description="**nice**"), sqlite_db)

        assert segment.name == "River path"
        assert segment.description == "**nice**"
        assert segment.sport_group == segments_constants.SportGroup.RUN
        assert segment.distance == pytest.approx(1000.0, rel=0.01)
        assert segment.elevation_gain == pytest.approx(50, abs=2)
        assert segment.average_grade == pytest.approx(5.0, abs=0.1)
        assert segment.maximum_grade == pytest.approx(5.0, abs=0.1)
        assert segment.city == "Lisbon"
        assert segment.source_activity_id == activity.id
        # A straight slice simplifies to its two end points.
        assert len(segment.geometry) == 2
        assert _queued_segments(sqlite_db) == [segment.id]

    def test_rejects_activity_of_another_user(self, sqlite_db):
        activity = add_activity(sqlite_db, user_id=2)
        with pytest.raises(HTTPException) as err:
            segment_crud.create_segment(1, _request(activity.id), sqlite_db)
        assert err.value.status_code == 404

    def test_rejects_missing_activity(self, sqlite_db):
        with pytest.raises(HTTPException) as err:
            segment_crud.create_segment(1, _request(999), sqlite_db)
        assert err.value.status_code == 404

    def test_rejects_unsupported_sport(self, sqlite_db):
        activity = add_activity(sqlite_db, activity_type=7)  # virtual cycling
        with pytest.raises(HTTPException) as err:
            segment_crud.create_segment(1, _request(activity.id), sqlite_db)
        assert err.value.status_code == 400

    def test_rejects_activity_without_gps(self, sqlite_db):
        activity = add_activity(sqlite_db)
        sqlite_db.execute(delete(activity_streams_models.ActivityStreams))
        sqlite_db.commit()
        with pytest.raises(HTTPException) as err:
            segment_crud.create_segment(1, _request(activity.id), sqlite_db)
        assert err.value.status_code == 400

    def test_rejects_invalid_slice(self, sqlite_db):
        activity = add_activity(sqlite_db)
        with pytest.raises(HTTPException) as err:
            segment_crud.create_segment(1, _request(activity.id, start=40, end=60), sqlite_db)
        assert err.value.status_code == 400
        assert "shorter" in err.value.detail

    def test_sanitizes_name_to_default(self, sqlite_db):
        activity = add_activity(sqlite_db)
        request = _request(activity.id)
        request.name = "<b></b>"
        assert segment_crud.create_segment(1, request, sqlite_db).name == "Segment"


class TestVisibility:
    def test_public_visible_to_all_private_only_to_owner(self, sqlite_db):
        public = add_segment(sqlite_db, user_id=1)
        private = add_segment(sqlite_db, user_id=1, visibility=PRIVATE)

        assert segment_crud.get_segment_visible_to_user(public.id, 2, sqlite_db) is not None
        assert segment_crud.get_segment_visible_to_user(private.id, 2, sqlite_db) is None
        assert segment_crud.get_segment_visible_to_user(private.id, 1, sqlite_db) is not None

    def test_archived_hidden_from_others(self, sqlite_db):
        archived = add_segment(sqlite_db, user_id=1, is_archived=True)
        assert segment_crud.get_segment_visible_to_user(archived.id, 2, sqlite_db) is None
        assert segment_crud.get_segment_visible_to_user(archived.id, 1, sqlite_db) is not None


class TestListSegments:
    def test_filters(self, sqlite_db):
        mine = add_segment(sqlite_db, user_id=1, name="Castle climb")
        theirs = add_segment(sqlite_db, user_id=2, name="River path")
        add_segment(sqlite_db, user_id=2, name="Secret", visibility=PRIVATE)
        ride = add_segment(sqlite_db, user_id=2, name="Bridge", sport_group=segments_constants.SportGroup.RIDE)
        far_lats, far_lons = tracks.to_lat_lon(np.asarray([50_000.0, 51_000.0]), np.asarray([0.0, 0.0]))
        far = add_segment(
            sqlite_db,
            user_id=2,
            name="Far away",
            bbox_min_lat=float(far_lats.min()),
            bbox_max_lat=float(far_lats.max()),
            bbox_min_lon=float(far_lons.min()),
            bbox_max_lon=float(far_lons.max()),
        )

        def ids(**kwargs):
            return {segment.id for segment in segment_crud.list_segments(1, sqlite_db, **kwargs)}

        assert ids() == {mine.id, theirs.id, ride.id, far.id}
        assert ids(created_by_me=True) == {mine.id}
        assert ids(sport_group=segments_constants.SportGroup.RIDE) == {ride.id}
        assert ids(query="castle") == {mine.id}
        assert ids(query="100%") == set()
        near = core_geo.BoundingBox(mine.bbox_min_lat, mine.bbox_min_lon, mine.bbox_max_lat, mine.bbox_max_lon)
        assert ids(bbox=near) == {mine.id, theirs.id, ride.id}
        assert len(segment_crud.list_segments(1, sqlite_db, page_number=2, num_records=3)) == 1


class TestEditAndDelete:
    def test_edit_metadata_without_requeue(self, sqlite_db):
        segment = add_segment(sqlite_db)
        edited = segment_crud.edit_segment(
            segment.id, 1, segment_schema.SegmentEdit(name="New <i>name</i>", description=None), sqlite_db
        )
        assert (edited.name, edited.description) == ("New name", None)
        assert _queued_segments(sqlite_db) == []

    def test_edit_description_and_visibility_requeues(self, sqlite_db):
        segment = add_segment(sqlite_db)
        edited = segment_crud.edit_segment(
            segment.id, 1, segment_schema.SegmentEdit(description="Hi", visibility=PRIVATE), sqlite_db
        )
        assert (edited.description, edited.visibility) == ("Hi", PRIVATE)
        assert _queued_segments(sqlite_db) == [segment.id]

    def test_edit_requires_ownership(self, sqlite_db):
        segment = add_segment(sqlite_db, user_id=2)
        with pytest.raises(HTTPException) as err:
            segment_crud.edit_segment(segment.id, 1, segment_schema.SegmentEdit(name="x"), sqlite_db)
        assert err.value.status_code == 404

    def test_delete_removes_efforts(self, sqlite_db):
        segment = add_segment(sqlite_db)
        activity = add_activity(sqlite_db)
        jobs.match_activity(activity.id, sqlite_db)

        segment_crud.delete_segment(segment.id, 1, sqlite_db)

        assert segment_crud.get_segment_model(segment.id, sqlite_db) is None
        assert list(sqlite_db.scalars(select(segment_efforts_models.SegmentEffort))) == []

    def test_delete_requires_ownership(self, sqlite_db):
        segment = add_segment(sqlite_db, user_id=2)
        with pytest.raises(HTTPException):
            segment_crud.delete_segment(segment.id, 1, sqlite_db)

    def test_request_rematch(self, sqlite_db):
        segment = add_segment(sqlite_db)
        segment_crud.request_rematch(segment.id, 1, sqlite_db)
        assert _queued_segments(sqlite_db) == [segment.id]


def test_candidate_segments(sqlite_db):
    """Candidates share the sport group, overlap, and are public or owned."""
    public = add_segment(sqlite_db, user_id=2)
    own_private = add_segment(sqlite_db, user_id=1, visibility=PRIVATE)
    add_segment(sqlite_db, user_id=2, visibility=PRIVATE)
    add_segment(sqlite_db, user_id=2, is_archived=True)
    add_segment(sqlite_db, user_id=2, sport_group=segments_constants.SportGroup.RIDE)
    bbox = core_geo.BoundingBox(public.bbox_min_lat, public.bbox_min_lon, public.bbox_max_lat, public.bbox_max_lon)

    candidates = segment_crud.get_candidate_segments(segments_constants.SportGroup.RUN, bbox, 1, sqlite_db)

    assert {segment.id for segment in candidates} == {public.id, own_private.id}


def test_outdated_segment_ids(sqlite_db):
    """Only non-archived segments from an older matcher are listed."""
    old = add_segment(sqlite_db, matcher_version=0)
    add_segment(sqlite_db, matcher_version=0, is_archived=True)
    add_segment(sqlite_db)
    assert segment_crud.get_outdated_segment_ids(sqlite_db) == [old.id]


def test_refresh_counts_skips_missing_segments(sqlite_db):
    """Unknown segment IDs are ignored."""
    segment_crud.refresh_counts({4242}, sqlite_db)
