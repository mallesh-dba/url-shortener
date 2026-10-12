import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from redis.exceptions import RedisError

from url_shortener.config import Settings
from url_shortener.security import (
    InvalidClientAddress,
    RateLimitUnavailable,
    _client_address,
    enforce_rate_limit,
)


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://localhost/url_shortener",
        "redis_url": "redis://localhost:6379/0",
        "public_base_url": "https://sho.rt",
        "analytics_api_key": "test-only-analytics-token-for-unit-tests-012345",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_request(
    peer: str,
    forwarded_for: str | None = None,
    trusted_proxy_cidrs: list[str] | None = None,
) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("localhost", 80),
        "root_path": "",
        "app": SimpleNamespace(
            state=SimpleNamespace(
                settings=make_settings(
                    trusted_proxy_cidrs=trusted_proxy_cidrs or [],
                ),
                redis=AsyncMock(),
            )
        ),
    }
    return Request(scope)


def test_untrusted_forwarded_header_is_ignored() -> None:
    request = make_request(
        "198.51.100.7",
        "203.0.113.99",
        ["10.0.0.0/8"],
    )

    assert _client_address(request, request.app.state.settings) == "198.51.100.7"


def test_trusted_proxy_chain_resolves_first_untrusted_address_from_right() -> None:
    request = make_request(
        "10.0.0.2",
        "203.0.113.9, 10.0.0.1",
        ["10.0.0.0/8"],
    )

    assert _client_address(request, request.app.state.settings) == "203.0.113.9"


def test_malformed_forwarded_header_from_trusted_proxy_is_rejected() -> None:
    request = make_request(
        "10.0.0.2",
        "not-an-address",
        ["10.0.0.0/8"],
    )

    with pytest.raises(InvalidClientAddress):
        _client_address(request, request.app.state.settings)


def test_rate_limit_uses_short_lived_hmac_key_not_raw_client_address() -> None:
    request = make_request("198.51.100.7")
    redis_client = AsyncMock()
    redis_client.eval.return_value = [1, 60]
    request.app.state.redis = redis_client

    asyncio.run(enforce_rate_limit(request, "create"))

    redis_client.eval.assert_awaited_once()
    _, key_count, key, rate_window = redis_client.eval.await_args.args
    assert key_count == 1
    assert key.startswith("rate:v1:create:")
    assert "198.51.100.7" not in key
    assert rate_window == 60


def test_rate_limit_fails_closed_when_redis_is_unavailable() -> None:
    request = make_request("198.51.100.7")
    request.app.state.redis.eval.side_effect = RedisError("redis unavailable")

    with pytest.raises(RateLimitUnavailable):
        asyncio.run(enforce_rate_limit(request, "redirect"))


def test_rate_limit_fails_closed_without_hashing_secret() -> None:
    request = make_request("198.51.100.7")
    request.app.state.settings = make_settings(analytics_api_key=None)

    with pytest.raises(RateLimitUnavailable):
        asyncio.run(enforce_rate_limit(request, "analytics"))
