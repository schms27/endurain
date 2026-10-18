"""CRUD operations for scheduled auto import settings."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import activities.activity_auto_import.models as auto_import_models
import activities.activity_auto_import.schema as auto_import_schema
import core.decorators as core_decorators


@core_decorators.handle_db_errors
def get_settings_by_user_id(
    user_id: int,
    db: Session,
) -> auto_import_models.UsersAutoImportSettings | None:
    """
    Retrieve a user's auto import settings row.

    Args:
        user_id: Owner user ID.
        db: Database session.

    Returns:
        The settings row, or None when the user never saved any.
    """
    stmt = select(auto_import_models.UsersAutoImportSettings).where(
        auto_import_models.UsersAutoImportSettings.user_id == user_id
    )
    return db.execute(stmt).scalar_one_or_none()


@core_decorators.handle_db_errors
def get_enabled_settings(db: Session) -> list[auto_import_models.UsersAutoImportSettings]:
    """
    Retrieve every enabled settings row.

    Args:
        db: Database session.

    Returns:
        Enabled settings rows.
    """
    stmt = select(auto_import_models.UsersAutoImportSettings).where(
        auto_import_models.UsersAutoImportSettings.enabled.is_(True)
    )
    return list(db.execute(stmt).scalars().all())


@core_decorators.handle_db_errors
def upsert_settings(
    user_id: int,
    settings: auto_import_schema.AutoImportSettingsUpdate,
    db: Session,
) -> auto_import_models.UsersAutoImportSettings:
    """
    Create or update a user's auto import settings.

    Args:
        user_id: Owner user ID.
        settings: New settings.
        db: Database session.

    Returns:
        The saved settings row.
    """
    db_settings = get_settings_by_user_id(user_id, db)
    if db_settings is None:
        db_settings = auto_import_models.UsersAutoImportSettings(user_id=user_id)
        db.add(db_settings)

    db_settings.enabled = settings.enabled
    db_settings.interval_minutes = settings.interval_minutes

    db.commit()
    db.refresh(db_settings)
    return db_settings


@core_decorators.handle_db_errors
def record_run(
    user_id: int,
    started_at: datetime,
    imported: int,
    failed: int,
    db: Session,
) -> None:
    """
    Store the outcome of a scan on the user's settings row.

    Does nothing when the user has no settings row.

    Args:
        user_id: Owner user ID.
        started_at: When the scan started.
        imported: Files imported.
        failed: Files that failed.
        db: Database session.
    """
    db_settings = get_settings_by_user_id(user_id, db)
    if db_settings is None:
        return

    db_settings.last_run_at = started_at
    db_settings.last_run_imported = imported
    db_settings.last_run_failed = failed
    db.commit()
