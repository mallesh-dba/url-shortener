from collections.abc import Awaitable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from fastapi import APIRouter, Request, Response, status
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


class DatabaseProbe(Protocol):
    def connect(self) -> AbstractAsyncContextManager[object]: ...


class RedisProbe(Protocol):
    def ping(self) -> Awaitable[bool | None]: ...


async def postgres_is_ready(engine: DatabaseProbe) -> bool:
    try:
        async with engine.connect():
            return True
    except (SQLAlchemyError, TimeoutError):
        return False


async def redis_is_ready(redis_client: RedisProbe) -> bool:
    try:
        return bool(await redis_client.ping())
    except (RedisError, TimeoutError):
        return False


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request, response: Response) -> dict[str, object]:
    dependencies = {
        "postgres": await postgres_is_ready(request.app.state.engine),
        "redis": await redis_is_ready(request.app.state.redis),
    }
    ready = all(dependencies.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "dependencies": dependencies,
    }
