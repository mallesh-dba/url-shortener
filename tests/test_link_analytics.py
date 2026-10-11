from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
    )


def request_analytics(session: AsyncMock, code: str = "Ab12Cd34"):
    app = create_app(make_settings())

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with (
        patch(
            "url_shortener.main.Redis.from_url",
            return_value=AsyncMock(),
        ),
        TestClient(app) as client,
    ):
        response = client.get(f"/api/v1/links/{code}/analytics")
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
    assert "FROM short_links" in str(statement)


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
