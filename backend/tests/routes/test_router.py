"""Tests for the routes router."""

from datetime import UTC, datetime
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
        "visibility": routes_constants.RouteVisibility.PRIVATE,
        "distance": 1000.0,
        "elevation_gain": 10,
        "elevation_loss": 10,
        "is_loop": True,
        "city": None,
        "country": None,
        "created_at": NOW,
        "description": None,
        "source_activity_id": None,
        "source_route_id": None,
        "original_filename": "castle.gpx",
        "share_token": None,
        "hide_endpoints_m": 0,
        "is_owner": True,
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
    assert client.put("/routes/1", json={"visibility": 0, "hide_endpoints_m": 300}, headers=AUTH).status_code == 200
    edit = mock_edit.call_args.args[2]
    assert (edit.visibility, edit.hide_endpoints_m) == (routes_constants.RouteVisibility.PUBLIC, 300)
    assert client.put("/routes/1", json={"visibility": 3}, headers=AUTH).status_code == 422
    assert client.put("/routes/1", json={"hide_endpoints_m": 5000}, headers=AUTH).status_code == 422
    assert client.put("/routes/1", json={"share_token": "x"}, headers=AUTH).status_code == 422


@patch("routes.route.router.route_crud.delete_route")
def test_delete_route(mock_delete, client):
    assert client.delete("/routes/1", headers=AUTH).status_code == 204
    mock_delete.assert_called_once()


@patch("routes.route.router.route_crud.get_route")
def test_export_route(mock_get, client):
    mock_get.return_value = _route(name="Castle Loop")
    response = client.get("/routes/1/export?format=gpx", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert response.headers["content-disposition"] == 'attachment; filename="castle-loop.gpx"'
    assert "<trkpt" in response.text
    assert client.get("/routes/1/export?format=kml", headers=AUTH).status_code == 422


TOKEN = "A" * 43


@patch("routes.route.router.route_crud.copy_route")
@patch("routes.route.router.route_crud.get_visible_route_model")
def test_copy_route(mock_get, mock_copy, client):
    mock_copy.return_value = _route(id=2, source=routes_constants.RouteSource.COPY, source_route_id=1)
    response = client.post("/routes/1/copy", headers=AUTH)
    assert response.status_code == 201
    assert response.json()["source_route_id"] == 1
    assert mock_get.call_args.args[:2] == (1, 1)
    assert mock_copy.call_args.args[0] is mock_get.return_value


@patch("routes.route.router.route_crud.copy_route")
@patch("routes.route.router.route_crud.get_shared_route_model")
def test_copy_shared_route(mock_get, mock_copy, client):
    mock_copy.return_value = _route(id=2, source=routes_constants.RouteSource.COPY, source_route_id=1)
    assert client.post(f"/routes/shared/{TOKEN}/copy", headers=AUTH).status_code == 201
    assert mock_get.call_args.args[0] == TOKEN
    assert client.post("/routes/shared/bad$token$value!!/copy", headers=AUTH).status_code == 422


@patch("routes.route.router.route_crud.revoke_share_token")
@patch("routes.route.router.route_crud.create_share_token")
def test_share_token(mock_create, mock_revoke, client):
    mock_create.return_value = _route(share_token=TOKEN)
    mock_revoke.return_value = _route()
    assert client.post("/routes/1/share_token", headers=AUTH).json()["share_token"] == TOKEN
    assert client.delete("/routes/1/share_token", headers=AUTH).json()["share_token"] is None
    assert mock_create.call_args.args[:2] == (1, 1)
    assert mock_revoke.call_args.args[:2] == (1, 1)


@patch("routes.route.router.route_crud.home_location_warning")
def test_home_warning(mock_warning, client):
    mock_warning.return_value = route_schema.RouteHomeWarning(start_near_home=True, end_near_home=False)
    assert client.get("/routes/1/home_warning", headers=AUTH).json() == {
        "start_near_home": True,
        "end_near_home": False,
    }


@patch("routes.route.router.route_crud.list_user_routes")
def test_list_user_routes(mock_list, client):
    import routes.route.router as routes_router

    client.app.include_router(routes_router.user_router, prefix="/users")
    mock_list.return_value = route_schema.RoutesPage(records=[_route(is_owner=False)], total=1)
    response = client.get("/users/7/routes?page_number=2&num_records=5", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert mock_list.call_args.args[:2] == (7, 1)
    assert mock_list.call_args.kwargs == {"page_number": 2, "num_records": 5}


@pytest.fixture
def public_client(mock_db):
    import core.database as core_db
    import routes.route.public_router as public_router

    app = FastAPI()
    app.include_router(public_router.router, prefix="/public/routes")
    app.dependency_overrides[core_db.get_db] = lambda: mock_db
    return TestClient(app)


def _public(**overrides):
    return route_schema.PublicRouteRead(**dict(_route(is_owner=False, original_filename=None)), **overrides)


@patch("routes.route.public_router.route_crud.present_public_route")
@patch("routes.route.public_router.route_crud.get_shared_route_model")
def test_public_by_token(mock_get, mock_present, public_client):
    mock_present.return_value = _public(owner=route_schema.RouteOwner(id=1, name="Ana", username="ana"))
    response = public_client.get(f"/public/routes/by_token/{TOKEN}")
    assert response.status_code == 200
    assert response.json()["owner"]["username"] == "ana"
    assert mock_get.call_args.args[0] == TOKEN
    assert public_client.get("/public/routes/by_token/short").status_code == 422


@patch("routes.route.public_router.route_crud.present_public_route")
@patch("routes.route.public_router.route_crud.get_public_route_model")
def test_public_by_id(mock_get, mock_present, public_client):
    mock_present.return_value = _public()
    response = public_client.get("/public/routes/5")
    assert response.status_code == 200
    assert response.json()["owner"] is None
    assert mock_get.call_args.args[0] == 5


@pytest.mark.parametrize(
    ("path", "getter"),
    [
        (f"/public/routes/by_token/{TOKEN}/export", "get_shared_route_model"),
        ("/public/routes/5/export", "get_public_route_model"),
    ],
)
def test_public_export_is_non_owner_view(public_client, path, getter):
    with (
        patch(f"routes.route.public_router.route_crud.{getter}") as mock_get,
        patch("routes.route.public_router.route_crud.present_route") as mock_present,
    ):
        mock_present.return_value = _route(name="Castle Loop", is_owner=False)
        response = public_client.get(path)
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="castle-loop.gpx"'
    assert mock_present.call_args.args[0] is mock_get.return_value
    assert mock_present.call_args.kwargs == {"is_owner": False}


@patch("routes.route.public_router.route_crud.get_public_route_model")
def test_public_not_found(mock_get, public_client):
    from fastapi import HTTPException

    mock_get.side_effect = HTTPException(status_code=404, detail="Route not found")
    assert public_client.get("/public/routes/5").status_code == 404
