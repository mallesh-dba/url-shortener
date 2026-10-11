import json
import logging
from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

METRICS_REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "url_shortener_http_requests_total",
    "HTTP requests by method, route template, and status",
    ("method", "route", "status_code"),
    registry=METRICS_REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "url_shortener_http_request_duration_seconds",
    "HTTP request duration by method and route template",
    ("method", "route"),
    registry=METRICS_REGISTRY,
)
CACHE_OPERATIONS = Counter(
    "url_shortener_cache_operations_total",
    "Cache operations by operation and outcome",
    ("operation", "outcome"),
    registry=METRICS_REGISTRY,
)
CODE_COLLISION_RETRIES = Counter(
    "url_shortener_code_collision_retries_total",
    "Short-code uniqueness conflicts encountered during creation",
    registry=METRICS_REGISTRY,
)
DB_POOL_CHECKED_OUT = Gauge(
    "url_shortener_db_pool_checked_out",
    "Database connections currently checked out",
    registry=METRICS_REGISTRY,
)
DB_POOL_CHECKED_OUT_HIGH_WATER = Gauge(
    "url_shortener_db_pool_checked_out_high_water",
    "Peak checked-out database connections since process start",
    registry=METRICS_REGISTRY,
)
DB_POOL_CAPACITY = Gauge(
    "url_shortener_db_pool_capacity",
    "Configured database connection pool capacity",
    registry=METRICS_REGISTRY,
)
CLICK_EVENT_PUBLISH_FAILURES = Counter(
    "url_shortener_click_event_publish_failures_total",
    "Best-effort click event publication failures",
    registry=METRICS_REGISTRY,
)
ANALYTICS_PROCESSING_FAILURES = Counter(
    "url_shortener_analytics_processing_failures_total",
    "Click event processing failures",
    registry=METRICS_REGISTRY,
)
ANALYTICS_PROCESSED_EVENTS = Counter(
    "url_shortener_analytics_processed_events_total",
    "Click stream entries successfully persisted and acknowledged",
    registry=METRICS_REGISTRY,
)
ANALYTICS_REDIS_FAILURES = Counter(
    "url_shortener_analytics_redis_failures_total",
    "Analytics worker Redis operation failures",
    registry=METRICS_REGISTRY,
)
ANALYTICS_PENDING_EVENTS = Gauge(
    "url_shortener_analytics_pending_events",
    "Pending click events in the consumer group",
    registry=METRICS_REGISTRY,
)
ANALYTICS_STREAM_LAG = Gauge(
    "url_shortener_analytics_stream_lag",
    "Unprocessed click events; -1 when Redis does not report lag",
    registry=METRICS_REGISTRY,
)


def observe_database_pool(engine: AsyncEngine, capacity: int) -> None:
    DB_POOL_CAPACITY.set(capacity)
    checked_out_count = 0
    high_water_count = 0

    def checked_out(*_args: object) -> None:
        nonlocal checked_out_count, high_water_count
        checked_out_count += 1
        DB_POOL_CHECKED_OUT.inc()
        high_water_count = max(high_water_count, checked_out_count)
        DB_POOL_CHECKED_OUT_HIGH_WATER.set(high_water_count)

    def checked_in(*_args: object) -> None:
        nonlocal checked_out_count
        checked_out_count -= 1
        DB_POOL_CHECKED_OUT.dec()

    event.listen(engine.sync_engine, "checkout", checked_out)
    event.listen(engine.sync_engine, "checkin", checked_in)


class JsonLogFormatter(logging.Formatter):
    _structured_fields = (
        "method",
        "route",
        "status_code",
        "duration_seconds",
        "operation",
        "outcome",
        "pending_count",
        "lag",
        "stream_entry_id",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._structured_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_structured_logging() -> None:
    logging.getLogger("uvicorn.access").disabled = True
    logger = logging.getLogger("url_shortener")
    if any(
        isinstance(handler.formatter, JsonLogFormatter)
        for handler in logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
