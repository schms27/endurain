"""Tests for the scheduled auto import API endpoints."""

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import activities.activity_auto_import.models as auto_import_models

AUTH = {"Authorization": "Bearer x"}


def _build_app(mock_db):
    import activities.activity_auto_import.router as router
    import auth.dependencies as auth_deps
    import core.database as core_db

    app = FastAPI()
    app.include_router(router.router, prefix="/auto_import")
    app.dependency_overrides[auth_deps.get_sub_from_access_token] = lambda: 1
    app.dependency_overrides[auth_deps.check_scopes] = lambda: None
    app.dependency_overrides[core_db.get_db] = lambda: mock_db
    return app


_USER = SimpleNamespace(id=1, username="alice")


@patch("activities.activity_auto_import.router.users_crud.get_user_by_id", return_value=_USER)
class TestReadSettings:
    @patch("activities.activity_auto_import.router.auto_import_crud.get_settings_by_user_id", return_value=None)
    def test_defaults_when_unsaved(self, _get, _user, mock_db):
        response = TestClient(_build_app(mock_db)).get("/auto_import", headers=AUTH)

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is False
        assert body["interval_minutes"] == 60
        assert body["folder"] == "auto_import/alice"

    def test_unknown_user_404(self, user, mock_db):
        user.return_value = None
        response = TestClient(_build_app(mock_db)).get("/auto_import", headers=AUTH)
        assert response.status_code == 404


@patch("activities.activity_auto_import.router.users_crud.get_user_by_id", return_value=_USER)
class TestEditSettings:
    @patch("activities.activity_auto_import.router.auto_import_utils.ensure_user_import_dir")
    @patch("activities.activity_auto_import.router.auto_import_crud.upsert_settings")
    def test_enable_creates_folder(self, upsert, ensure_dir, _user, mock_db):
        upsert.return_value = auto_import_models.UsersAutoImportSettings(
            user_id=1, enabled=True, interval_minutes=30, last_run_imported=0, last_run_failed=0
        )

        response = TestClient(_build_app(mock_db)).put(
            "/auto_import", json={"enabled": True, "interval_minutes": 30}, headers=AUTH
        )

        assert response.status_code == 200
        assert response.json()["interval_minutes"] == 30
        ensure_dir.assert_called_once_with("alice")

    def test_rejects_unlisted_interval(self, _user, mock_db):
        response = TestClient(_build_app(mock_db)).put(
            "/auto_import", json={"enabled": True, "interval_minutes": 7}, headers=AUTH
        )
        assert response.status_code == 422


class TestRunNow:
    @patch("activities.activity_auto_import.router.core_scheduler.schedule_user_auto_import")
    def test_queues_job(self, schedule, mock_db):
        response = TestClient(_build_app(mock_db)).post("/auto_import/run", headers=AUTH)

        assert response.status_code == 202
        schedule.assert_called_once_with(1)

    @patch("activities.activity_auto_import.router.core_scheduler.schedule_user_auto_import")
    @patch("activities.activity_auto_import.router.auto_import_utils.is_running", return_value=True)
    def test_conflict_when_running(self, _running, schedule, mock_db):
        response = TestClient(_build_app(mock_db)).post("/auto_import/run", headers=AUTH)

        assert response.status_code == 409
        schedule.assert_not_called()
