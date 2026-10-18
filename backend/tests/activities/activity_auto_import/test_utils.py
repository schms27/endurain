"""Tests for the scheduled auto import scan and job."""

import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from tests._helpers.db import create_sqlite_session

import activities.activity_auto_import.crud as auto_import_crud
import activities.activity_auto_import.models as auto_import_models
import activities.activity_auto_import.schema as auto_import_schema
import activities.activity_auto_import.utils as auto_import_utils


@pytest.fixture
def sqlite_db():
    session = create_sqlite_session()
    try:
        yield session
    finally:
        session.close()
        session.bind.dispose()


@pytest.fixture
def import_root(tmp_path, monkeypatch):
    root = tmp_path / "auto_import"
    root.mkdir()
    monkeypatch.setattr(auto_import_utils.core_config, "FILES_AUTO_IMPORT_DIR", str(root))
    monkeypatch.setattr(
        auto_import_utils.core_config, "FILES_BULK_IMPORT_IMPORT_ERRORS_DIR", str(tmp_path / "import_errors")
    )
    return root


def _write(path, age_seconds=3600):
    path.write_bytes(b"data")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _settings(**overrides):
    values = {
        "user_id": 1,
        "enabled": True,
        "interval_minutes": 60,
        "last_run_at": None,
        "last_run_imported": 0,
        "last_run_failed": 0,
    }
    values.update(overrides)
    return auto_import_models.UsersAutoImportSettings(**values)


class TestUserImportDir:
    def test_folder_is_username_under_root(self, import_root):
        assert auto_import_utils.user_import_dir("alice") == (import_root / "alice").resolve()

    @pytest.mark.parametrize("username", ["", ".", "..", "../bob", "a/b"])
    def test_rejects_names_escaping_root(self, import_root, username):
        with pytest.raises(ValueError):
            auto_import_utils.user_import_dir(username)

    def test_relative_folder(self, import_root):
        assert auto_import_utils.relative_folder("alice") == "auto_import/alice"


class TestListPendingFiles:
    def test_missing_folder_is_empty(self, tmp_path):
        assert auto_import_utils.list_pending_files(tmp_path / "nope") == []

    def test_filters_and_orders_oldest_first(self, tmp_path):
        newer = _write(tmp_path / "b.GPX", age_seconds=600)
        older = _write(tmp_path / "a.fit", age_seconds=1200)
        _write(tmp_path / "notes.txt")
        _write(tmp_path / "copying.tcx", age_seconds=5)
        (tmp_path / "sub.fit").mkdir()

        assert auto_import_utils.list_pending_files(tmp_path) == [older, newer]


class TestIsDue:
    NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)

    def test_disabled_never_due(self):
        assert not auto_import_utils.is_due(_settings(enabled=False), self.NOW)

    def test_never_run_is_due(self):
        assert auto_import_utils.is_due(_settings(), self.NOW)

    def test_due_after_interval(self):
        assert auto_import_utils.is_due(_settings(last_run_at=self.NOW - timedelta(minutes=60)), self.NOW)
        assert not auto_import_utils.is_due(_settings(last_run_at=self.NOW - timedelta(minutes=59)), self.NOW)

    def test_naive_timestamp_treated_as_utc(self):
        naive = (self.NOW - timedelta(minutes=61)).replace(tzinfo=None)
        assert auto_import_utils.is_due(_settings(last_run_at=naive), self.NOW)


class TestBuildSettingsRead:
    def test_defaults_when_unsaved(self, import_root):
        (import_root / "alice").mkdir()
        _write(import_root / "alice" / "a.fit")

        result = auto_import_utils.build_settings_read("alice", None)

        assert result.enabled is False
        assert result.interval_minutes == auto_import_schema.DEFAULT_INTERVAL_MINUTES
        assert result.folder == "auto_import/alice"
        assert result.pending_files == 1

    def test_unusable_username_reports_no_pending(self, import_root):
        assert auto_import_utils.build_settings_read("..", _settings()).pending_files == 0


