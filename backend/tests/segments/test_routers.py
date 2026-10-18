"""Tests for the segment and segment effort routers."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import segments.constants as segments_constants
import segments.segment.schema as segment_schema
import segments.segment_efforts.schema as segment_efforts_schema

AUTH = {"Authorization": "Bearer x"}
NOW = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def client(mock_db):
    import auth.dependencies as auth_deps
    import core.database as core_db
    import segments.segment.router as segments_router
    import segments.segment_efforts.router as segment_efforts_router

    app = FastAPI()
    app.include_router(segments_router.router, prefix="/segments")
    app.include_router(segment_efforts_router.router, prefix="/segment_efforts")
    app.dependency_overrides[auth_deps.check_scopes] = lambda: None
    app.dependency_overrides[auth_deps.get_sub_from_access_token] = lambda: 1
    app.dependency_overrides[core_db.get_db] = lambda: mock_db
    return TestClient(app)


def _summary(**overrides):
    fields = {
        "id": 1,
        "user_id": 1,
        "name": "River path",
        "sport_group": segments_constants.SportGroup.RUN,
        "visibility": 0,
        "distance": 1000.0,
        "elevation_gain": 10,
        "average_grade": 1.0,
        "start_lat": 1.0,
        "start_lon": 2.0,
        "city": None,
        "town": None,
        "country": None,
        "is_archived": False,
        "effort_count": 0,
        "athlete_count": 0,
        "created_at": NOW,
    }
    fields.update(overrides)
    return fields


def _segment(**overrides):
    fields = _summary(
        description=None,
        geometry=[[1.0, 2.0, None], [1.1, 2.1, None]],
        elevation_loss=None,
        maximum_grade=None,
        end_lat=1.1,
        end_lon=2.1,
        source_activity_id=5,
        updated_at=NOW,
    )
    fields.update(overrides)
    return segment_schema.SegmentRead(**fields)


def _effort():
    return segment_efforts_schema.SegmentEffortRead(
        id=1,
        segment_id=1,
        activity_id=5,
        user_id=1,
        start_time=NOW,
        elapsed_time=200.0,
        distance=1000.0,
        start_index=40,
        end_index=240,
        average_hr=None,
        max_hr=None,
        average_power=None,
        normalized_power=None,
        average_cad=None,
        average_speed=5.0,
        is_excluded=False,
    )


@patch("segments.segment.router.segment_crud.create_segment")
def test_create_segment(mock_create, client):
    mock_create.return_value = _segment()
    response = client.post(
        "/segments",
        json={"activity_id": 5, "start_index": 40, "end_index": 240, "name": "River path"},
        headers=AUTH,
    )
    assert response.status_code == 201
    assert response.json()["source_activity_id"] == 5
    assert mock_create.call_args.args[0] == 1


def test_create_segment_rejects_reversed_slice(client):
    response = client.post(
        "/segments",
        json={"activity_id": 5, "start_index": 240, "end_index": 40, "name": "x"},
        headers=AUTH,
    )
    assert response.status_code == 422


@patch("segments.segment.router.segment_crud.list_segments")
def test_list_segments_with_bbox(mock_list, client):
    mock_list.return_value = [segment_schema.SegmentSummary(**_summary())]
    response = client.get(
        "/segments?min_lat=1&min_lon=2&max_lat=3&max_lon=4&sport_group=run&q=river",
        headers=AUTH,
    )
    assert response.status_code == 200
    kwargs = mock_list.call_args.kwargs
    assert kwargs["bbox"].max_lon == 4
    assert kwargs["sport_group"] == segments_constants.SportGroup.RUN
    assert kwargs["query"] == "river"


def test_list_segments_rejects_partial_bbox(client):
    assert client.get("/segments?min_lat=1", headers=AUTH).status_code == 400


@patch("segments.segment.router.segment_crud.get_segment_visible_to_user")
def test_read_segment(mock_get, client):
    mock_get.return_value = _segment()
    assert client.get("/segments/1", headers=AUTH).json()["name"] == "River path"
    mock_get.return_value = None
    assert client.get("/segments/1", headers=AUTH).status_code == 404


@patch("segments.segment.router.segment_crud.edit_segment")
def test_edit_segment(mock_edit, client):
    mock_edit.return_value = _segment(name="New")
    response = client.put("/segments/1", json={"name": "New"}, headers=AUTH)
    assert response.status_code == 200
    assert mock_edit.call_args.args[2].name == "New"


def test_edit_segment_rejects_followers_visibility(client):
    assert client.put("/segments/1", json={"visibility": 1}, headers=AUTH).status_code == 422


@patch("segments.segment.router.segment_crud.delete_segment")
def test_delete_segment(mock_delete, client):
    assert client.delete("/segments/1", headers=AUTH).status_code == 204
    mock_delete.assert_called_once()


@patch("segments.segment.router.segment_efforts_crud.get_user_segment_efforts")
@patch("segments.segment.router.segment_crud.get_segment_visible_to_user")
def test_read_my_efforts(mock_get, mock_efforts, client):
    mock_get.return_value = _segment()
    mock_efforts.return_value = [_effort()]
    assert client.get("/segments/1/efforts", headers=AUTH).json()[0]["elapsed_time"] == 200.0
    mock_get.return_value = None
    assert client.get("/segments/1/efforts", headers=AUTH).status_code == 404


@patch("segments.segment.router.segment_crud.request_rematch")
def test_rematch_segment(mock_rematch, client):
    assert client.post("/segments/1/rematch", headers=AUTH).status_code == 202
    mock_rematch.assert_called_once()


@patch("segments.segment_efforts.router.segment_efforts_crud.get_activity_efforts")
def test_read_activity_efforts(mock_get, client):
    mock_get.return_value = [_effort()]
    response = client.get("/segment_efforts/activity_id/5", headers=AUTH)
    assert response.status_code == 200
    assert mock_get.call_args.args[:2] == (5, 1)


@patch("segments.segment_efforts.router.segment_efforts_crud.set_effort_excluded")
def test_exclude_effort(mock_set, client):
    mock_set.return_value = _effort()
    response = client.patch("/segment_efforts/1", json={"is_excluded": True}, headers=AUTH)
    assert response.status_code == 200
    assert mock_set.call_args.args == (1, 1, True, mock_set.call_args.args[3])
