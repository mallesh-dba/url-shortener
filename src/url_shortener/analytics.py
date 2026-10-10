import asyncio
import logging
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from redis.exceptions import RedisError, ResponseError
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from url_shortener.config import Settings, get_settings
from url_shortener.models import ClickEvent, ShortLink

logger = logging.getLogger(__name__)

DEFAULT_STREAM_NAME = "clicks:v1"
DEFAULT_CONSUMER_GROUP = "click-analytics:v1"


class ClickStreamClient(Protocol):
    async def xadd(
        self,
        name: str,
        fields: Mapping[str, str],
    ) -> str: ...

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "0-0",
        mkstream: bool = False,
    ) -> object: ...

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]: ...

    async def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int | None = None,
    ) -> tuple[str, list[tuple[str, dict[str, str]]], list[str]]: ...

    async def xack(self, name: str, groupname: str, *ids: str) -> int: ...

    async def xlen(self, name: str) -> int: ...

    async def xinfo_groups(self, name: str) -> list[dict[str, object]]: ...

    async def xpending_range(
        self,
        name: str,
        groupname: str,
        min: str,
        max: str,
        count: int,
    ) -> list[dict[str, object]]: ...

    async def xrevrange(
        self,
        name: str,
        max: str = "+",
        min: str = "-",
        count: int | None = None,
    ) -> list[tuple[str, dict[str, str]]]: ...

    async def xtrim(
        self,
        name: str,
        maxlen: int | None = None,
        minid: str | None = None,
        approximate: bool = True,
        limit: int | None = None,
    ) -> int: ...


async def publish_click_event(
    redis_client: ClickStreamClient,
    link_id: int,
    stream_name: str = DEFAULT_STREAM_NAME,
) -> None:
    fields = {
        "event_id": str(uuid4()),
        "link_id": str(link_id),
        "clicked_at": datetime.now(UTC).isoformat(),
    }
    try:
        await redis_client.xadd(stream_name, fields)
    except (RedisError, TimeoutError):
        logger.warning(
            "Click event publication failed",
            exc_info=True,
        )


def _field(fields: Mapping[str | bytes, str | bytes], key: str) -> str:
    value = fields.get(key)
    if value is None:
        value = fields.get(key.encode())
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, str):
        return value
    raise ValueError(f"Click event is missing a valid {key} field")


def _parse_click_event(
    fields: Mapping[str | bytes, str | bytes],
) -> tuple[UUID, int, datetime]:
    event_id = UUID(_field(fields, "event_id"))
    link_id = int(_field(fields, "link_id"))
    if link_id < 1:
        raise ValueError("Click event link_id must be positive")
    clicked_at = datetime.fromisoformat(_field(fields, "clicked_at"))
    if clicked_at.tzinfo is None or clicked_at.utcoffset() is None:
        raise ValueError("Click event clicked_at must include a timezone")
    return event_id, link_id, clicked_at.astimezone(UTC)


async def ensure_consumer_group(
    redis_client: ClickStreamClient,
    stream_name: str,
    group_name: str,
) -> None:
    try:
        await redis_client.xgroup_create(
            stream_name,
            group_name,
            id="0-0",
            mkstream=True,
        )
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


def _stream_id_tuple(stream_id: str | bytes) -> tuple[int, int]:
    if isinstance(stream_id, bytes):
        stream_id = stream_id.decode()
    milliseconds, sequence = stream_id.split("-", maxsplit=1)
    return int(milliseconds), int(sequence)


def _mapping_value(mapping: Mapping[object, object], key: str) -> object:
    if key in mapping:
        return mapping[key]
    return mapping.get(key.encode())


def _text_value(value: object) -> str | None:
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, str):
        return value
    return None


@dataclass
class StreamTrimState:
    safe_boundary: str | None = None


async def trim_acknowledged_stream(
    redis_client: ClickStreamClient,
    stream_name: str,
    group_name: str,
    max_length: int,
    state: StreamTrimState | None = None,
) -> int:
    if await redis_client.xlen(stream_name) <= max_length:
        return 0

    groups = await redis_client.xinfo_groups(stream_name)
    safe_boundaries: list[str] = []
    found_target_group = False
    for group in groups:
        current_group = _text_value(_mapping_value(group, "name"))
        if current_group is None:
            continue
        if current_group == group_name:
            found_target_group = True
        pending = await redis_client.xpending_range(
            stream_name,
            current_group,
            min="-",
            max="+",
            count=1,
        )
        boundary = (
            _mapping_value(pending[0], "message_id")
            if pending
            else _mapping_value(group, "last-delivered-id")
        )
        text_boundary = _text_value(boundary)
        if text_boundary is None:
            return 0
        safe_boundaries.append(text_boundary)
    if not found_target_group or not safe_boundaries:
        return 0
    safe_boundary = min(safe_boundaries, key=_stream_id_tuple)
    if state is not None and safe_boundary == state.safe_boundary:
        return 0

    recent_entries = await redis_client.xrevrange(
        stream_name,
        max="+",
        min="-",
        count=max_length,
    )
    if len(recent_entries) < max_length:
        return 0
    retention_boundary = _text_value(recent_entries[-1][0])
    if retention_boundary is None:
        return 0
    trim_boundary = min(
        safe_boundary,
        retention_boundary,
        key=_stream_id_tuple,
    )
    if _stream_id_tuple(trim_boundary) == (0, 0):
        return 0
    trimmed = await redis_client.xtrim(
        stream_name,
        minid=trim_boundary,
        approximate=False,
    )
    if state is not None:
        state.safe_boundary = safe_boundary
    return trimmed


