from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.link_service import (
    ShortLinkNotFound,
    create_short_link,
    find_short_link,
    make_short_url,
)
from url_shortener.models import ShortLink
from url_shortener.schemas import (
    ShortLinkCreateRequest,
    ShortLinkCreateResponse,
)

router = APIRouter(tags=["links"])


@router.get("/{code}", response_class=RedirectResponse)
async def redirect_to_destination(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    destination_url, _link_id = await find_short_link(
        session,
        request.app.state.redis,
        code,
        request.app.state.settings,
    )
    if destination_url is None:
        raise ShortLinkNotFound
    return RedirectResponse(
        destination_url,
        status_code=status.HTTP_302_FOUND,
    )


@router.post(
    "/api/v1/shorten",
    response_model=ShortLinkCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_link(
    payload: ShortLinkCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ShortLinkCreateResponse:
    settings: Settings = request.app.state.settings
    link: ShortLink = await create_short_link(
        session,
        request.app.state.redis,
        str(payload.destination_url),
        settings,
    )
    return ShortLinkCreateResponse(
        code=link.code,
        short_url=make_short_url(settings, link.code),
        created_at=link.created_at,
    )
