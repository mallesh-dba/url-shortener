import asyncio
import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from url_shortener.config import Settings, get_settings
from url_shortener.main import create_app
from url_shortener.models import ClickEvent, ShortLink

pytestmark = pytest.mark.skipif(
    os.getenv("URL_SHORTENER_RUN_INTEGRATION") != "1",
    reason="Set URL_SHORTENER_RUN_INTEGRATION=1 to use configured PostgreSQL and Redis",
)


def integration_settings() -> Settings:
    configured = get_settings()
    return configured.model_copy(
        update={
            "analytics_stream_name": f"clicks:t109:{uuid4().hex}",
            "api_metrics_port": 0,
        }
    )


async def assert_persisted_and_published(
    settings: Settings,
    code: str,
) -> None:
    redis_client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
    )
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )
    try:
        cache_value = await redis_client.get(f"short:v1:{code}")
        assert cache_value is not None
        assert json.loads(cache_value)["destination_url"] == (
            "https://example.com/t109-integration"
        )

        stream_entries = await redis_client.xrevrange(
            settings.analytics_stream_name,
            max="+",
            min="-",
            count=1,
        )
        assert len(stream_entries) == 1
        _, fields = stream_entries[0]
        assert set(fields) == {"event_id", "link_id", "clicked_at"}

        async with engine.connect() as connection:
            result = await connection.execute(
                select(
                    ShortLink.id,
                    ShortLink.code,
                    ShortLink.destination_url,
                    ShortLink.clicks_total,
                ).where(ShortLink.code == code)
            )
            stored_link = result.one()
        assert stored_link.code == code
        assert stored_link.destination_url == (
            "https://example.com/t109-integration"
        )
        assert stored_link.clicks_total == 0
        assert fields["link_id"] == str(stored_link.id)
    finally:
        await redis_client.aclose()
        await engine.dispose()


async def remove_integration_data(
    settings: Settings,
    code: str,
) -> None:
    redis_client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
    )
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )
    try:
        await redis_client.delete(
            f"short:v1:{code}",
            settings.analytics_stream_name,
        )
        async with engine.begin() as connection:
            link_id_result = await connection.execute(
                select(ShortLink.id).where(ShortLink.code == code)
            )
            link_id = link_id_result.scalar_one_or_none()
            if link_id is not None:
                await connection.execute(
                    delete(ClickEvent).where(ClickEvent.link_id == link_id)
                )
                await connection.execute(
                    delete(ShortLink).where(ShortLink.id == link_id)
                )
    finally:
        await redis_client.aclose()
        await engine.dispose()


def test_create_redirect_analytics_contract_with_postgres_and_redis() -> None:
    settings = integration_settings()
    created_code: str | None = None
    try:
        with TestClient(create_app(settings)) as client:
            create_response = client.post(
                "/api/v1/shorten",
                json={
                    "destination_url": "https://example.com/t109-integration"
                },
            )
            assert create_response.status_code == 201
            created = create_response.json()
            created_code = created["code"]

            analytics_before_redirect = client.get(
                f"/api/v1/links/{created_code}/analytics"
            )
            assert analytics_before_redirect.status_code == 200
            assert analytics_before_redirect.json() == {
                "code": created_code,
                "clicks_total": 0,
            }

            redirect_response = client.get(
                f"/{created_code}",
                follow_redirects=False,
            )
            assert redirect_response.status_code == 302
            assert redirect_response.headers["location"] == (
                "https://example.com/t109-integration"
            )

            missing_analytics = client.get(
                "/api/v1/links/T109Missing/analytics"
            )
            assert missing_analytics.status_code == 404
            assert missing_analytics.json()["error"]["code"] == "link_not_found"

        asyncio.run(assert_persisted_and_published(settings, created_code))
    finally:
        if created_code is not None:
            asyncio.run(remove_integration_data(settings, created_code))


def test_custom_alias_persists_redirects_and_conflicts_with_postgres() -> None:
    settings = integration_settings()
    alias = f"t116{uuid4().hex[:8]}"
    created = False
    try:
        with TestClient(create_app(settings)) as client:
            first = client.post(
                "/api/v1/shorten",
                json={
                    "destination_url": "https://example.com/custom-alias",
                    "custom_alias": alias,
                },
            )
            assert first.status_code == 201
            created = True
            assert first.json()["code"] == alias

            duplicate = client.post(
                "/api/v1/shorten",
                json={
                    "destination_url": "https://example.com/duplicate",
                    "custom_alias": alias,
                },
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "short_code_conflict"

            redirect = client.get(f"/{alias}", follow_redirects=False)
            assert redirect.status_code == 302
            assert redirect.headers["location"] == (
                "https://example.com/custom-alias"
            )
    finally:
        if created:
            asyncio.run(remove_integration_data(settings, alias))
