import json
import logging
import secrets
from typing import Protocol

from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.config import Settings
from url_shortener.models import ShortLink

logger = logging.getLogger(__name__)

BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SHORT_CODE_LENGTH = 8
MAX_CODE_GENERATION_ATTEMPTS = 5


class LinkCache(Protocol):
    async def set(self, name: str, value: str, ex: int) -> object: ...


class LinkPersistenceUnavailable(Exception):
    pass


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
            if (
                _is_code_collision(error)
                and attempt + 1 < MAX_CODE_GENERATION_ATTEMPTS
            ):
                continue
            logger.error("Short-link persistence failed")
            raise LinkPersistenceUnavailable from error
        except SQLAlchemyError as error:
            await _rollback(session)
            logger.error("Short-link persistence failed")
            raise LinkPersistenceUnavailable from error

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
        except RedisError:
            logger.warning(
                "Short-link cache population failed",
                extra={"short_code": link.code},
            )
        return link

    raise LinkPersistenceUnavailable


def make_short_url(settings: Settings, code: str) -> str:
    return f"{str(settings.public_base_url).rstrip('/')}/{code}"