class TestCrud:
    def test_upsert_creates_then_updates(self, sqlite_db):
        update = auto_import_schema.AutoImportSettingsUpdate(enabled=True, interval_minutes=30)
        created = auto_import_crud.upsert_settings(1, update, sqlite_db)
        updated = auto_import_crud.upsert_settings(
            1, auto_import_schema.AutoImportSettingsUpdate(enabled=False, interval_minutes=1440), sqlite_db
        )

        assert created.id == updated.id
        assert (updated.enabled, updated.interval_minutes) == (False, 1440)

    def test_get_enabled_settings(self, sqlite_db):
        auto_import_crud.upsert_settings(1, auto_import_schema.AutoImportSettingsUpdate(enabled=True), sqlite_db)
        auto_import_crud.upsert_settings(2, auto_import_schema.AutoImportSettingsUpdate(enabled=False), sqlite_db)

        assert [s.user_id for s in auto_import_crud.get_enabled_settings(sqlite_db)] == [1]

    def test_record_run_without_row_is_noop(self, sqlite_db):
        auto_import_crud.record_run(9, datetime.now(UTC), 1, 0, sqlite_db)
        assert auto_import_crud.get_settings_by_user_id(9, sqlite_db) is None


@contextmanager
def _job_env(sqlite_db, username="alice"):
    @contextmanager
    def _session():
        yield sqlite_db

    with (
        patch.object(auto_import_utils.core_database, "SessionLocal", _session),
        patch.object(
            auto_import_utils.users_crud,
            "get_user_by_id",
            return_value=SimpleNamespace(id=1, username=username),
        ),
        patch.object(auto_import_utils.core_file_uploads, "validate_local_file", new=AsyncMock()) as validate,
        patch.object(
            auto_import_utils.activities_utils, "parse_and_store_activity_from_file", new=AsyncMock()
        ) as parse,
    ):
        yield validate, parse


class TestRunUserAutoImport:
    def test_imports_pending_files_and_records_run(self, sqlite_db, import_root):
        auto_import_crud.upsert_settings(1, auto_import_schema.AutoImportSettingsUpdate(enabled=True), sqlite_db)
        folder = import_root / "alice"
        folder.mkdir()
        good = _write(folder / "good.fit", age_seconds=1200)
        bad = _write(folder / "bad.gpx", age_seconds=600)

        with _job_env(sqlite_db) as (_, parse):
            parse.side_effect = [[object()], None]
            result = auto_import_utils.run_user_auto_import(1)

        assert result == (1, 1)
        assert [call.args[1] for call in parse.call_args_list] == [str(good), str(bad)]
        assert all(call.kwargs["is_bulk_import"] for call in parse.call_args_list)
        stored = auto_import_crud.get_settings_by_user_id(1, sqlite_db)
        assert (stored.last_run_imported, stored.last_run_failed) == (1, 1)
        assert stored.last_run_at is not None

    def test_invalid_file_moved_to_errors(self, sqlite_db, import_root, tmp_path):
        folder = import_root / "alice"
        folder.mkdir()
        _write(folder / "fake.fit")

        with _job_env(sqlite_db) as (validate, parse):
            validate.side_effect = HTTPException(status_code=400, detail="bad content")
            result = auto_import_utils.run_user_auto_import(1)

        assert result == (0, 1)
        parse.assert_not_called()
        assert (tmp_path / "import_errors" / "fake.fit").exists()
        assert not (folder / "fake.fit").exists()

    def test_creates_missing_folder(self, sqlite_db, import_root):
        with _job_env(sqlite_db):
            assert auto_import_utils.run_user_auto_import(1) == (0, 0)
        assert (import_root / "alice").is_dir()

    def test_skips_when_already_running(self, sqlite_db, import_root):
        auto_import_utils._running_user_ids.add(1)
        try:
            with _job_env(sqlite_db) as (_, parse):
                assert auto_import_utils.run_user_auto_import(1) is None
            parse.assert_not_called()
        finally:
            auto_import_utils._running_user_ids.discard(1)

    def test_running_flag_cleared_after_error(self, sqlite_db, import_root):
        with _job_env(sqlite_db), patch.object(auto_import_utils, "list_pending_files", side_effect=OSError("boom")):
            assert auto_import_utils.run_user_auto_import(1) is None
        assert not auto_import_utils.is_running(1)


class TestRunDueAutoImports:
    def test_runs_only_due_users(self, sqlite_db):
        now = datetime.now(UTC)
        sqlite_db.add_all(
            [
                _settings(user_id=1),
                _settings(user_id=2, last_run_at=now - timedelta(minutes=5)),
                _settings(user_id=3, enabled=False),
            ]
        )
        sqlite_db.commit()

        @contextmanager
        def _session():
            yield sqlite_db

        with (
            patch.object(auto_import_utils.core_database, "SessionLocal", _session),
            patch.object(auto_import_utils, "run_user_auto_import") as run_user,
        ):
            auto_import_utils.run_due_auto_imports()

        run_user.assert_called_once_with(1)