class ClickAnalyticsWorker:
    def __init__(
        self,
        redis_client: ClickStreamClient,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        consumer_name: str | None = None,
    ) -> None:
        self.redis_client = redis_client
        self.session_factory = session_factory
        self.settings = settings
        self.stream_name = settings.analytics_stream_name
        self.group_name = settings.analytics_consumer_group
        self.consumer_name = consumer_name or (
            f"{socket.gethostname()}-{uuid4().hex}"
        )
        self.pending_cursor = "0-0"
        self.trim_state = StreamTrimState()
        self.next_trim_at: float | None = None

    async def persist_and_ack(
        self,
        stream_id: str,
        fields: Mapping[str | bytes, str | bytes],
    ) -> None:
        event_id, link_id, clicked_at = _parse_click_event(fields)
        async with self.session_factory() as session:
            async with session.begin():
                inserted = await session.execute(
                    insert(ClickEvent)
                    .values(
                        event_id=event_id,
                        link_id=link_id,
                        clicked_at=clicked_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[ClickEvent.event_id]
                    )
                    .returning(ClickEvent.event_id)
                )
                if inserted.scalar_one_or_none() is not None:
                    updated = await session.execute(
                        update(ShortLink)
                        .where(ShortLink.id == link_id)
                        .values(clicks_total=ShortLink.clicks_total + 1)
                    )
                    if updated.rowcount != 1:
                        raise ValueError(
                            "Click event references a missing short link"
                        )
        await self.redis_client.xack(
            self.stream_name,
            self.group_name,
            stream_id,
        )

    async def _process_messages(
        self,
        messages: list[tuple[str, dict[str, str]]],
    ) -> int:
        processed = 0
        for stream_id, fields in messages:
            try:
                await self.persist_and_ack(stream_id, fields)
                processed += 1
            except (
                SQLAlchemyError,
                RedisError,
                OSError,
                TimeoutError,
                ValueError,
                TypeError,
            ):
                logger.exception(
                    "Click event processing failed; stream entry remains pending",
                    extra={"stream_entry_id": stream_id},
                )
        return processed

    async def trim_if_due(self, now: float) -> int:
        if self.next_trim_at is None:
            self.next_trim_at = (
                now + self.settings.analytics_stream_trim_interval_seconds
            )
            return 0
        if now < self.next_trim_at:
            return 0
        trimmed = await trim_acknowledged_stream(
            self.redis_client,
            self.stream_name,
            self.group_name,
            self.settings.analytics_stream_max_length,
            self.trim_state,
        )
        self.next_trim_at = (
            now + self.settings.analytics_stream_trim_interval_seconds
        )
        return trimmed

    async def recover_pending(self) -> int:
        next_cursor, messages, _ = await self.redis_client.xautoclaim(
            self.stream_name,
            self.group_name,
            self.consumer_name,
            self.settings.analytics_pending_idle_ms,
            start_id=self.pending_cursor,
            count=self.settings.analytics_batch_size,
        )
        self.pending_cursor = next_cursor
        return await self._process_messages(messages)

    async def read_new(self) -> int:
        streams = await self.redis_client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {self.stream_name: ">"},
            count=self.settings.analytics_batch_size,
            block=self.settings.analytics_block_ms,
        )
        messages = [
            message
            for _, entries in streams
            for message in entries
        ]
        return await self._process_messages(messages)

    async def report_lag(self) -> None:
        groups = await self.redis_client.xinfo_groups(self.stream_name)
        group_info = next(
            (
                group
                for group in groups
                if _mapping_value(group, "name") == self.group_name
                or _mapping_value(group, "name")
                == self.group_name.encode()
            ),
            None,
        )
        if group_info is None:
            logger.warning("Analytics consumer group is missing")
            return
        logger.info(
            "Analytics stream lag",
            extra={
                "pending_count": _mapping_value(group_info, "pending"),
                "lag": _mapping_value(group_info, "lag"),
            },
        )

    async def run_forever(self) -> None:
        consumer_group_ready = False
        next_lag_report = asyncio.get_running_loop().time()
        while True:
            try:
                if not consumer_group_ready:
                    await ensure_consumer_group(
                        self.redis_client,
                        self.stream_name,
                        self.group_name,
                    )
                    consumer_group_ready = True
                await self.recover_pending()
                await self.read_new()
                now = asyncio.get_running_loop().time()
                await self.trim_if_due(now)
                if now >= next_lag_report:
                    await self.report_lag()
                    next_lag_report = now + (
                        self.settings.analytics_lag_log_interval_seconds
                    )
            except (RedisError, TimeoutError):
                logger.exception("Analytics worker Redis operation failed")
                await asyncio.sleep(
                    self.settings.analytics_retry_delay_seconds
                )


async def run_worker(settings: Settings | None = None) -> None:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    current_settings = settings or get_settings()
    engine = create_async_engine(
        current_settings.database_url.get_secret_value(),
        pool_size=current_settings.db_pool_size,
        max_overflow=current_settings.db_max_overflow,
        pool_timeout=current_settings.db_pool_timeout_seconds,
        connect_args={"timeout": current_settings.db_connect_timeout_seconds},
        pool_pre_ping=True,
    )
    redis_client = Redis.from_url(
        current_settings.redis_url.get_secret_value(),
        max_connections=current_settings.redis_max_connections,
        socket_connect_timeout=current_settings.redis_connect_timeout_seconds,
        socket_timeout=current_settings.redis_socket_timeout_seconds,
        decode_responses=True,
    )
    try:
        factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        worker = ClickAnalyticsWorker(redis_client, factory, current_settings)
        await worker.run_forever()
    finally:
        try:
            await redis_client.aclose()
        finally:
            await engine.dispose()
