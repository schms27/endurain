"""Tests for the routes router."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.constants as routes_constants
import routes.route.schema as route_schema
from tests.routes.test_parsers import GPX_TRACK

AUTH = {"Authorization": "Bearer x"}
NOW = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def client(mock_db):
    import auth.dependencies as auth_deps
    import core.database as core_db
    import routes.route.router as routes_router

    app = FastAPI()
    app.include_router(routes_router.router, prefix="/routes")
    app.dependency_overrides[auth_deps.check_scopes] = lambda: None
    app.dependency_overrides[auth_deps.get_sub_from_access_token] = lambda: 1
    app.dependency_overrides[core_db.get_db] = lambda: mock_db
    return TestClient(app)


def _route(**overrides):
    fields = {
        "id": 1,
        "user_id": 1,
        "name": "Castle loop",
        "activity_type": None,
        "source": routes_constants.RouteSource.IMPORT,
        "distance": 1000.0,
        "elevation_gain": 10,
        "elevation_loss": 10,
        "is_loop": True,
        "city": None,
        "country": None,
        "created_at": NOW,
        "description": None,
        "source_activity_id": None,
        "original_filename": "castle.gpx",
        "geometry": [[1.0, 2.0, None], [1.1, 2.1, 5.0]],
        "waypoints": [],
        "elevation_min": 0,
        "elevation_max": 5,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return route_schema.RouteRead(**fields)


@patch("routes.route.router.core_file_uploads.validate_upload", new_callable=AsyncMock)
@patch("routes.route.router.route_crud.import_route")
def test_import_route(mock_import, mock_validate, client):
    mock_import.return_value = _route()
    response = client.post("/routes/import", files={"file": ("Castle.GPX", GPX_TRACK)}, headers=AUTH)
    assert response.status_code == 201
    user_id, data, filename, extension, _ = mock_import.call_args.args
    assert (user_id, data, filename, extension) == (1, GPX_TRACK, "Castle.GPX", "gpx")
    mock_validate.assert_awaited_once()


@pytest.mark.parametrize("filename", ["route.kml", "noextension"])
def test_import_rejects_unsupported_types(client, filename):
    response = client.post("/routes/import", files={"file": (filename, b"data")}, headers=AUTH)
    assert response.status_code == 400


@patch("routes.route.router.core_file_uploads.validate_upload", new_callable=AsyncMock)
def test_import_rejects_large_files(_validate, client, monkeypatch):
    monkeypatch.setattr(routes_constants, "MAX_ROUTE_FILE_BYTES", 10)
    response = client.post("/routes/import", files={"file": ("a.gpx", GPX_TRACK)}, headers=AUTH)
    assert response.status_code == 413


@patch("routes.route.router.route_crud.create_route_from_activity")
def test_from_activity(mock_create, client):
    mock_create.return_value = _route(source=routes_constants.RouteSource.ACTIVITY, source_activity_id=5)
    response = client.post("/routes/from_activity/5", json={"start_index": 1, "end_index": 9}, headers=AUTH)
    assert response.status_code == 201
    assert mock_create.call_args.args[1] == 5
    assert (
        client.post("/routes/from_activity/5", json={"start_index": 9, "end_index": 1}, headers=AUTH).status_code == 422
    )


@patch("routes.route.router.route_crud.list_routes")
def test_list_routes(mock_list, client):
    mock_list.return_value = route_schema.RoutesPage(records=[_route()], total=1)
    response = client.get("/routes?q=castle&activity_type=4&page_number=2&num_records=5", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert mock_list.call_args.kwargs == {"query": "castle", "activity_type": 4, "page_number": 2, "num_records": 5}


@patch("routes.route.router.route_crud.get_route")
def test_read_route(mock_get, client):
    mock_get.return_value = _route()
    assert client.get("/routes/1", headers=AUTH).json()["geometry"][1] == [1.1, 2.1, 5.0]


@patch("routes.route.router.route_crud.edit_route")
def test_edit_route(mock_edit, client):
    mock_edit.return_value = _route(name="New")
    assert client.put("/routes/1", json={"name": "New"}, headers=AUTH).json()["name"] == "New"
    assert client.put("/routes/1", json={"visibility": 0}, headers=AUTH).status_code == 422


@patch("routes.route.router.route_crud.delete_route")
def test_delete_route(mock_delete, client):
    assert client.delete("/routes/1", headers=AUTH).status_code == 204
    mock_delete.assert_called_once()


@patch("routes.route.router.route_crud.get_owned_route_model")
def test_export_route(mock_get, client):
    mock_get.return_value = SimpleNamespace(
        name="Castle Loop", description=None, geometry=[[1.0, 2.0, None], [1.1, 2.1, None]], waypoints=[]
    )
    response = client.get("/routes/1/export?format=gpx", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert response.headers["content-disposition"] == 'attachment; filename="castle-loop.gpx"'
    assert "<trkpt" in response.text
    assert client.get("/routes/1/export?format=kml", headers=AUTH).status_code == 422
