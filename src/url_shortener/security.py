import hmac
import ipaddress
import logging
import secrets

from fastapi import Request
from redis.exceptions import RedisError

from url_shortener.config import Settings

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMITS = {
    "create": ("rate_limit_create_requests_per_minute", 10),
    "redirect": ("rate_limit_redirect_requests_per_minute", 120),
    "analytics": ("rate_limit_analytics_requests_per_minute", 60),
}

_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


class AnalyticsAuthenticationRequired(Exception):
    pass


class AnalyticsAuthenticationUnavailable(Exception):
    pass


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


class RateLimitUnavailable(Exception):
    pass


class InvalidClientAddress(Exception):
    pass


def _is_trusted_proxy(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    settings: Settings,
) -> bool:
    return any(
        address in ipaddress.ip_network(network, strict=False)
        for network in settings.trusted_proxy_cidrs
    )


def _parse_forwarded_addresses(
    header: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(value.strip()) for value in header.split(",")]
    except ValueError as error:
        raise InvalidClientAddress from error


def _client_address(request: Request, settings: Settings) -> str:
    if request.client is None or not request.client.host:
        raise InvalidClientAddress
    peer = request.client.host
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        if settings.trusted_proxy_cidrs:
            raise InvalidClientAddress
        return peer.lower()

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded or not _is_trusted_proxy(peer_address, settings):
        return peer_address.compressed

    forwarded_addresses = _parse_forwarded_addresses(forwarded)
    for address in reversed(forwarded_addresses):
        if not _is_trusted_proxy(address, settings):
            return address.compressed
    raise InvalidClientAddress


def require_analytics_authentication(request: Request) -> None:
    settings: Settings = request.app.state.settings
    expected = settings.analytics_api_key
    if expected is None:
        raise AnalyticsAuthenticationUnavailable

    scheme, separator, supplied = request.headers.get(
        "authorization", ""
    ).partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not supplied
        or not secrets.compare_digest(
            supplied,
            expected.get_secret_value(),
        )
    ):
        raise AnalyticsAuthenticationRequired


async def enforce_rate_limit(request: Request, category: str) -> None:
    settings: Settings = request.app.state.settings
    if category not in RATE_LIMITS:
        raise ValueError(f"Unknown rate-limit category: {category}")
    setting_name, default_limit = RATE_LIMITS[category]
    request_limit = int(getattr(settings, setting_name, default_limit))
    address = _client_address(request, settings)
    if settings.analytics_api_key is None:
        raise RateLimitUnavailable
    address_hash = hmac.new(
        settings.analytics_api_key.get_secret_value().encode("utf-8"),
        address.encode("utf-8"),
        "sha256",
    ).hexdigest()
    key = f"rate:v1:{category}:{address_hash}"

    try:
        result = await request.app.state.redis.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            RATE_LIMIT_WINDOW_SECONDS,
        )
    except (RedisError, OSError, TimeoutError) as error:
        logger.error(
            "Rate-limit check failed",
            extra={"operation": "rate_limit", "category": category},
        )
        raise RateLimitUnavailable from error

    try:
        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise ValueError("Redis rate-limit script returned an invalid result")
        count, ttl = result
        current_count = int(count)
        retry_after = max(1, int(ttl))
    except (TypeError, ValueError) as error:
        raise RateLimitUnavailable from error
    if current_count > request_limit:
        raise RateLimitExceeded(retry_after)
