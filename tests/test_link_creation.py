import json
import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import asyncpg
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.link_service import generate_short_code
from url_shortener.main import create_app
from url_shortener.models import ShortLink


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
    )


def make_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()

    async def populate_generated_columns() -> None:
        link: ShortLink = session.add.call_args.args[0]
        link.id = 42
        link.created_at = datetime(2026, 10, 10, tzinfo=UTC)

    session.flush.side_effect = populate_generated_columns
    return session


def adapted_unique_violation(constraint_name: str) -> IntegrityError:
    driver_error = asyncpg.exceptions.UniqueViolationError("duplicate key")
    driver_error.constraint_name = constraint_name
    adapted_error = AsyncAdapt_asyncpg_dbapi(asyncpg).IntegrityError(
        str(driver_error),
        driver_error,
    )
    adapted_error.__cause__ = driver_error
    return IntegrityError("INSERT", {}, adapted_error)


def post_create_link(
    session: AsyncMock,
    redis_client: AsyncMock,
    destination_url: str = "https://example.com/path",
):
    app = create_app(make_settings())

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        client.app.state.redis = redis_client
        response = client.post(
            "/api/v1/shorten",
            json={"destination_url": destination_url},
        )
    return response


@pytest.mark.parametrize(
    "destination_url",
    [
        "ftp://example.com/file",
        "//example.com/path",
        "not a URL",
        "http:///missing-host",
        "https://",
    ],
)
def test_create_link_rejects_malformed_or_non_http_urls(
    destination_url: str,
) -> None:
    session = make_session()
    redis_client = AsyncMock()

    response = post_create_link(session, redis_client, destination_url)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    redis_client.set.assert_not_awaited()


def test_generated_short_code_is_eight_base62_characters() -> None:
    assert re.fullmatch(r"[0-9A-Za-z]{8}", generate_short_code())


def test_create_link_commits_before_best_effort_cache_and_returns_contract() -> None:
    session = make_session()
    redis_client = AsyncMock()

    async def verify_commit_precedes_cache(
        name: str,
        value: str,
        ex: int,
    ) -> bool:
        assert session.commit.await_count == 1
        return True

    redis_client.set.side_effect = verify_commit_precedes_cache
    with patch(
        "url_shortener.link_service.generate_short_code",
        return_value="Ab12Cd34",
    ):
        response = post_create_link(session, redis_client)

    assert response.status_code == 201
    assert response.json() == {
        "code": "Ab12Cd34",
        "short_url": "https://sho.rt/Ab12Cd34",
        "created_at": "2026-10-10T00:00:00Z",
    }
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    redis_client.set.assert_awaited_once()
    cache_key, cache_value = redis_client.set.await_args.args
    assert cache_key == "short:v1:Ab12Cd34"
    assert json.loads(cache_value) == {
        "link_id": 42,
        "destination_url": "https://example.com/path",
    }
    assert redis_client.set.await_args.kwargs == {"ex": 3600}


def test_create_link_retries_only_short_code_unique_conflict() -> None:
    session = make_session()
    redis_client = AsyncMock()
    collision = adapted_unique_violation("uq_short_links_code")

    flush_count = 0

    async def flush_with_collision_once() -> None:
        nonlocal flush_count
        flush_count += 1
        if flush_count == 1:
            raise collision
        link: ShortLink = session.add.call_args.args[0]
        link.id = 42
        link.created_at = datetime(2026, 10, 10, tzinfo=UTC)

    session.flush.side_effect = flush_with_collision_once
    codes = iter(["Ab12Cd34", "Ef56Gh78"])

    with patch(
        "url_shortener.link_service.generate_short_code",
        side_effect=lambda: next(codes),
    ):
        response = post_create_link(session, redis_client)

    assert response.status_code == 201
    assert session.add.call_count == 2
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 1
    assert redis_client.set.await_count == 1


def test_create_link_stops_after_bounded_collision_retries() -> None:
    session = make_session()
    redis_client = AsyncMock()
    collision = adapted_unique_violation("uq_short_links_code")
    session.flush.side_effect = [collision] * 5

    with patch(
        "url_shortener.link_service.generate_short_code",
        return_value="Ab12Cd34",
    ):
        response = post_create_link(session, redis_client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_unavailable"
    assert session.add.call_count == 5
    assert session.rollback.await_count == 5
    session.commit.assert_not_awaited()
    redis_client.set.assert_not_awaited()


def test_create_link_maps_database_failure_to_service_unavailable() -> None:
    session = make_session()
    session.flush.side_effect = OperationalError(
        "INSERT",
        {},
        RuntimeError("database unavailable"),
    )
    redis_client = AsyncMock()

    response = post_create_link(session, redis_client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_unavailable"
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    redis_client.set.assert_not_awaited()


def test_create_link_maps_commit_failure_to_service_unavailable() -> None:
    session = make_session()
    session.commit.side_effect = OperationalError(
        "COMMIT",
        {},
        RuntimeError("database unavailable"),
    )
    redis_client = AsyncMock()

    response = post_create_link(session, redis_client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_unavailable"
    session.rollback.assert_awaited_once()
    redis_client.set.assert_not_awaited()


def test_create_link_succeeds_when_redis_cache_population_fails() -> None:
    session = make_session()
    redis_client = AsyncMock()
    redis_client.set.side_effect = RedisError("redis unavailable")

    with patch(
        "url_shortener.link_service.generate_short_code",
        return_value="Ab12Cd34",
    ):
        response = post_create_link(session, redis_client)

    assert response.status_code == 201
    session.commit.assert_awaited_once()
    redis_client.set.assert_awaited_once()
