from dataclasses import dataclass
import asyncio
import time

from scripts.load_test import histogram_percentile, percentile, run_load


@dataclass
class FakeResponse:
    status_code: int


class SlowClient:
    async def get(self, *_args, **_kwargs) -> FakeResponse:
        await asyncio.sleep(0.03)
        return FakeResponse(302)

    async def post(self, *_args, **_kwargs) -> FakeResponse:
        await asyncio.sleep(0.03)
        return FakeResponse(201)


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4, 5], 0.95) == 5


def test_percentile_sorts_values_before_selecting_nearest_rank() -> None:
    assert percentile([5, 1, 4, 2, 3], 0.50) == 3


def test_percentile_returns_none_for_empty_input() -> None:
    assert percentile([], 0.95) is None


def test_service_histogram_percentile_uses_delta_buckets() -> None:
    before = {
        (
            "url_shortener_http_request_duration_seconds_bucket",
            (("le", "0.01"), ("method", "GET"), ("route", "/{code}")),
        ): 2.0,
        (
            "url_shortener_http_request_duration_seconds_bucket",
            (("le", "+Inf"), ("method", "GET"), ("route", "/{code}")),
        ): 2.0,
    }
    after = {
        **before,
        (
            "url_shortener_http_request_duration_seconds_bucket",
            (("le", "0.01"), ("method", "GET"), ("route", "/{code}")),
        ): 3.0,
        (
            "url_shortener_http_request_duration_seconds_bucket",
            (("le", "0.05"), ("method", "GET"), ("route", "/{code}")),
        ): 7.0,
        (
            "url_shortener_http_request_duration_seconds_bucket",
            (("le", "+Inf"), ("method", "GET"), ("route", "/{code}")),
        ): 7.0,
    }

    assert histogram_percentile(
        before,
        after,
        "GET",
        "/{code}",
        0.95,
    ) == 50.0


def test_fixed_rate_scheduler_skips_missed_slots_instead_of_backlogging() -> None:
    async def exercise() -> tuple[int, float]:
        started = time.monotonic()
        stats, warmup_stats, tail_stats, _ = await run_load(
            client=SlowClient(),
            links=[(1, "Ab12Cd34", "https://example.com/seed")],
            marker="bench-test",
            redirect_rate=100,
            creation_rate=1,
            warmup_seconds=0,
            duration_seconds=1,
            concurrency=1,
            cache_mode="warm",
        )
        completed = sum(
            len(group[operation].latencies_ms)
            for group in (stats, warmup_stats, tail_stats)
            for operation in ("redirect", "creation")
        )
        return completed, time.monotonic() - started

    completed, elapsed = asyncio.run(exercise())

    assert 25 <= completed <= 45
    assert elapsed < 4.5
