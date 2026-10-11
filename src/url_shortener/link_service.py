import json
import logging
import secrets
from typing import Protocol

from sqlalchemy import select
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.models import ShortLink
from url_shortener.observability import CACHE_OPERATIONS, CODE_COLLISION_RETRIES
from url_shortener.schemas import ShortLinkCreateRequest

logger = logging.getLogger(__name__)

BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SHORT_CODE_LENGTH = 8
MAX_CODE_GENERATION_ATTEMPTS = 5


class LinkCache(Protocol):
    async def get(self, name: str) -> str | None: ...

    async def set(self, name: str, value: str, ex: int) -> object: ...


class LinkPersistenceUnavailable(Exception):
    pass


class LinkLookupUnavailable(Exception):
    pass


class ShortLinkNotFound(Exception):
    pass


async def get_link_analytics(
    session: AsyncSession,
    code: str,
) -> tuple[str, int]:
    try:
        result = await session.execute(
            select(ShortLink.code, ShortLink.clicks_total).where(
                ShortLink.code == code
            )
        )
        link_analytics = result.one_or_none()
    except (SQLAlchemyError, OSError, TimeoutError) as error:
        await _rollback(session)
        logger.error("Short-link analytics lookup failed")
        raise LinkLookupUnavailable from error

    if link_analytics is None:
        raise ShortLinkNotFound
    return link_analytics.code, link_analytics.clicks_total


def generate_short_code() -> str:
    return "".join(
        secrets.choice(BASE62_ALPHABET)
        for _ in range(SHORT_CODE_LENGTH)
    )


def _is_code_collision(error: IntegrityError) -> bool:
    original = error.orig
    cause = getattr(original, "__cause__", None)
    diagnostic = getattr(cause, "diag", None)
    sqlstate = getattr(original, "sqlstate", None) or getattr(
        original,
        "pgcode",
        None,
    )
    constraint_name = getattr(cause, "constraint_name", None) or getattr(
        diagnostic,
        "constraint_name",
        None,
    )
    return sqlstate == "23505" and constraint_name == "uq_short_links_code"


async def _rollback(session: AsyncSession) -> None:
    await session.rollback()


async def create_short_link(
    session: AsyncSession,
    redis_client: LinkCache,
    destination_url: str,
    settings: Settings,
) -> ShortLink:
    for attempt in range(MAX_CODE_GENERATION_ATTEMPTS):
        link = ShortLink(
            code=generate_short_code(),
            destination_url=destination_url,
        )
        session.add(link)
        try:
            await session.flush()
            await session.commit()
        except IntegrityError as error:
            await _rollback(session)
            if _is_code_collision(error):
                CODE_COLLISION_RETRIES.inc()
                if attempt + 1 < MAX_CODE_GENERATION_ATTEMPTS:
                    continue
            logger.error("Short-link persistence failed")
            raise LinkPersistenceUnavailable from error
        except (SQLAlchemyError, OSError, TimeoutError) as error:
            await _rollback(session)
            logger.error("Short-link persistence failed")
            raise LinkPersistenceUnavailable from error

        await _cache_mapping(redis_client, link, settings)
        return link

    raise LinkPersistenceUnavailable


def _mapping_cache_value(value: str) -> tuple[int, str] | None:
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            return None
        link_id = parsed.get("link_id")
        destination_url = parsed.get("destination_url")
        if isinstance(link_id, bool) or not isinstance(link_id, int):
            return None
        validated_destination = ShortLinkCreateRequest.model_validate(
            {"destination_url": destination_url}
        ).destination_url
    except (json.JSONDecodeError, TypeError, ValidationError):
        return None

    return link_id, str(validated_destination)


async def _cache_mapping(
    redis_client: LinkCache,
    link: ShortLink,
    settings: Settings,
) -> None:
    cache_key = f"short:v1:{link.code}"
    cache_value = json.dumps(
        {
            "link_id": link.id,
            "destination_url": link.destination_url,
        },
        separators=(",", ":"),
    )
    try:
        await redis_client.set(
            cache_key,
            cache_value,
            ex=settings.link_cache_ttl_seconds,
        )
        CACHE_OPERATIONS.labels("populate", "success").inc()
    except (RedisError, OSError, TimeoutError):
        CACHE_OPERATIONS.labels("populate", "error").inc()
        logger.warning(
            "Short-link cache population failed",
            extra={"operation": "populate", "outcome": "error"},
        )


async def find_short_link(
    session: AsyncSession,
    redis_client: LinkCache,
    code: str,
    settings: Settings,
) -> tuple[str | None, int | None]:
    cache_key = f"short:v1:{code}"
    cache_error = False
    try:
        cached_value = await redis_client.get(cache_key)
    except (RedisError, OSError, TimeoutError):
        cache_error = True
        CACHE_OPERATIONS.labels("lookup", "error").inc()
        logger.warning(
            "Short-link cache lookup failed",
            extra={"operation": "lookup", "outcome": "error"},
        )
        cached_value = None

    if cached_value is not None:
        cached_mapping = _mapping_cache_value(cached_value)
        if cached_mapping is not None:
            CACHE_OPERATIONS.labels("lookup", "hit").inc()
            link_id, destination_url = cached_mapping
            return destination_url, link_id
        CACHE_OPERATIONS.labels("lookup", "invalid").inc()
        logger.warning(
            "Invalid short-link cache entry",
            extra={"operation": "lookup", "outcome": "invalid"},
        )
    elif cached_value is None and not cache_error:
        CACHE_OPERATIONS.labels("lookup", "miss").inc()

    try:
        result = await session.execute(
            select(ShortLink).where(ShortLink.code == code)
        )
        link = result.scalar_one_or_none()
    except (SQLAlchemyError, OSError, TimeoutError) as error:
        await _rollback(session)
        logger.error("Short-link lookup failed")
        raise LinkLookupUnavailable from error

    if link is None:
        return None, None

    await _cache_mapping(redis_client, link, settings)
    return link.destination_url, link.id


def make_short_url(settings: Settings, code: str) -> str:
    return f"{str(settings.public_base_url).rstrip('/')}/{code}"
