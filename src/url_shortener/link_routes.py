from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.analytics import publish_click_event
from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.link_service import (
    ShortLinkNotFound,
    create_short_link,
    find_short_link,
    get_link_analytics,
    make_short_url,
)
from url_shortener.models import ShortLink
from url_shortener.schemas import (
    LinkAnalyticsResponse,
    ShortLinkCreateRequest,
    ShortLinkCreateResponse,
)

router = APIRouter(tags=["links"])


@router.get(
    "/api/v1/links/{code}/analytics",
    response_model=LinkAnalyticsResponse,
)
async def get_link_analytics_endpoint(
    code: str,
    session: AsyncSession = Depends(get_session),
) -> LinkAnalyticsResponse:
    analytics_code, clicks_total = await get_link_analytics(session, code)
    return LinkAnalyticsResponse(
        code=analytics_code,
        clicks_total=clicks_total,
    )


@router.get("/{code}", response_class=RedirectResponse)
async def redirect_to_destination(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    destination_url, link_id = await find_short_link(
        session,
        request.app.state.redis,
        code,
        request.app.state.settings,
    )
    if destination_url is None:
        raise ShortLinkNotFound
    if link_id is None:
        raise RuntimeError("Resolved short link is missing its database ID")
    background_tasks.add_task(
        publish_click_event,
        request.app.state.redis,
        link_id,
        request.app.state.settings.analytics_stream_name,
    )
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
