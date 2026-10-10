import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.main import create_app
from url_shortener.models import ShortLink


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
    )


def make_link() -> ShortLink:
    return ShortLink(
        id=42,
        code="Ab12Cd34",
        destination_url="https://example.com/path",
    )


def cached_mapping(link: ShortLink) -> str:
    return json.dumps(
        {
            "link_id": link.id,
            "destination_url": link.destination_url,
        }
    )


def request_redirect(
    session: AsyncMock,
    redis_client: AsyncMock,
    code: str = "Ab12Cd34",
):
    app = create_app(make_settings())

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with (
        patch("url_shortener.main.Redis.from_url", return_value=redis_client),
        TestClient(app, follow_redirects=False) as client,
    ):
        response = client.get(f"/{code}")
    return response


def make_session(link: ShortLink | None) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=link)
    )
    return session


def test_redirect_cache_hit_skips_database_lookup() -> None:
    link = make_link()
    session = make_session(None)
    redis_client = AsyncMock()
    redis_client.get.return_value = cached_mapping(link)

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    assert response.headers["location"] == link.destination_url
    redis_client.get.assert_awaited_once_with("short:v1:Ab12Cd34")
    session.execute.assert_not_awaited()
    redis_client.set.assert_not_awaited()


def test_redirect_publishes_a_click_event_in_background() -> None:
    link = make_link()
    session = make_session(None)
    redis_client = AsyncMock()
    redis_client.get.return_value = cached_mapping(link)

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    redis_client.xadd.assert_awaited_once()
    stream, fields = redis_client.xadd.await_args.args
    assert stream == "clicks:v1"
    assert fields["link_id"] == str(link.id)
    assert set(fields) == {"event_id", "link_id", "clicked_at"}


def test_redirect_cache_miss_reads_database_and_populates_cache() -> None:
    link = make_link()
    session = make_session(link)
    redis_client = AsyncMock()
    redis_client.get.return_value = None

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    assert response.headers["location"] == link.destination_url
    session.execute.assert_awaited_once()
    redis_client.set.assert_awaited_once()
    assert redis_client.set.await_args.args[0] == "short:v1:Ab12Cd34"
    assert json.loads(redis_client.set.await_args.args[1]) == {
        "link_id": 42,
        "destination_url": link.destination_url,
    }
    assert redis_client.set.await_args.kwargs == {"ex": 3600}


def test_redirect_cold_start_uses_database_when_cache_is_empty() -> None:
    link = make_link()
    session = make_session(link)
    redis_client = AsyncMock()
    redis_client.get.return_value = None

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    assert response.headers["location"] == link.destination_url
    session.execute.assert_awaited_once()
    redis_client.set.assert_awaited_once()


def test_redirect_returns_404_only_after_database_confirms_unknown_code() -> None:
    session = make_session(None)
    redis_client = AsyncMock()
    redis_client.get.return_value = None

    response = request_redirect(session, redis_client, "Unknown1")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "link_not_found"
    session.execute.assert_awaited_once()
    redis_client.set.assert_not_awaited()


def test_redis_read_outage_falls_back_to_database_for_known_link() -> None:
    link = make_link()
    session = make_session(link)
    redis_client = AsyncMock()
    redis_client.get.side_effect = RedisError("redis unavailable")
    redis_client.set.side_effect = RedisError("redis unavailable")

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    assert response.headers["location"] == link.destination_url
    session.execute.assert_awaited_once()
    redis_client.set.assert_awaited_once()


def test_redis_outage_does_not_create_false_404_if_database_is_unavailable() -> None:
    session = make_session(None)
    session.execute.side_effect = OperationalError(
        "SELECT",
        {},
        RuntimeError("database unavailable"),
    )
    redis_client = AsyncMock()
    redis_client.get.side_effect = RedisError("redis unavailable")

    response = request_redirect(session, redis_client, "Unknown1")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "lookup_unavailable"
    session.rollback.assert_awaited_once()
    redis_client.set.assert_not_awaited()


def test_invalid_cache_entry_falls_back_to_database() -> None:
    link = make_link()
    session = make_session(link)
    redis_client = AsyncMock()
    redis_client.get.return_value = '{"link_id":42,"destination_url":"javascript:bad"}'

    response = request_redirect(session, redis_client)

    assert response.status_code == 302
    assert response.headers["location"] == link.destination_url
    session.execute.assert_awaited_once()
    redis_client.set.assert_awaited_once()


def test_database_failure_after_cache_miss_returns_503_not_404() -> None:
    session = make_session(None)
    session.execute.side_effect = OperationalError(
        "SELECT",
        {},
        RuntimeError("database unavailable"),
    )
    redis_client = AsyncMock()
    redis_client.get.return_value = None

    response = request_redirect(session, redis_client, "Unknown1")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "lookup_unavailable"
    session.rollback.assert_awaited_once()


def test_connection_refused_after_cache_miss_returns_503_not_500_or_404() -> None:
    session = make_session(None)
    session.execute.side_effect = ConnectionRefusedError(
        "database connection refused"
    )
    redis_client = AsyncMock()
    redis_client.get.return_value = None

    response = request_redirect(session, redis_client, "Unknown1")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "lookup_unavailable"
    session.rollback.assert_awaited_once()
