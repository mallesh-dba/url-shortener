import asyncio
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from redis.exceptions import RedisError, ResponseError

from url_shortener.analytics import (
    ClickAnalyticsWorker,
    StreamTrimState,
    ensure_consumer_group,
    publish_click_event,
    trim_acknowledged_stream,
)
from url_shortener.config import Settings


def async_test(
    function: Callable[..., Coroutine[Any, Any, None]],
) -> Callable[..., None]:
    @wraps(function)
    def run(*args: Any, **kwargs: Any) -> None:
        asyncio.run(function(*args, **kwargs))

    return run


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
    )


def click_fields(
    event_id: UUID | None = None,
) -> dict[str, str]:
    return {
        "event_id": str(event_id or UUID("11111111-1111-4111-8111-111111111111")),
        "link_id": "42",
        "clicked_at": "2026-10-10T12:00:00+00:00",
    }


class FakeResult:
    def __init__(
        self,
        inserted_event_id: UUID | None = None,
        rowcount: int = 1,
    ) -> None:
        self.inserted_event_id = inserted_event_id
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> UUID | None:
        return self.inserted_event_id


class FakeTransaction:
    def __init__(self, session: "FakeSession") -> None:
        self.session = session

    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(
        self,
        error_type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: object,
    ) -> bool:
        _ = (_error, _traceback)
        if error_type is None:
            if self.session.commit_error is not None:
                self.session.rolled_back = True
                raise self.session.commit_error
            self.session.committed = True
        else:
            self.session.rolled_back = True
        return False


class FakeSession:
    def __init__(self, results: list[FakeResult | BaseException]) -> None:
        self.results = iter(results)
        self.executed_statements: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.commit_error: BaseException | None = None

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(
        self,
        _error_type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: object,
    ) -> bool:
        _ = (_error_type, _error, _traceback)
        return False

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def execute(self, statement: object) -> FakeResult:
        self.executed_statements.append(statement)
        result = next(self.results)
        if isinstance(result, BaseException):
            raise result
        return result


def make_worker(
    redis_client: AsyncMock,
    session: FakeSession,
) -> ClickAnalyticsWorker:
    redis_client.xlen.return_value = 0
    session_factory = lambda: session
    return ClickAnalyticsWorker(
        redis_client,
        session_factory,  # type: ignore[arg-type]
        make_settings(),
        consumer_name="worker-test",
    )


@async_test
async def test_click_event_producer_emits_minimal_utc_event() -> None:
    redis_client = AsyncMock()

    await publish_click_event(redis_client, 42, "clicks:test")

    redis_client.xadd.assert_awaited_once()
    stream, fields = redis_client.xadd.await_args.args
    assert stream == "clicks:test"
    assert set(fields) == {"event_id", "link_id", "clicked_at"}
    assert UUID(fields["event_id"])
    assert fields["link_id"] == "42"
    assert datetime.fromisoformat(fields["clicked_at"]).utcoffset() == timedelta(0)


@async_test
async def test_click_event_publish_failure_is_logged_as_best_effort() -> None:
    redis_client = AsyncMock()
    redis_client.xadd.side_effect = RedisError("redis unavailable")

    await publish_click_event(redis_client, 42)

    redis_client.xadd.assert_awaited_once()


@async_test
async def test_consumer_group_creation_ignores_only_existing_group_error() -> None:
    redis_client = AsyncMock()

    async def already_exists(*_args: object, **_kwargs: object) -> None:
        _ = (_args, _kwargs)
        raise ResponseError("BUSYGROUP Consumer Group name already exists")

    redis_client.xgroup_create.side_effect = already_exists
    await ensure_consumer_group(redis_client, "clicks:v1", "click-analytics:v1")
    redis_client.xgroup_create.assert_awaited_once_with(
        "clicks:v1",
        "click-analytics:v1",
        id="0-0",
        mkstream=True,
    )


@async_test
async def test_worker_retries_consumer_group_creation_after_redis_failure() -> None:
    session = FakeSession([])
    redis_client = AsyncMock()
    redis_client.xgroup_create.side_effect = [
        RedisError("redis unavailable during startup"),
        None,
    ]
    worker = make_worker(redis_client, session)
    worker.recover_pending = AsyncMock(return_value=0)
    worker.read_new = AsyncMock(side_effect=RuntimeError("stop test loop"))

    with (
        patch("url_shortener.analytics.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(RuntimeError, match="stop test loop"),
    ):
        await worker.run_forever()

    assert redis_client.xgroup_create.await_count == 2
    sleep.assert_awaited_once_with(
        make_settings().analytics_retry_delay_seconds
    )
    worker.recover_pending.assert_awaited_once()


@async_test
async def test_worker_commits_event_and_increment_before_acknowledging() -> None:
    event_id = UUID("11111111-1111-4111-8111-111111111111")
    session = FakeSession(
        [FakeResult(inserted_event_id=event_id), FakeResult(rowcount=1)]
    )
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)

    async def verify_committed_before_ack(
        stream: str,
        group: str,
        stream_id: str,
    ) -> int:
        assert session.committed
        assert (stream, group, stream_id) == (
            "clicks:v1",
            "click-analytics:v1",
            "1710000000000-0",
        )
        return 1

    redis_client.xack.side_effect = verify_committed_before_ack

    await worker.persist_and_ack("1710000000000-0", click_fields(event_id))

    assert len(session.executed_statements) == 2
    assert session.committed
    redis_client.xack.assert_awaited_once()


