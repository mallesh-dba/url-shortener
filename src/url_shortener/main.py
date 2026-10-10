from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from url_shortener.config import Settings, get_settings
from url_shortener.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        current_settings = settings or get_settings()
        engine = create_async_engine(
            current_settings.database_url.get_secret_value(),
            pool_size=current_settings.db_pool_size,
            max_overflow=current_settings.db_max_overflow,
            pool_timeout=current_settings.db_pool_timeout_seconds,
            connect_args={
                "timeout": current_settings.db_connect_timeout_seconds,
            },
            pool_pre_ping=True,
        )
        redis_client: Redis | None = None
        try:
            redis_client = Redis.from_url(
                current_settings.redis_url.get_secret_value(),
                max_connections=current_settings.redis_max_connections,
                socket_connect_timeout=current_settings.redis_connect_timeout_seconds,
                socket_timeout=current_settings.redis_socket_timeout_seconds,
                decode_responses=True,
            )
            application.state.engine = engine
            application.state.session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            application.state.redis = redis_client
            application.state.settings = current_settings
            yield
        finally:
            try:
                if redis_client is not None:
                    await redis_client.aclose()
            finally:
                await engine.dispose()

    application = FastAPI(
        title="URL Shortener",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    return application


app = create_app()
