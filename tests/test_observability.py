import json
import logging
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import generate_latest

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.main import create_app
from url_shortener.observability import (
    JsonLogFormatter,
    METRICS_REGISTRY,
    configure_structured_logging,
)


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
    )


def test_public_app_does_not_expose_metrics_and_labels_stay_bounded() -> None:
    session = AsyncMock(spec=AsyncSession)
    redis_client = AsyncMock()
    redis_client.get.return_value = json.dumps(
        {
            "link_id": 42,
            "destination_url": "https://example.com/private?token=secret",
        }
    )
    app = create_app(make_settings())

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        client.app.state.redis = redis_client
        redirect = client.get("/Ab12Cd34", follow_redirects=False)
        metrics_response = client.get("/metrics", follow_redirects=False)

    metrics = generate_latest(METRICS_REGISTRY).decode()
    assert redirect.status_code == 302
    assert metrics_response.status_code == 404
    assert (
        'url_shortener_http_requests_total{method="GET",route="/{code}",'
        'status_code="302"}'
    ) in metrics
    assert (
        'url_shortener_cache_operations_total{operation="lookup",outcome="hit"}'
    ) in metrics
    assert "Ab12Cd34" not in metrics
    assert "example.com" not in metrics
    assert "token=secret" not in metrics


def test_api_metrics_listener_uses_private_bind_and_closes_on_shutdown() -> None:
    settings = make_settings().model_copy(
        update={"api_metrics_host": "127.0.0.1", "api_metrics_port": 19100}
    )
    engine = Mock()
    engine.dispose = AsyncMock()
    redis_client = Mock()
    redis_client.aclose = AsyncMock()
    metrics_server = Mock()

    with (
        patch("url_shortener.main.create_async_engine", return_value=engine),
        patch("url_shortener.main.Redis.from_url", return_value=redis_client),
        patch("url_shortener.main.async_sessionmaker", return_value=Mock()),
        patch(
            "url_shortener.main.start_http_server",
            return_value=(metrics_server, Mock()),
        ) as start_metrics,
        TestClient(create_app(settings)),
    ):
        pass

    start_metrics.assert_called_once()
    assert start_metrics.call_args.args == (19100,)
    assert start_metrics.call_args.kwargs["addr"] == "127.0.0.1"
    assert start_metrics.call_args.kwargs["registry"] is METRICS_REGISTRY
    metrics_server.shutdown.assert_called_once()
    metrics_server.server_close.assert_called_once()
    redis_client.aclose.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_json_log_formatter_omits_codes_and_destination_urls() -> None:
    record = logging.LogRecord(
        "url_shortener.http",
        logging.INFO,
        __file__,
        1,
        "HTTP request completed",
        (),
        None,
    )
    record.method = "GET"
    record.route = "/{code}"
    record.status_code = 302
    record.short_code = "Ab12Cd34"
    record.destination_url = "https://example.com/private?token=secret"

    formatted = JsonLogFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["message"] == "HTTP request completed"
    assert payload["route"] == "/{code}"
    assert "Ab12Cd34" not in formatted
    assert "example.com" not in formatted
    assert "token=secret" not in formatted


def test_structured_logging_disables_raw_uvicorn_access_paths() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    was_disabled = access_logger.disabled
    try:
        configure_structured_logging()
        assert access_logger.disabled
    finally:
        access_logger.disabled = was_disabled
