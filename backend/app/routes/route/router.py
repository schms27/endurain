"""Planned route API endpoints."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Security, UploadFile, status
from sqlalchemy.orm import Session

import activities.activity.dependencies as activities_dependencies
import auth.dependencies as auth_dependencies
import core.database as core_database
import core.file_uploads as core_file_uploads
import routes.constants as routes_constants
import routes.route.crud as route_crud
import routes.route.export as route_export
import routes.route.public_router as route_public_router
import routes.route.schema as route_schema

router = APIRouter()
# Mounted under /users: the routes listed on a user's profile.
user_router = APIRouter()


async def _read_route_file(file: UploadFile) -> tuple[bytes, str]:
    """
    Validate an uploaded route file and read it into memory.

    Args:
        file: The uploaded file.

    Returns:
        Tuple of (contents, lowercase extension).

    Raises:
        HTTPException: 400 for an unsupported type or failed validation,
            413 when the file is too large.
    """
    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in routes_constants.ROUTE_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported route file type. Accepted: .gpx, .tcx, .fit",
        )
    await core_file_uploads.validate_upload(file, kind=core_file_uploads.UploadKind.ACTIVITY)
    data = await file.read(routes_constants.MAX_ROUTE_FILE_BYTES + 1)
    if len(data) > routes_constants.MAX_ROUTE_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Route file is too large")
    return data, extension


@router.post(
    "/import",
    response_model=route_schema.RouteRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_route(
    file: UploadFile,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Import a route from a GPX, TCX or FIT file.

    Args:
        file: The route file.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The created route.
    """
    data, extension = await _read_route_file(file)
    return route_crud.import_route(token_user_id, data, file.filename or "", extension, db)


@router.post(
    "/from_activity/{activity_id}",
    response_model=route_schema.RouteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_route_from_activity(
    activity_id: int,
    request: route_schema.RouteFromActivity,
    _validate_activity_id: Annotated[Callable, Depends(activities_dependencies.validate_activity_id)],
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Save (part of) one of your activities as a route.

    Args:
        activity_id: Source activity ID.
        request: Optional name and slice.
        _validate_activity_id: Activity ID validator dependency.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The created route.
    """
    return route_crud.create_route_from_activity(token_user_id, activity_id, request, db)


@router.get("", response_model=route_schema.RoutesPage)
async def list_routes(
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
    q: Annotated[str | None, Query(max_length=250)] = None,
    activity_type: Annotated[int | None, Query(gt=0)] = None,
    page_number: Annotated[int, Query(ge=1)] = 1,
    num_records: Annotated[int, Query(ge=1, le=100)] = 25,
) -> route_schema.RoutesPage:
    """
    List your routes, newest first.

    Args:
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.
        q: Name search.
        activity_type: Only routes for this activity type.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        One page of routes and the total count.
    """
    return route_crud.list_routes(
        token_user_id,
        db,
        query=q,
        activity_type=activity_type,
        page_number=page_number,
        num_records=num_records,
    )


@router.get("/{route_id}", response_model=route_schema.RouteRead)
async def read_route(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Get a route you own or can see (trimmed for non-owners).

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The route.
    """
    return route_crud.get_route(route_id, token_user_id, db)


@router.put("/{route_id}", response_model=route_schema.RouteRead)
async def edit_route(
    route_id: int,
    edit: route_schema.RouteEdit,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Edit one of your routes.

    Args:
        route_id: Route ID.
        edit: Changes to apply.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The updated route.
    """
    return route_crud.edit_route(route_id, token_user_id, edit, db)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_route(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> None:
    """
    Delete one of your routes.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        None.
    """
    route_crud.delete_route(route_id, token_user_id, db)


@router.get(
    "/{route_id}/export",
    response_class=Response,
    responses={200: {"content": {"application/gpx+xml": {}}}},
)
async def export_route(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
    export_format: Annotated[Literal["gpx"], Query(alias="format")] = "gpx",
) -> Response:
    """
    Download a route you can see as a file for a device or another app.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.
        export_format: Output format (GPX only for now).

    Returns:
        The file as an attachment, trimmed for non-owners.
    """
    return route_export.gpx_response(route_crud.get_route(route_id, token_user_id, db))


@router.post(
    "/{route_id}/copy",
    response_model=route_schema.RouteRead,
    status_code=status.HTTP_201_CREATED,
)
async def copy_route(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Save a route you can see to your routes, as a private copy.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The new route.
    """
    route = route_crud.get_visible_route_model(route_id, token_user_id, db)
    return route_crud.copy_route(route, token_user_id, db)


@router.post(
    "/shared/{token}/copy",
    response_model=route_schema.RouteRead,
    status_code=status.HTTP_201_CREATED,
)
async def copy_shared_route(
    token: route_public_router.ShareToken,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Save a route shared with you by link to your routes, as a private copy.

    Args:
        token: Share token from the link.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The new route.
    """
    route = route_crud.get_shared_route_model(token, db)
    return route_crud.copy_route(route, token_user_id, db)


@router.post("/{route_id}/share_token", response_model=route_schema.RouteRead)
async def create_share_token(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Create or rotate the unlisted share link of one of your routes.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The route with its new share token.
    """
    return route_crud.create_share_token(route_id, token_user_id, db)


@router.delete("/{route_id}/share_token", response_model=route_schema.RouteRead)
async def revoke_share_token(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:write"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteRead:
    """
    Revoke the unlisted share link of one of your routes.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        The route without a share token.
    """
    return route_crud.revoke_share_token(route_id, token_user_id, db)


@router.get("/{route_id}/home_warning", response_model=route_schema.RouteHomeWarning)
async def read_home_warning(
    route_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.RouteHomeWarning:
    """
    Check whether one of your routes starts or ends near where many of your
    activities start, which may reveal where you live.

    Args:
        route_id: Route ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.

    Returns:
        Which visible endpoints are flagged.
    """
    return route_crud.home_location_warning(route_id, token_user_id, db)


@user_router.get("/{user_id}/routes", response_model=route_schema.RoutesPage)
async def list_user_routes(
    user_id: int,
    _check_scopes: Annotated[Callable, Security(auth_dependencies.check_scopes, scopes=["routes:read"])],
    token_user_id: Annotated[int, Depends(auth_dependencies.get_sub_from_access_token)],
    db: Annotated[Session, Depends(core_database.get_db)],
    page_number: Annotated[int, Query(ge=1)] = 1,
    num_records: Annotated[int, Query(ge=1, le=100)] = 25,
) -> route_schema.RoutesPage:
    """
    List a user's routes that you can see, newest first.

    Args:
        user_id: Profile user ID.
        _check_scopes: Scope authorization dependency.
        token_user_id: Authenticated user ID.
        db: Database session.
        page_number: 1-based page number.
        num_records: Page size.

    Returns:
        One page of routes and the total count.
    """
    return route_crud.list_user_routes(
        user_id,
        token_user_id,
        db,
        page_number=page_number,
        num_records=num_records,
    )