@async_test
async def test_duplicate_delivery_does_not_increment_click_counter_again() -> None:
    session = FakeSession([FakeResult(inserted_event_id=None)])
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)

    await worker.persist_and_ack("1710000000000-0", click_fields())

    assert len(session.executed_statements) == 1
    assert session.committed
    redis_client.xack.assert_awaited_once()


@async_test
async def test_database_failure_rolls_back_and_leaves_event_unacknowledged() -> None:
    session = FakeSession([RuntimeError("database failed")])
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)

    with pytest.raises(RuntimeError, match="database failed"):
        await worker.persist_and_ack("1710000000000-0", click_fields())

    assert session.rolled_back
    assert not session.committed
    redis_client.xack.assert_not_awaited()


@async_test
async def test_counter_update_failure_rolls_back_event_insert_and_does_not_ack() -> None:
    event_id = UUID("11111111-1111-4111-8111-111111111111")
    session = FakeSession(
        [FakeResult(inserted_event_id=event_id), RuntimeError("counter failed")]
    )
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)

    with pytest.raises(RuntimeError, match="counter failed"):
        await worker.persist_and_ack("1710000000000-0", click_fields(event_id))

    assert len(session.executed_statements) == 2
    assert session.rolled_back
    assert not session.committed
    redis_client.xack.assert_not_awaited()


@async_test
async def test_commit_failure_leaves_stream_entry_unacknowledged() -> None:
    event_id = UUID("11111111-1111-4111-8111-111111111111")
    session = FakeSession(
        [FakeResult(inserted_event_id=event_id), FakeResult(rowcount=1)]
    )
    session.commit_error = RuntimeError("commit failed")
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)

    with pytest.raises(RuntimeError, match="commit failed"):
        await worker.persist_and_ack("1710000000000-0", click_fields(event_id))

    assert session.rolled_back
    assert not session.committed
    redis_client.xack.assert_not_awaited()


@async_test
async def test_commit_then_ack_failure_can_be_replayed_idempotently() -> None:
    event_id = UUID("11111111-1111-4111-8111-111111111111")
    session = FakeSession(
        [
            FakeResult(inserted_event_id=event_id),
            FakeResult(rowcount=1),
            FakeResult(inserted_event_id=None),
        ]
    )
    redis_client = AsyncMock()
    worker = make_worker(redis_client, session)
    redis_client.xack.side_effect = [
        RedisError("ack lost after commit"),
        1,
    ]
    message = ("1710000000000-0", click_fields(event_id))

    assert await worker._process_messages([message]) == 0
    assert session.committed
    assert await worker._process_messages([message]) == 1

    assert len(session.executed_statements) == 3
    assert redis_client.xack.await_count == 2


@async_test
async def test_worker_recovers_pending_entries_before_reading_new_messages() -> None:
    session = FakeSession(
        [FakeResult(inserted_event_id=UUID(click_fields()["event_id"])), FakeResult()]
    )
    redis_client = AsyncMock()
    redis_client.xautoclaim.return_value = (
        "0-0",
        [("1710000000000-0", click_fields())],
        [],
    )
    worker = make_worker(redis_client, session)

    assert await worker.recover_pending() == 1

    redis_client.xautoclaim.assert_awaited_once_with(
        "clicks:v1",
        "click-analytics:v1",
        "worker-test",
        60_000,
        start_id="0-0",
        count=100,
    )
    redis_client.xreadgroup.assert_not_awaited()
    redis_client.xack.assert_awaited_once()


@async_test
async def test_worker_advances_pending_recovery_cursor_between_batches() -> None:
    session = FakeSession([])
    redis_client = AsyncMock()
    redis_client.xautoclaim.side_effect = [
        ("1710000000000-0", [], []),
        ("0-0", [], []),
    ]
    worker = make_worker(redis_client, session)

    assert await worker.recover_pending() == 0
    assert await worker.recover_pending() == 0

    assert redis_client.xautoclaim.await_args_list[0].kwargs["start_id"] == "0-0"
    assert (
        redis_client.xautoclaim.await_args_list[1].kwargs["start_id"]
        == "1710000000000-0"
    )


