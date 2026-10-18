"""Scan per-user import folders and import new activity files."""

import asyncio
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

import activities.activity.utils as activities_utils
import activities.activity_auto_import.crud as auto_import_crud
import activities.activity_auto_import.models as auto_import_models
import activities.activity_auto_import.schema as auto_import_schema
import core.config as core_config
import core.database as core_database
import core.file_uploads as core_file_uploads
import core.logger as core_logger
import users.users.crud as users_crud
import websocket.manager as websocket_manager

# Files touched more recently than this may still be being copied in.
FILE_SETTLE_SECONDS = 60

_running_user_ids: set[int] = set()
_running_lock = threading.Lock()


def user_import_dir(username: str) -> Path:
    """
    Return the import folder for a username.

    Args:
        username: The user's username.

    Returns:
        ``<FILES_AUTO_IMPORT_DIR>/<username>``.

    Raises:
        ValueError: If the username would escape the auto import root.
    """
    root = Path(core_config.FILES_AUTO_IMPORT_DIR).resolve()
    folder = (root / username).resolve()
    if username in ("", ".", "..") or folder.parent != root:
        raise ValueError(f"Username {username!r} is not usable as a folder name")
    return folder


def relative_folder(username: str) -> str:
    """
    Return the import folder relative to the files directory, for display.

    Args:
        username: The user's username.

    Returns:
        A path such as ``auto_import/alice``.
    """
    root = Path(core_config.FILES_AUTO_IMPORT_DIR)
    return f"{root.name}/{username}"


def list_pending_files(folder: Path, now: float | None = None) -> list[Path]:
    """
    List supported activity files ready to import, oldest first.

    Skips subfolders, unsupported extensions and files modified less
    than ``FILE_SETTLE_SECONDS`` ago (likely still being copied).

    Args:
        folder: Folder to scan.
        now: Current epoch time; defaults to ``time.time()``.

    Returns:
        Paths of files to import.
    """
    if not folder.is_dir():
        return []
    now = time.time() if now is None else now
    pending: list[tuple[float, Path]] = []
    for entry in folder.iterdir():
        if not entry.is_file() or entry.suffix.lower() not in core_config.SUPPORTED_FILE_FORMATS:
            continue
        mtime = entry.stat().st_mtime
        if now - mtime < FILE_SETTLE_SECONDS:
            continue
        pending.append((mtime, entry))
    return [path for _, path in sorted(pending)]


def build_settings_read(
    username: str,
    db_settings: auto_import_models.UsersAutoImportSettings | None,
) -> auto_import_schema.AutoImportSettingsRead:
    """
    Build the API view of a user's settings, with defaults when unsaved.

    Args:
        username: The user's username.
        db_settings: Stored settings, or None.

    Returns:
        Settings, folder and pending-file count.
    """
    try:
        pending = len(list_pending_files(user_import_dir(username)))
    except (OSError, ValueError):
        pending = 0

    if db_settings is None:
        return auto_import_schema.AutoImportSettingsRead(
            enabled=False,
            interval_minutes=auto_import_schema.DEFAULT_INTERVAL_MINUTES,
            folder=relative_folder(username),
            pending_files=pending,
        )
    return auto_import_schema.AutoImportSettingsRead(
        enabled=db_settings.enabled,
        interval_minutes=db_settings.interval_minutes,
        folder=relative_folder(username),
        pending_files=pending,
        last_run_at=db_settings.last_run_at,
        last_run_imported=db_settings.last_run_imported,
        last_run_failed=db_settings.last_run_failed,
    )


def ensure_user_import_dir(username: str) -> None:
    """
    Create the user's import folder if missing; log and continue on failure.

    Args:
        username: The user's username.
    """
    try:
        user_import_dir(username).mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as err:
        core_logger.print_to_log(
            f"Auto import: could not create import folder for {username!r}: {err}",
            "warning",
            exc=err,
        )


def is_due(
    db_settings: auto_import_models.UsersAutoImportSettings,
    now: datetime,
) -> bool:
    """
    Whether a user's next scan is due.

    Args:
        db_settings: The user's settings.
        now: Current aware UTC time.

    Returns:
        True when enabled and never run, or the interval has elapsed.
    """
    if not db_settings.enabled:
        return False
    last_run_at = db_settings.last_run_at
    if last_run_at is None:
        return True
    if last_run_at.tzinfo is None:
        last_run_at = last_run_at.replace(tzinfo=UTC)
    return now - last_run_at >= timedelta(minutes=db_settings.interval_minutes)


