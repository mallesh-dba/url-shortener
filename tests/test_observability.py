import json
import logging
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.database import get_session
from url_shortener.main import create_app
from url_shortener.observability import (
    JsonLogFormatter,
    configure_structured_logging,
)


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
    )


def test_metrics_use_route_templates_and_cache_outcomes() -> None:
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
        metrics_response = client.get("/metrics")

    metrics = metrics_response.text
    assert redirect.status_code == 302
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
