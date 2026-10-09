import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from url_shortener import health
from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.health import postgres_is_ready, redis_is_ready
from url_shortener.main import create_app


class AsyncConnectContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class ReadyEngine:
    def connect(self) -> AsyncConnectContext:
        return AsyncConnectContext()


class FailedEngine:
    def connect(self) -> AsyncConnectContext:
        raise OperationalError("connect", {}, RuntimeError("database unavailable"))


class SessionContext:
    def __init__(self) -> None:
        self.session = object()
        self.closed = False

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.closed = True


def test_request_session_is_closed_after_dependency_finishes() -> None:
    session_context = SessionContext()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                session_factory=lambda: session_context,
            )
        )
    )

    async def consume_dependency() -> object:
        dependency = get_session(request)
        session = await anext(dependency)
        await dependency.aclose()
        return session

    session = asyncio.run(consume_dependency())

    assert session is session_context.session
    assert session_context.closed is True


def test_liveness_does_not_require_dependency_connections() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:password@localhost/shortener",
        redis_url="redis://localhost:6379/0",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_dependency_status(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:password@localhost/shortener",
        redis_url="redis://localhost:6379/0",
    )
    monkeypatch.setattr(health, "postgres_is_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(health, "redis_is_ready", AsyncMock(return_value=True))

    with TestClient(create_app(settings)) as client:
        ready_response = client.get("/health/ready")
        monkeypatch.setattr(
            health, "redis_is_ready", AsyncMock(return_value=False)
        )
        unavailable_response = client.get("/health/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "dependencies": {"postgres": True, "redis": True},
    }
    assert unavailable_response.status_code == 503
    assert unavailable_response.json() == {
        "status": "not_ready",
        "dependencies": {"postgres": True, "redis": False},
    }


def test_lifespan_closes_database_and_redis_resources() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:password@localhost/shortener",
        redis_url="redis://localhost:6379/0",
    )
    engine = Mock()
    engine.dispose = AsyncMock()
    redis_client = Mock()
    redis_client.aclose = AsyncMock()

    with (
        patch(
            "url_shortener.main.create_async_engine",
            return_value=engine,
        ) as create_engine,
        patch(
            "url_shortener.main.Redis.from_url",
            return_value=redis_client,
        ) as create_redis,
        patch("url_shortener.main.async_sessionmaker", return_value=Mock()),
        TestClient(create_app(settings)),
    ):
        pass

    create_engine.assert_called_once_with(
        "postgresql+asyncpg://user:password@localhost/shortener",
        pool_size=10,
        max_overflow=20,
        pool_timeout=5,
        connect_args={"timeout": 5},
        pool_pre_ping=True,
    )
    create_redis.assert_called_once_with(
        "redis://localhost:6379/0",
        max_connections=50,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )
    engine.dispose.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()


def test_dependency_readiness_checks() -> None:
    redis_client = AsyncMock()
    redis_client.ping.return_value = True

    async def run_checks() -> tuple[bool, bool, bool]:
        return (
            await postgres_is_ready(ReadyEngine()),
            await postgres_is_ready(FailedEngine()),
            await redis_is_ready(redis_client),
        )

    assert asyncio.run(run_checks()) == (True, False, True)

    redis_client.ping.side_effect = TimeoutError
    assert asyncio.run(redis_is_ready(redis_client)) is False