def is_running(user_id: int) -> bool:
    """
    Whether an import for this user is in progress.

    Args:
        user_id: User ID.

    Returns:
        True while a scan for the user runs.
    """
    with _running_lock:
        return user_id in _running_user_ids


def _move_to_errors(file_path: Path) -> None:
    error_dir = core_config.FILES_BULK_IMPORT_IMPORT_ERRORS_DIR
    try:
        os.makedirs(error_dir, exist_ok=True)
        core_file_uploads.move_within(str(file_path), error_dir, filename=file_path.name)
    except (OSError, HTTPException) as err:
        core_logger.print_to_log(
            f"Auto import: could not move rejected file {file_path} to {error_dir}",
            "error",
            exc=err,
        )


async def _import_files(
    user_id: int,
    files: list[Path],
    ws_manager: websocket_manager.WebSocketManager,
    db: Session,
) -> tuple[int, int]:
    import_time = datetime.now(UTC).isoformat()
    imported = failed = 0
    for file_path in files:
        kind = (
            core_file_uploads.UploadKind.GZIP
            if file_path.suffix.lower() == ".gz"
            else core_file_uploads.UploadKind.ACTIVITY
        )
        try:
            await core_file_uploads.validate_local_file(file_path, kind=kind)
        except HTTPException as err:
            core_logger.print_to_log_and_console(
                f"Auto import: rejecting {file_path}: {err.detail}",
                "warning",
            )
            _move_to_errors(file_path)
            failed += 1
            continue

        # Failures are logged and the file moved to import_errors
        # by parse_and_store_activity_from_file; it returns None.
        result = await activities_utils.parse_and_store_activity_from_file(
            user_id,
            str(file_path),
            ws_manager,
            db,
            is_bulk_import=True,
            import_initiated_time=import_time,
        )
        if result:
            imported += 1
        else:
            failed += 1
    return imported, failed


def run_user_auto_import(user_id: int) -> tuple[int, int] | None:
    """
    Import every pending file from one user's folder.

    Blocking; call from a worker thread (the scheduler's executor).
    Skips the user when a scan for them is already running.

    Args:
        user_id: User ID.

    Returns:
        ``(imported, failed)`` counts, or None when skipped.
    """
    with _running_lock:
        if user_id in _running_user_ids:
            return None
        _running_user_ids.add(user_id)

    started_at = datetime.now(UTC)
    try:
        with core_database.SessionLocal() as db:
            user = users_crud.get_user_by_id(user_id, db)
            if user is None:
                return None
            try:
                folder = user_import_dir(user.username)
            except ValueError as err:
                core_logger.print_to_log(f"Auto import: {err}", "warning")
                return None

            folder.mkdir(parents=True, exist_ok=True)
            files = list_pending_files(folder)
            imported = failed = 0
            if files:
                core_logger.print_to_log_and_console(
                    f"Auto import: {len(files)} file(s) found for user {user_id} in {folder}",
                    "info",
                )
                imported, failed = asyncio.run(
                    _import_files(user_id, files, websocket_manager.get_websocket_manager(), db)
                )
                core_logger.print_to_log_and_console(
                    f"Auto import for user {user_id} done: {imported} imported, {failed} failed",
                    "info",
                )
            auto_import_crud.record_run(user_id, started_at, imported, failed, db)
            return imported, failed
    except Exception as err:
        core_logger.print_to_log(
            f"Auto import for user {user_id} failed: {err}",
            "error",
            exc=err,
        )
        return None
    finally:
        with _running_lock:
            _running_user_ids.discard(user_id)


def run_due_auto_imports() -> None:
    """
    Scheduler entry point: scan the folder of every user whose next run is due.

    Returns:
        None.
    """
    now = datetime.now(UTC)
    with core_database.SessionLocal() as db:
        due_user_ids = [s.user_id for s in auto_import_crud.get_enabled_settings(db) if is_due(s, now)]

    for user_id in due_user_ids:
        run_user_auto_import(user_id)
