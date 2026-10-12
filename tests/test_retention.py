import asyncio
from datetime import UTC, date, datetime

from url_shortener.analytics import cleanup_expired_analytics
from url_shortener.config import Settings
from url_shortener.retention import months_before


class FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class FakeTransaction:
    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(
        self,
        _error_type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: object,
    ) -> bool:
        return False


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(
        self,
        _error_type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: object,
    ) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(2)


def test_months_before_handles_month_end_and_leap_year() -> None:
    assert months_before(date(2025, 3, 31), 12) == date(2024, 3, 31)
    assert months_before(date(2024, 2, 29), 12) == date(2023, 2, 28)


def test_retention_cleanup_deletes_raw_events_and_expired_rollups() -> None:
    session = FakeSession()
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/url_shortener",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
        analytics_raw_retention_days=90,
        analytics_aggregate_retention_months=12,
    )

    deleted = asyncio.run(
        cleanup_expired_analytics(
            lambda: session,  # type: ignore[arg-type]
            settings,
            datetime(2026, 10, 12, tzinfo=UTC),
        )
    )

    assert deleted == (2, 2, 2)
    assert len(session.statements) == 3
    sql = "\n".join(str(statement) for statement in session.statements)
    assert "click_events" in sql
    assert "daily_click_aggregates" in sql
    assert "processed_click_event_ids" in sql
