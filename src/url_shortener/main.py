from contextlib import asynccontextmanager
import logging
from time import perf_counter
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.middleware.base import RequestResponseEndpoint

from url_shortener.config import Settings, get_settings
from url_shortener.health import router as health_router
from url_shortener.link_routes import router as link_router
from url_shortener.link_service import (
    LinkLookupUnavailable,
    LinkPersistenceUnavailable,
    ShortLinkNotFound,
)
from url_shortener.observability import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS,
    METRICS_REGISTRY,
    configure_structured_logging,
    observe_database_pool,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_structured_logging()
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
            if isinstance(engine, AsyncEngine):
                observe_database_pool(
                    engine,
                    current_settings.db_pool_size
                    + current_settings.db_max_overflow,
                )
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

    @application.middleware("http")
    async def observe_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            if not isinstance(route_template, str):
                route_template = "unmatched"
            duration_seconds = perf_counter() - started_at
            HTTP_REQUESTS.labels(
                request.method,
                route_template,
                str(status_code),
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                request.method,
                route_template,
            ).observe(duration_seconds)
            logging.getLogger("url_shortener.http").info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "route": route_template,
                    "status_code": status_code,
                    "duration_seconds": duration_seconds,
                },
            )

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(
            content=generate_latest(METRICS_REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": jsonable_encoder(error.errors()),
                }
            },
        )

    @application.exception_handler(LinkPersistenceUnavailable)
    async def persistence_error(
        request: Request,
        error: LinkPersistenceUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "persistence_unavailable",
                    "message": "Link persistence is temporarily unavailable",
                    "details": None,
                }
            },
        )

    @application.exception_handler(LinkLookupUnavailable)
    async def lookup_error(
        request: Request,
        error: LinkLookupUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "lookup_unavailable",
                    "message": "Link lookup is temporarily unavailable",
                    "details": None,
                }
            },
        )

    @application.exception_handler(ShortLinkNotFound)
    async def not_found(
        request: Request,
        error: ShortLinkNotFound,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "link_not_found",
                    "message": "Short link was not found",
                    "details": None,
                }
            },
        )

    application.include_router(health_router)
    application.include_router(link_router)
    return application


app = create_app()
