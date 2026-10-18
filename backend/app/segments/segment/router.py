"""Segment API endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from sqlalchemy.orm import Session

import auth.dependencies as auth_dependencies
import core.database as core_database
import core.geo as core_geo
import segments.constants as segments_constants
import segments.segment.crud as segment_crud
import segments.segment.schema as segment_schema
import segments.segment_efforts.crud as segment_efforts_crud
import segments.segment_efforts.schema as segment_efforts_schema

router = APIRouter()


@router.post(
    "",
    response_model=segment_schema.SegmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_segment(
    segment: segment_schema.SegmentCreate,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> segment_schema.SegmentRead:
    """
    Create a segment from a slice of one of your activities.

    Existing activities are matched against it in the background.

    Args:
        segment: Creation request.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The created segment.
    """
    return segment_crud.create_segment(token_user_id, segment, db)


@router.get(
    "",
    response_model=list[segment_schema.SegmentSummary],
)
async def list_segments(
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
    sport_group: Annotated[segments_constants.SportGroup | None, Query()] = None,
    created_by_me: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=250)] = None,
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    page_number: Annotated[int, Query(ge=1)] = 1,
    num_records: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[segment_schema.SegmentSummary]:
    """
    List segments visible to you.

    Args:
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.
        sport_group: Only this sport group.
        created_by_me: Only segments you created.
        q: Name search.
        min_lat: Bounding box southern edge (all four or none).
        min_lon: Bounding box western edge.
        max_lat: Bounding box northern edge.
        max_lon: Bounding box eastern edge.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        Matching segments, newest first.

    Raises:
        HTTPException: 400 when only part of the bounding box is given.
    """
    edges = (min_lat, min_lon, max_lat, max_lon)
    bbox: core_geo.BoundingBox | None = None
    if any(edge is not None for edge in edges):
        if min_lat is None or min_lon is None or max_lat is None or max_lon is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide all of min_lat, min_lon, max_lat and max_lon",
            )
        bbox = core_geo.BoundingBox(min_lat, min_lon, max_lat, max_lon)
    return segment_crud.list_segments(
        token_user_id,
        db,
        sport_group=sport_group,
        created_by_me=created_by_me,
        bbox=bbox,
        query=q,
        page_number=page_number,
        num_records=num_records,
    )


@router.get(
    "/{segment_id}",
    response_model=segment_schema.SegmentRead,
)
async def read_segment(
    segment_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> segment_schema.SegmentRead:
    """
    Get a segment.

    Args:
        segment_id: Segment ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The segment.

    Raises:
        HTTPException: 404 if missing or not visible.
    """
    segment = segment_crud.get_segment_visible_to_user(segment_id, token_user_id, db)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return segment


@router.put(
    "/{segment_id}",
    response_model=segment_schema.SegmentRead,
)
async def edit_segment(
    segment_id: int,
    edit: segment_schema.SegmentEdit,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> segment_schema.SegmentRead:
    """
    Edit one of your segments.

    Args:
        segment_id: Segment ID.
        edit: Changes to apply.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The updated segment.
    """
    return segment_crud.edit_segment(segment_id, token_user_id, edit, db)


@router.delete(
    "/{segment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_segment(
    segment_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> None:
    """
    Delete one of your segments and its efforts.

    Args:
        segment_id: Segment ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        None.
    """
    segment_crud.delete_segment(segment_id, token_user_id, db)


@router.get(
    "/{segment_id}/efforts",
    response_model=list[segment_efforts_schema.SegmentEffortRead],
)
async def read_my_segment_efforts(
    segment_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> list[segment_efforts_schema.SegmentEffortRead]:
    """
    Your efforts on a segment, fastest first.

    Args:
        segment_id: Segment ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        Your efforts with personal ranks.

    Raises:
        HTTPException: 404 if the segment is missing or not visible.
    """
    if segment_crud.get_segment_visible_to_user(segment_id, token_user_id, db) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return segment_efforts_crud.get_user_segment_efforts(segment_id, token_user_id, db)


@router.post(
    "/{segment_id}/rematch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def rematch_segment(
    segment_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["segments:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> None:
    """
    Queue a full rematch of one of your segments.

    Args:
        segment_id: Segment ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        None.
    """
    segment_crud.request_rematch(segment_id, token_user_id, db)
