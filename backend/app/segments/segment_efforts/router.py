"""Segment effort API endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session

import activities.activity.dependencies as activities_dependencies
import auth.dependencies as auth_dependencies
import core.database as core_database
import segments.segment_efforts.crud as segment_efforts_crud
import segments.segment_efforts.schema as segment_efforts_schema

router = APIRouter()


@router.get(
    "/activity_id/{activity_id}",
    response_model=list[segment_efforts_schema.SegmentEffortRead],
)
async def read_activity_segment_efforts(
    activity_id: int,
    _validate_activity_id: Annotated[Callable, Depends(activities_dependencies.validate_activity_id)],
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> list[segment_efforts_schema.SegmentEffortRead]:
    """
    Segment efforts of an activity you can see.

    Args:
        activity_id: Activity ID.
        _validate_activity_id: Activity ID validator dependency.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        Efforts in start-time order (with personal ranks for the owner).
    """
    return segment_efforts_crud.get_activity_efforts(activity_id, token_user_id, db)


@router.patch(
    "/{effort_id}",
    response_model=segment_efforts_schema.SegmentEffortRead,
)
async def edit_segment_effort(
    effort_id: int,
    edit: segment_efforts_schema.SegmentEffortEdit,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> segment_efforts_schema.SegmentEffortRead:
    """
    Exclude or restore one of your efforts.

    Args:
        effort_id: Effort ID.
        edit: New exclusion state.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The updated effort.
    """
    return segment_efforts_crud.set_effort_excluded(effort_id, token_user_id, edit.is_excluded, db)
