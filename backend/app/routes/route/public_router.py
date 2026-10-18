"""Public (unauthenticated) planned route endpoints.

Gated by the ``public_shareable_links`` server setting. Every response is
the non-owner view: owner-only fields removed and endpoints trimmed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.orm import Session

import core.database as core_database
import routes.route.crud as route_crud
import routes.route.export as route_export
import routes.route.schema as route_schema

router = APIRouter()

ShareToken = Annotated[str, Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
_GPX_RESPONSES: dict[int | str, dict] = {200: {"content": {"application/gpx+xml": {}}}}


@router.get("/by_token/{token}", response_model=route_schema.PublicRouteRead)
async def read_shared_route(
    token: ShareToken,
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.PublicRouteRead:
    """
    Get a route shared through an unlisted link.

    Args:
        token: Share token from the link.
        db: Database session.

    Returns:
        The route as a non-owner sees it.
    """
    return route_crud.present_public_route(route_crud.get_shared_route_model(token, db), db)


@router.get("/by_token/{token}/export", response_class=Response, responses=_GPX_RESPONSES)
async def export_shared_route(
    token: ShareToken,
    db: Annotated[Session, Depends(core_database.get_db)],
) -> Response:
    """
    Download a route shared through an unlisted link as GPX.

    Args:
        token: Share token from the link.
        db: Database session.

    Returns:
        The GPX file as an attachment.
    """
    route = route_crud.get_shared_route_model(token, db)
    return route_export.gpx_response(route_crud.present_route(route, is_owner=False))


@router.get("/{route_id}", response_model=route_schema.PublicRouteRead)
async def read_public_route(
    route_id: int,
    db: Annotated[Session, Depends(core_database.get_db)],
) -> route_schema.PublicRouteRead:
    """
    Get a public route.

    Args:
        route_id: Route ID.
        db: Database session.

    Returns:
        The route as a non-owner sees it.
    """
    return route_crud.present_public_route(route_crud.get_public_route_model(route_id, db), db)


@router.get("/{route_id}/export", response_class=Response, responses=_GPX_RESPONSES)
async def export_public_route(
    route_id: int,
    db: Annotated[Session, Depends(core_database.get_db)],
) -> Response:
    """
    Download a public route as GPX.

    Args:
        route_id: Route ID.
        db: Database session.

    Returns:
        The GPX file as an attachment.
    """
    route = route_crud.get_public_route_model(route_id, db)
    return route_export.gpx_response(route_crud.present_route(route, is_owner=False))
