"""Scheduled auto import API endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm import Session

import activities.activity_auto_import.crud as auto_import_crud
import activities.activity_auto_import.schema as auto_import_schema
import activities.activity_auto_import.utils as auto_import_utils
import auth.dependencies as auth_dependencies
import core.database as core_database
import core.scheduler as core_scheduler
import users.users.crud as users_crud

# Define the API router
router = APIRouter()


def _get_username_or_404(user_id: int, db: Session) -> str:
    user = users_crud.get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user.username


@router.get(
    "",
    response_model=auto_import_schema.AutoImportSettingsRead,
    status_code=status.HTTP_200_OK,
)
async def read_auto_import_settings(
    token_user_id: Annotated[
        int,
        Depends(auth_dependencies.get_sub_from_access_token),
    ],
    db: Annotated[
        Session,
        Depends(core_database.get_db),
    ],
) -> auto_import_schema.AutoImportSettingsRead:
    """
    Retrieve the authenticated user's auto import settings and status.

    Args:
        token_user_id: User ID from access token.
        db: Database session dependency.

    Returns:
        Settings (defaults when never saved), folder and last-run status.
    """
    username = _get_username_or_404(token_user_id, db)
    db_settings = auto_import_crud.get_settings_by_user_id(token_user_id, db)
    return auto_import_utils.build_settings_read(username, db_settings)


@router.put(
    "",
    response_model=auto_import_schema.AutoImportSettingsRead,
    status_code=status.HTTP_200_OK,
)
async def edit_auto_import_settings(
    settings: auto_import_schema.AutoImportSettingsUpdate,
    token_user_id: Annotated[
        int,
        Depends(auth_dependencies.get_sub_from_access_token),
    ],
    db: Annotated[
        Session,
        Depends(core_database.get_db),
    ],
) -> auto_import_schema.AutoImportSettingsRead:
    """
    Update the authenticated user's auto import settings.

    Creates the user's import folder when enabling.

    Args:
        settings: New settings.
        token_user_id: User ID from access token.
        db: Database session dependency.

    Returns:
        The saved settings and status.
    """
    username = _get_username_or_404(token_user_id, db)
    db_settings = auto_import_crud.upsert_settings(token_user_id, settings, db)
    if db_settings.enabled:
        auto_import_utils.ensure_user_import_dir(username)
    return auto_import_utils.build_settings_read(username, db_settings)


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict[str, str],
)
async def run_auto_import_now(
    token_user_id: Annotated[
        int,
        Depends(auth_dependencies.get_sub_from_access_token),
    ],
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["activities:write"])],
) -> dict[str, str]:
    """
    Scan the authenticated user's import folder now, in the background.

    Works whether or not the schedule is enabled.

    Args:
        token_user_id: User ID from access token.
        _check_scopes: Scope validation dependency.

    Returns:
        Confirmation that the scan was queued.

    Raises:
        HTTPException: 409 if a scan for this user is already running.
    """
    if auto_import_utils.is_running(token_user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An import of your folder is already running",
        )
    core_scheduler.schedule_user_auto_import(token_user_id)
    return {"detail": "Import of your folder started"}
