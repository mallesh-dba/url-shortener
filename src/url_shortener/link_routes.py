from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.link_service import create_short_link, make_short_url
from url_shortener.models import ShortLink
from url_shortener.schemas import (
    ShortLinkCreateRequest,
    ShortLinkCreateResponse,
)

router = APIRouter(tags=["links"])


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