@async_test
async def test_worker_reads_new_messages_from_its_consumer_group() -> None:
    session = FakeSession(
        [FakeResult(inserted_event_id=UUID(click_fields()["event_id"])), FakeResult()]
    )
    redis_client = AsyncMock()
    redis_client.xreadgroup.return_value = [
        ("clicks:v1", [("1710000000000-0", click_fields())])
    ]
    worker = make_worker(redis_client, session)

    assert await worker.read_new() == 1

    redis_client.xreadgroup.assert_awaited_once_with(
        "click-analytics:v1",
        "worker-test",
        {"clicks:v1": ">"},
        count=100,
        block=1000,
    )
    redis_client.xack.assert_awaited_once()


@async_test
@pytest.mark.parametrize(
    ("pending_id", "expected_boundary"),
    [("150-0", "101-0"), ("90-0", "90-0")],
)
async def test_stream_trim_preserves_pending_and_recent_entries(
    pending_id: str,
    expected_boundary: str,
) -> None:
    redis_client = AsyncMock()
    redis_client.xlen.return_value = 120
    redis_client.xinfo_groups.return_value = [
        {
            "name": "click-analytics:v1",
            "last-delivered-id": "200-0",
        }
    ]
    redis_client.xpending_range.return_value = [{"message_id": pending_id}]
    redis_client.xrevrange.return_value = [
        (f"{200 - index}-0", {}) for index in range(100)
    ]
    redis_client.xtrim.return_value = 0

    trimmed = await trim_acknowledged_stream(
        redis_client,
        "clicks:v1",
        "click-analytics:v1",
        100,
    )

    assert trimmed == 0
    redis_client.xtrim.assert_awaited_once_with(
        "clicks:v1",
        minid=expected_boundary,
        approximate=False,
    )


@async_test
async def test_stream_without_pending_entries_trims_only_delivered_prefix() -> None:
    redis_client = AsyncMock()
    redis_client.xlen.return_value = 120
    redis_client.xinfo_groups.return_value = [
        {
            "name": "click-analytics:v1",
            "last-delivered-id": "150-0",
        }
    ]
    redis_client.xpending_range.return_value = []
    redis_client.xrevrange.return_value = [
        (f"{200 - index}-0", {}) for index in range(100)
    ]
    redis_client.xtrim.return_value = 50

    trimmed = await trim_acknowledged_stream(
        redis_client,
        "clicks:v1",
        "click-analytics:v1",
        100,
    )

    assert trimmed == 50
    redis_client.xtrim.assert_awaited_once_with(
        "clicks:v1",
        minid="101-0",
        approximate=False,
    )


@async_test
async def test_stream_trim_respects_pending_entries_in_every_consumer_group() -> None:
    redis_client = AsyncMock()
    redis_client.xlen.return_value = 120
    redis_client.xinfo_groups.return_value = [
        {"name": "click-analytics:v1", "last-delivered-id": "200-0"},
        {"name": "archive-worker", "last-delivered-id": "190-0"},
    ]
    redis_client.xpending_range.side_effect = [
        [{"message_id": "150-0"}],
        [{"message_id": "90-0"}],
    ]
    redis_client.xrevrange.return_value = [
        (f"{200 - index}-0", {}) for index in range(100)
    ]
    redis_client.xtrim.return_value = 10

    trimmed = await trim_acknowledged_stream(
        redis_client,
        "clicks:v1",
        "click-analytics:v1",
        100,
    )

    assert trimmed == 10
    assert redis_client.xpending_range.await_count == 2
    redis_client.xtrim.assert_awaited_once_with(
        "clicks:v1",
        minid="90-0",
        approximate=False,
    )


@async_test
async def test_unchanged_safe_boundary_skips_retention_window_fetch() -> None:
    redis_client = AsyncMock()
    redis_client.xlen.return_value = 120
    redis_client.xinfo_groups.return_value = [
        {
            "name": "click-analytics:v1",
            "last-delivered-id": "200-0",
        }
    ]
    redis_client.xpending_range.return_value = [{"message_id": "150-0"}]
    redis_client.xrevrange.return_value = [
        (f"{200 - index}-0", {}) for index in range(100)
    ]
    redis_client.xtrim.return_value = 10
    state = StreamTrimState()

    await trim_acknowledged_stream(
        redis_client,
        "clicks:v1",
        "click-analytics:v1",
        100,
        state,
    )
    await trim_acknowledged_stream(
        redis_client,
        "clicks:v1",
        "click-analytics:v1",
        100,
        state,
    )

    assert redis_client.xrevrange.await_count == 1
    assert redis_client.xtrim.await_count == 1


@async_test
async def test_worker_trimming_runs_on_interval_not_for_each_batch() -> None:
    session = FakeSession([])
    redis_client = AsyncMock()
    redis_client.xlen.return_value = 0
    worker = make_worker(redis_client, session)

    assert await worker._process_messages([]) == 0
    assert redis_client.xlen.await_count == 0

    assert await worker.trim_if_due(100.0) == 0
    assert await worker.trim_if_due(159.0) == 0
    assert redis_client.xlen.await_count == 0
    assert await worker.trim_if_due(160.0) == 0
    assert redis_client.xlen.await_count == 1
