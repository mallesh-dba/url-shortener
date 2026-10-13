from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.main import create_app


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
        analytics_api_key="test-only-analytics-token-for-unit-tests-012345",
    )


def request_analytics(
    session: AsyncMock,
    code: str = "Ab12Cd34",
    authorization: str | None = (
        "Bearer test-only-analytics-token-for-unit-tests-012345"
    ),
    redis_eval_result: list[int] | None = None,
):
    app = create_app(make_settings())

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    redis = AsyncMock()
    redis.eval.return_value = redis_eval_result or [1, 60]
    with (
        patch(
            "url_shortener.main.Redis.from_url",
            return_value=redis,
        ),
        TestClient(app) as client,
    ):
        headers = (
            {"Authorization": authorization}
            if authorization is not None
            else {}
        )
        response = client.get(f"/api/v1/links/{code}/analytics", headers=headers)
    return response


def make_session(result: object | None) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = SimpleNamespace(one_or_none=lambda: result)
    return session


def test_analytics_returns_persisted_aggregate_for_known_code() -> None:
    session = make_session(
        SimpleNamespace(code="Ab12Cd34", clicks_total=7)
    )

    response = request_analytics(session)

    assert response.status_code == 200
    assert response.json() == {"code": "Ab12Cd34", "clicks_total": 7}
    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    assert statement.selected_columns.keys() == ["code", "clicks_total"]
    assert "FROM short_links LEFT OUTER JOIN daily_click_aggregates" in str(statement)


def test_analytics_returns_zero_before_any_click_is_processed() -> None:
    session = make_session(
        SimpleNamespace(code="Ab12Cd34", clicks_total=0)
    )

    response = request_analytics(session)

    assert response.status_code == 200
    assert response.json() == {"code": "Ab12Cd34", "clicks_total": 0}


def test_analytics_returns_404_only_when_database_confirms_unknown_code() -> None:
    session = make_session(None)

    response = request_analytics(session, "Unknown1")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "link_not_found"
    session.execute.assert_awaited_once()


def test_analytics_rollback_failure_preserves_503_response() -> None:
    session = make_session(None)
    session.execute.side_effect = OperationalError(
        "SELECT",
        {},
        RuntimeError("database unavailable"),
    )
    session.rollback.side_effect = RuntimeError("rollback failed")

    with patch("url_shortener.link_service.logger.exception") as log_rollback:
        response = request_analytics(session, "Unknown1")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "lookup_unavailable"
    session.rollback.assert_awaited_once()
    log_rollback.assert_called_once_with("Short-link analytics rollback failed")


def test_analytics_database_failure_returns_503_not_404() -> None:
    session = make_session(None)
    session.execute.side_effect = OperationalError(
        "SELECT",
        {},
        RuntimeError("database unavailable"),
    )

    response = request_analytics(session, "Unknown1")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "lookup_unavailable"
    session.rollback.assert_awaited_once()


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-token", "Basic test"])
def test_analytics_requires_valid_bearer_token(
    authorization: str | None,
) -> None:
    session = make_session(SimpleNamespace(code="Ab12Cd34", clicks_total=7))

    response = request_analytics(session, authorization=authorization)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "authentication_required"
    session.execute.assert_not_awaited()


def test_analytics_returns_429_with_retry_after_when_limited() -> None:
    session = make_session(SimpleNamespace(code="Ab12Cd34", clicks_total=7))

    response = request_analytics(session, redis_eval_result=[61, 23])

    assert response.status_code == 429
    assert response.headers["retry-after"] == "23"
    assert response.json()["error"]["code"] == "rate_limit_exceeded"
    session.execute.assert_not_awaited()
