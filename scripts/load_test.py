import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass, field
import json
import math
import os
import platform
import random
import secrets
import string
import sys
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from prometheus_client.parser import text_string_to_metric_families
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from url_shortener.config import Settings, get_settings
from url_shortener.models import ClickEvent, ShortLink


BASE62 = string.digits + string.ascii_uppercase + string.ascii_lowercase


@dataclass
class WorkItem:
    operation: str
    sequence: int
    scheduled_at: float


@dataclass
class OperationStats:
    latencies_ms: list[float] = field(default_factory=list)
    queue_delays_ms: list[float] = field(default_factory=list)
    statuses: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)

    def record(
        self,
        latency_ms: float,
        status: int | None,
        error: str | None,
        queue_delay_ms: float,
    ) -> None:
        self.latencies_ms.append(latency_ms)
        self.queue_delays_ms.append(queue_delay_ms)
        if status is not None:
            self.statuses[str(status)] += 1
        if error is not None:
            self.errors[error] += 1

    def summary(self, duration_seconds: float) -> dict[str, Any]:
        ordered = sorted(self.latencies_ms)
        return {
            "completed": len(ordered),
            "requests_per_second": round(
                len(ordered) / duration_seconds, 2
            ),
            "status_counts": dict(self.statuses),
            "errors": dict(self.errors),
            "client_queue_delay_ms": {
                "p95": percentile(self.queue_delays_ms, 0.95),
                "max": (
                    round(max(self.queue_delays_ms), 2)
                    if self.queue_delays_ms
                    else None
                ),
            },
            "latency_ms": {
                "p50": percentile(ordered, 0.50),
                "p95": percentile(ordered, 0.95),
                "p99": percentile(ordered, 0.99),
                "max": round(ordered[-1], 2) if ordered else None,
            },
        }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return round(ordered[index], 2)


def latency_summary(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    return {
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "max": round(ordered[-1], 2) if ordered else None,
    }


def parse_metrics(text: str) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
    result: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            labels = tuple(sorted(sample.labels.items()))
            result[(sample.name, labels)] = float(sample.value)
    return result


def metric_value(
    metrics: dict[tuple[str, tuple[tuple[str, str], ...]], float],
    name: str,
    **labels: str,
) -> float | None:
    return metrics.get((name, tuple(sorted(labels.items()))))


def histogram_percentile(
    before: dict[tuple[str, tuple[tuple[str, str], ...]], float],
    after: dict[tuple[str, tuple[tuple[str, str], ...]], float],
    method: str,
    route: str,
    quantile: float,
) -> float | None:
    buckets: list[tuple[float, float]] = []
    for key, end_value in after.items():
        name, labels_tuple = key
        labels = dict(labels_tuple)
        if (
            name != "url_shortener_http_request_duration_seconds_bucket"
            or labels.get("method") != method
            or labels.get("route") != route
        ):
            continue
        start_value = before.get(key, 0.0)
        buckets.append((float(labels["le"]), end_value - start_value))
    buckets.sort(key=lambda item: item[0])
    total = next((count for bound, count in buckets if math.isinf(bound)), 0.0)
    if total <= 0:
        return None
    target = total * quantile
    cumulative = 0.0
    for bound, count in buckets:
        cumulative = count
        if cumulative >= target:
            return None if math.isinf(bound) else round(bound * 1000, 2)
    return None


async def fetch_metrics(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    response.raise_for_status()
    return parse_metrics(response.text)


def make_codes(count: int) -> list[str]:
    return [
        "".join(secrets.choice(BASE62) for _ in range(8))
        for _ in range(count)
    ]


async def seed_links(
    settings: Settings,
    marker: str,
    count: int,
    cache_mode: str,
) -> list[tuple[int, str, str]]:
    engine = create_async_engine(settings.database_url.get_secret_value())
    redis_client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
    )
    codes = make_codes(count)
    destination_prefix = f"https://example.com/{marker}/"
    try:
        async with engine.begin() as connection:
            links: list[tuple[int, str, str]] = []
            for start in range(0, count, 5000):
                batch = codes[start : start + 5000]
                result = await connection.execute(
                    insert(ShortLink)
                    .values(
                        [
                            {
                                "code": code,
                                "destination_url": (
                                    f"{destination_prefix}seed-{start + index}"
                                ),
                                "clicks_total": 0,
                            }
                            for index, code in enumerate(batch)
                        ]
                    )
                    .returning(
                        ShortLink.id,
                        ShortLink.code,
                        ShortLink.destination_url,
                    )
                )
                links.extend(
                    (row.id, row.code, row.destination_url)
                    for row in result
                )
        if cache_mode == "warm":
            for link_id, code, destination_url in links:
                cache_value = json.dumps(
                    {
                        "link_id": link_id,
                        "destination_url": destination_url,
                    },
                    separators=(",", ":"),
                )
                await redis_client.set(
                    f"short:v1:{code}",
                    cache_value,
                    ex=settings.link_cache_ttl_seconds,
                )
        else:
            for start in range(0, len(codes), 1000):
                keys = [f"short:v1:{code}" for code in codes[start : start + 1000]]
                await redis_client.delete(*keys)
        return links
    except Exception:
        async with engine.begin() as connection:
            await connection.execute(
                delete(ShortLink).where(
                    ShortLink.destination_url.startswith(destination_prefix)
                )
            )
        raise
    finally:
        await redis_client.aclose()
        await engine.dispose()


async def current_stream_id(redis_client: Redis, stream_name: str) -> str:
    try:
        info = await redis_client.xinfo_stream(stream_name)
    except ResponseError as error:
        if "no such key" in str(error).lower():
            return "0-0"
        raise
    return str(info["last-generated-id"])


async def run_load(
    client: httpx.AsyncClient,
    links: list[tuple[int, str, str]],
    marker: str,
    redirect_rate: int,
    creation_rate: int,
    warmup_seconds: int,
    duration_seconds: int,
    concurrency: int,
    cache_mode: str,
) -> tuple[
    dict[str, OperationStats],
    dict[str, OperationStats],
    dict[str, OperationStats],
    float | None,
]:
    queue: asyncio.Queue[WorkItem | None] = asyncio.Queue(
        maxsize=concurrency * 4
    )
    stats = {
        "redirect": OperationStats(),
        "creation": OperationStats(),
    }
    warmup_stats = {
        "redirect": OperationStats(),
        "creation": OperationStats(),
    }
    tail_stats = {
        "redirect": OperationStats(),
        "creation": OperationStats(),
    }
    schedule_lateness_ms: list[float] = []
    start_at = asyncio.get_running_loop().time() + 2
    measure_at = start_at + warmup_seconds
    stop_at = measure_at + duration_seconds
    randomizer = random.Random(110)
    weights = [1 / ((index + 1) ** 1.05) for index in range(len(links))]
    cold_index = 0

    async def produce(operation: str, rate: int) -> None:
        nonlocal cold_index
        deadline = start_at
        sequence = 0
        interval = 1 / rate
        loop = asyncio.get_running_loop()
        while True:
            now = loop.time()
            if now >= stop_at:
                break
            if now > deadline:
                missed_slots = int((now - deadline) / interval)
                sequence += missed_slots
                deadline = start_at + sequence * interval
            if deadline >= stop_at:
                break
            delay = deadline - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            if loop.time() >= stop_at:
                break
            await queue.put(
                WorkItem(
                    operation=operation,
                    sequence=sequence,
                    scheduled_at=deadline,
                )
            )
            now = loop.time()
            schedule_lateness_ms.append(max(0, now - deadline) * 1000)
            sequence += 1
            deadline = start_at + sequence * interval

    async def consume() -> None:
        nonlocal cold_index
        while True:
            item = await queue.get()
            try:
                if item is None:
                    return
                request_started = asyncio.get_running_loop().time()
                queue_delay_ms = max(
                    0,
                    request_started - item.scheduled_at,
                ) * 1000
                if item.operation == "redirect":
                    if len(links) == 0:
                        raise RuntimeError("No seeded links available")
                    if cache_mode == "cold":
                        link_index = cold_index
                        cold_index += 1
                    else:
                        link_index = randomizer.choices(
                            range(len(links)), weights=weights, k=1
                        )[0]
                    _, code, _ = links[link_index]
                    request = client.get(f"/{code}", follow_redirects=False)
                else:
                    request = client.post(
                        "/api/v1/shorten",
                        json={
                            "destination_url": (
                                f"https://example.com/{marker}/created-"
                                f"{item.sequence}"
                            )
                        },
                    )
                started = time.perf_counter()
                try:
                    response = await request
                    elapsed = (time.perf_counter() - started) * 1000
                    expected = 302 if item.operation == "redirect" else 201
                    error = (
                        None
                        if response.status_code == expected
                        else f"unexpected_http_{response.status_code}"
                    )
                    status = response.status_code
                except httpx.HTTPError as error:
                    elapsed = (time.perf_counter() - started) * 1000
                    status = None
                    error = type(error).__name__
                if measure_at <= request_started < stop_at:
                    stats[item.operation].record(
                        elapsed,
                        status,
                        error,
                        queue_delay_ms,
                    )
                elif request_started < measure_at:
                    warmup_stats[item.operation].record(
                        elapsed,
                        status,
                        error,
                        queue_delay_ms,
                    )
                else:
                    tail_stats[item.operation].record(
                        elapsed,
                        status,
                        error,
                        queue_delay_ms,
                    )
            finally:
                queue.task_done()

    producers = [
        asyncio.create_task(produce("redirect", redirect_rate)),
        asyncio.create_task(produce("creation", creation_rate)),
    ]
    consumers = [
        asyncio.create_task(consume())
        for _ in range(concurrency)
    ]
    await asyncio.gather(*producers)
    await queue.join()
    for _ in consumers:
        await queue.put(None)
    await asyncio.gather(*consumers)
    return (
        stats,
        warmup_stats,
        tail_stats,
        percentile(schedule_lateness_ms, 0.95),
    )


async def count_test_events(
    engine_url: str,
    marker: str,
) -> int:
    engine = create_async_engine(engine_url)
    try:
        async with engine.connect() as connection:
            return int(
                await connection.scalar(
                    select(func.count(ClickEvent.event_id))
                    .join(ShortLink, ShortLink.id == ClickEvent.link_id)
                    .where(
                        ShortLink.destination_url.startswith(
                            f"https://example.com/{marker}/"
                        )
                    )
                )
                or 0
            )
    finally:
        await engine.dispose()


async def cleanup_test_data(
    settings: Settings,
    marker: str,
    start_stream_id: str,
) -> None:
    engine = create_async_engine(settings.database_url.get_secret_value())
    redis_client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
    )
    prefix = f"https://example.com/{marker}/"
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(ShortLink.id, ShortLink.code).where(
                        ShortLink.destination_url.startswith(prefix)
                    )
                )
            ).all()
        link_ids = {int(row.id) for row in rows}
        cache_keys = [f"short:v1:{row.code}" for row in rows]
        if cache_keys:
            for start in range(0, len(cache_keys), 1000):
                await redis_client.delete(*cache_keys[start : start + 1000])

        end_stream_id = await current_stream_id(
            redis_client,
            settings.analytics_stream_name,
        )
        cursor = start_stream_id
        while True:
            entries = await redis_client.xrange(
                settings.analytics_stream_name,
                min=f"({cursor}",
                max=end_stream_id,
                count=1000,
            )
            if not entries:
                break
            matching_ids = [
                entry_id
                for entry_id, fields in entries
                if fields.get("link_id", "").isdigit()
                and int(fields["link_id"]) in link_ids
            ]
            if matching_ids:
                await redis_client.xdel(
                    settings.analytics_stream_name,
                    *matching_ids,
                )
            cursor = entries[-1][0]

        if link_ids:
            benchmark_link_ids = select(ShortLink.id).where(
                ShortLink.destination_url.startswith(prefix)
            )
            async with engine.begin() as connection:
                await connection.execute(
                    delete(ClickEvent).where(ClickEvent.link_id.in_(benchmark_link_ids))
                )
                await connection.execute(
                    delete(ShortLink).where(
                        ShortLink.destination_url.startswith(prefix)
                    )
                )
    finally:
        await redis_client.aclose()
        await engine.dispose()


async def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    marker = f"bench-{uuid4().hex}"
    print(f"Benchmark run marker: {marker}", file=sys.stderr, flush=True)
    timeout = httpx.Timeout(args.request_timeout_seconds)
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
    )
    metrics_data: dict[str, Any] = {
        "api": [],
        "worker": [],
        "postgres_probe_ms": [],
        "redis_probe_ms": [],
        "errors": [],
    }
    stop_monitor = asyncio.Event()

    async with (
        httpx.AsyncClient(
            base_url=args.base_url.rstrip("/"),
            timeout=timeout,
            limits=limits,
        ) as client,
        httpx.AsyncClient(timeout=5) as metrics_client,
    ):
        health = await client.get("/health/ready")
        health.raise_for_status()
        api_before = await fetch_metrics(
            metrics_client,
            args.api_metrics_url,
        )
        worker_before = await fetch_metrics(
            metrics_client,
            args.worker_metrics_url,
        )
        if (
            metric_value(
                api_before,
                "url_shortener_db_pool_checked_out_high_water",
            )
            is None
        ):
            raise RuntimeError(
                "API metrics endpoint is missing database pool high-water metrics"
            )
        if (
            metric_value(
                worker_before,
                "url_shortener_db_pool_checked_out_high_water",
            )
            is None
        ):
            raise RuntimeError(
                "Worker metrics endpoint is missing database pool high-water metrics"
            )
        if (
            metric_value(
                worker_before,
                "url_shortener_analytics_processed_events_total",
            )
            is None
        ):
            raise RuntimeError(
                "Worker metrics endpoint must expose the processed-event counter"
            )

        redirects_to_seed = (
            args.redirects_per_second
            * (args.duration_seconds + args.warmup_seconds)
            + 1
        )
        seed_count = (
            max(100, args.concurrency * 2)
            if args.cache_mode == "warm"
            else redirects_to_seed
        )
        links = await seed_links(
            settings,
            marker,
            seed_count,
            args.cache_mode,
        )
        redis_client = Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
        )
        start_stream_id = await current_stream_id(
            redis_client,
            settings.analytics_stream_name,
        )
        await redis_client.aclose()
        probe_engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_size=1,
            max_overflow=0,
        )
        probe_redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            max_connections=1,
            decode_responses=True,
        )

        async def monitor_metrics() -> None:
            while not stop_monitor.is_set():
                for name, url in (
                    ("api", args.api_metrics_url),
                    ("worker", args.worker_metrics_url),
                ):
                    try:
                        sample = await fetch_metrics(metrics_client, url)
                    except httpx.HTTPError as error:
                        metrics_data["errors"].append(
                            f"{name}: {type(error).__name__}: {error}"
                        )
                    else:
                        metrics_data[name].append(sample)
                started = time.perf_counter()
                try:
                    async with probe_engine.connect() as connection:
                        await connection.execute(text("SELECT 1"))
                except (SQLAlchemyError, OSError, TimeoutError) as error:
                    metrics_data["errors"].append(
                        f"postgres probe: {type(error).__name__}: {error}"
                    )
                else:
                    metrics_data["postgres_probe_ms"].append(
                        (time.perf_counter() - started) * 1000
                    )
                started = time.perf_counter()
                try:
                    await probe_redis.ping()
                except (RedisError, OSError, TimeoutError) as error:
                    metrics_data["errors"].append(
                        f"redis probe: {type(error).__name__}: {error}"
                    )
                else:
                    metrics_data["redis_probe_ms"].append(
                        (time.perf_counter() - started) * 1000
                    )
                try:
                    await asyncio.wait_for(stop_monitor.wait(), timeout=0.25)
                except TimeoutError:
                    pass

        monitor_task = asyncio.create_task(monitor_metrics())
        try:
            stats, warmup_stats, tail_stats, scheduler_p95_ms = await run_load(
                client,
                links,
                marker,
                args.redirects_per_second,
                args.creations_per_second,
                args.warmup_seconds,
                args.duration_seconds,
                args.concurrency,
                args.cache_mode,
            )
            api_after_load = await fetch_metrics(
                metrics_client,
                args.api_metrics_url,
            )
            worker_after_load = await fetch_metrics(
                metrics_client,
                args.worker_metrics_url,
            )
            expected_redirects = (
                stats["redirect"].statuses.get("302", 0)
                + warmup_stats["redirect"].statuses.get("302", 0)
                + tail_stats["redirect"].statuses.get("302", 0)
            )
            publish_failure_delta = (
                metric_value(
                    api_after_load,
                    "url_shortener_click_event_publish_failures_total",
                )
                or 0
            ) - (
                metric_value(
                    api_before,
                    "url_shortener_click_event_publish_failures_total",
                )
                or 0
            )
            expected_events = max(
                0,
                expected_redirects - int(publish_failure_delta),
            )
            engine_url = settings.database_url.get_secret_value()
            drain_start = time.monotonic()
            persisted_events = 0
            acknowledged_events = 0
            drain_timeout = (
                time.monotonic() + args.analytics_drain_timeout_seconds
            )
            while time.monotonic() < drain_timeout:
                persisted_events = await count_test_events(engine_url, marker)
                worker_during_drain = await fetch_metrics(
                    metrics_client,
                    args.worker_metrics_url,
                )
                acknowledged_events = int(
                    (
                        metric_value(
                            worker_during_drain,
                            "url_shortener_analytics_processed_events_total",
                        )
                        or 0
                    )
                    - (
                        metric_value(
                            worker_before,
                            "url_shortener_analytics_processed_events_total",
                        )
                        or 0
                    )
                )
                if (
                    persisted_events >= expected_events
                    and acknowledged_events >= expected_events
                ):
                    break
                await asyncio.sleep(1)
            drain_seconds = time.monotonic() - drain_start
            cleanup_done = (
                persisted_events >= expected_events
                and acknowledged_events >= expected_events
            )
            if cleanup_done:
                await cleanup_test_data(
                    settings,
                    marker,
                    start_stream_id,
                )
            api_after = await fetch_metrics(
                metrics_client,
                args.api_metrics_url,
            )
            worker_after = await fetch_metrics(
                metrics_client,
                args.worker_metrics_url,
            )
        finally:
            stop_monitor.set()
            await monitor_task
            await probe_redis.aclose()
            await probe_engine.dispose()

    redirect_stats = stats["redirect"]
    creation_stats = stats["creation"]
    redirect_rate_measured = redirect_stats.summary(
        args.duration_seconds
    )["requests_per_second"]
    creation_rate_measured = creation_stats.summary(
        args.duration_seconds
    )["requests_per_second"]
    observed_ratio = (
        round(redirect_rate_measured / creation_rate_measured, 2)
        if creation_rate_measured
        else None
    )

    total_duration = args.duration_seconds
    report = {
        "run_id": marker,
        "cache_mode": args.cache_mode,
        "environment": {
            "host": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "api": args.base_url,
            "database_pool_capacity": (
                settings.db_pool_size + settings.db_max_overflow
            ),
            "redis_max_connections": settings.redis_max_connections,
            "api_metrics_url": args.api_metrics_url,
            "worker_metrics_url": args.worker_metrics_url,
            "warmup_seconds": args.warmup_seconds,
            "measurement_seconds": args.duration_seconds,
            "concurrency": args.concurrency,
        },
        "target": {
            "redirects_per_second": args.redirects_per_second,
            "creations_per_second": args.creations_per_second,
            "redirect_p95_ms": 50,
            "creation_p95_ms": 200,
        },
        "measured": {
            "redirect": redirect_stats.summary(total_duration),
            "creation": creation_stats.summary(total_duration),
            "outside_measurement_window": {
                operation: {
                    "warmup_completed": len(warmup_stats[operation].latencies_ms),
                    "warmup_status_counts": dict(
                        warmup_stats[operation].statuses
                    ),
                    "tail_completed": len(tail_stats[operation].latencies_ms),
                    "tail_status_counts": dict(tail_stats[operation].statuses),
                }
                for operation in ("redirect", "creation")
            },
            "redirect_to_creation_ratio": observed_ratio,
            "client_scheduler_lateness_p95_ms": scheduler_p95_ms,
            "telemetry_sample_count": {
                name: len(samples)
                for name, samples in metrics_data.items()
                if name != "errors"
            },
            "telemetry_errors": metrics_data["errors"],
            "dependency_probe_latency_ms": {
                "postgres_select_1": latency_summary(
                    metrics_data["postgres_probe_ms"]
                ),
                "redis_ping": latency_summary(
                    metrics_data["redis_probe_ms"]
                ),
            },
            "service_histogram_p95_ms": {
                "redirect": histogram_percentile(
                    api_before,
                    api_after,
                    "GET",
                    "/{code}",
                    0.95,
                ),
                "creation": histogram_percentile(
                    api_before,
                    api_after,
                    "POST",
                    "/api/v1/shorten",
                    0.95,
                ),
            },
            "cache_lookup_delta": {
                outcome: (
                    metric_value(
                        api_after,
                        "url_shortener_cache_operations_total",
                        operation="lookup",
                        outcome=outcome,
                    )
                    or 0
                )
                - (
                    metric_value(
                        api_before,
                        "url_shortener_cache_operations_total",
                        operation="lookup",
                        outcome=outcome,
                    )
                    or 0
                )
                for outcome in ("hit", "miss", "error")
            },
            "api_pool_checked_out_sampled_peak": max(
                (
                    metric_value(
                        sample,
                        "url_shortener_db_pool_checked_out",
                    )
                    or 0
                    for sample in metrics_data["api"]
                ),
                default=metric_value(
                    api_after,
                    "url_shortener_db_pool_checked_out",
                ),
            ),
            "api_pool_capacity": metric_value(
                api_after,
                "url_shortener_db_pool_capacity",
            ),
            "worker_pool_checked_out_sampled_peak": max(
                (
                    metric_value(
                        sample,
                        "url_shortener_db_pool_checked_out",
                    )
                    or 0
                    for sample in metrics_data["worker"]
                ),
                default=metric_value(
                    worker_after,
                    "url_shortener_db_pool_checked_out",
                ),
            ),
            "worker_pool_capacity": metric_value(
                worker_after,
                "url_shortener_db_pool_capacity",
            ),
            "process_lifetime_pool_high_water": {
                "api": metric_value(
                    api_after,
                    "url_shortener_db_pool_checked_out_high_water",
                ),
                "worker": metric_value(
                    worker_after,
                    "url_shortener_db_pool_checked_out_high_water",
                ),
            },
            "analytics": {
                "expected_events": expected_events,
                "persisted_events": persisted_events,
                "acknowledged_events": acknowledged_events,
                "acknowledged_by_load_completion": int(
                    (
                        metric_value(
                            worker_after_load,
                            "url_shortener_analytics_processed_events_total",
                        )
                        or 0
                    )
                    - (
                        metric_value(
                            worker_before,
                            "url_shortener_analytics_processed_events_total",
                        )
                        or 0
                    )
                ),
                "drain_seconds": round(drain_seconds, 2),
                "post_load_drain_events_per_second": round(
                    max(
                        0,
                        acknowledged_events
                        - int(
                            (
                                metric_value(
                                    worker_after_load,
                                    "url_shortener_analytics_processed_events_total",
                                )
                                or 0
                            )
                            - (
                                metric_value(
                                    worker_before,
                                    "url_shortener_analytics_processed_events_total",
                                )
                                or 0
                            )
                        ),
                    )
                    / max(drain_seconds, 0.001),
                    2,
                ),
                "worker_stream_lag_after": metric_value(
                    worker_after,
                    "url_shortener_analytics_stream_lag",
                ),
                "worker_stream_lag_peak": max(
                    (
                        metric_value(
                            sample,
                            "url_shortener_analytics_stream_lag",
                        )
                        or 0
                        for sample in metrics_data["worker"]
                    ),
                    default=metric_value(
                        worker_after,
                        "url_shortener_analytics_stream_lag",
                    ),
                ),
                "worker_pending_after": metric_value(
                    worker_after,
                    "url_shortener_analytics_pending_events",
                ),
                "worker_pending_peak": max(
                    (
                        metric_value(
                            sample,
                            "url_shortener_analytics_pending_events",
                        )
                        or 0
                        for sample in metrics_data["worker"]
                    ),
                    default=metric_value(
                        worker_after,
                        "url_shortener_analytics_pending_events",
                    ),
                ),
            },
        },
        "acceptance": {
            "redirect_rate_met": (
                redirect_stats.summary(total_duration)["requests_per_second"]
                >= args.redirects_per_second * 0.99
            ),
            "creation_rate_met": (
                creation_rate_measured
                >= args.creations_per_second * 0.99
            ),
            "redirect_creation_ratio_met": (
                observed_ratio is not None
                and abs(observed_ratio - 100) <= 1
            ),
            "redirect_p95_met": (
                percentile(redirect_stats.latencies_ms, 0.95) is not None
                and percentile(redirect_stats.latencies_ms, 0.95) <= 50
            ),
            "creation_p95_met": (
                percentile(creation_stats.latencies_ms, 0.95) is not None
                and percentile(creation_stats.latencies_ms, 0.95) <= 200
            ),
            "all_redirects_succeeded": (
                sum(redirect_stats.statuses.values())
                == redirect_stats.statuses.get("302", 0)
                and not redirect_stats.errors
            ),
            "all_creations_succeeded": (
                sum(creation_stats.statuses.values())
                == creation_stats.statuses.get("201", 0)
                and not creation_stats.errors
            ),
            "telemetry_complete": not metrics_data["errors"],
            "analytics_drained": (
                persisted_events >= expected_events
                and acknowledged_events >= expected_events
            ),
            "cleanup_done": cleanup_done,
        },
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fixed-rate URL shortener capacity/latency benchmark"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-metrics-url", default="http://127.0.0.1:9100/")
    parser.add_argument(
        "--worker-metrics-url",
        default="http://127.0.0.1:9101/",
    )
    parser.add_argument(
        "--cache-mode",
        choices=("warm", "cold"),
        default="warm",
    )
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--warmup-seconds", type=int, default=15)
    parser.add_argument("--redirects-per-second", type=int, default=1000)
    parser.add_argument("--creations-per-second", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=500)
    parser.add_argument("--request-timeout-seconds", type=float, default=10)
    parser.add_argument("--analytics-drain-timeout-seconds", type=int, default=120)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--cleanup-marker")
    parser.add_argument(
        "--output",
        default="docs/t110-local-load-test.json",
    )
    args = parser.parse_args()
    host = urlsplit(args.base_url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"} and not args.allow_remote:
        parser.error("Refusing non-local target without --allow-remote")
    if min(
        args.duration_seconds,
        args.redirects_per_second,
        args.creations_per_second,
        args.concurrency,
    ) < 1:
        parser.error("rates, concurrency, and duration must be positive")
    if args.warmup_seconds < 0:
        parser.error("warm-up must not be negative")
    return args


async def main() -> None:
    args = parse_args()
    if args.cleanup_marker:
        if not args.cleanup_marker.startswith("bench-"):
            raise SystemExit("Cleanup marker must start with 'bench-'")
        await cleanup_test_data(
            get_settings(),
            args.cleanup_marker,
            "0-0",
        )
        print(f"Cleaned benchmark data for {args.cleanup_marker}")
        return
    report = await benchmark(args)
    output = json.dumps(report, indent=2)
    print(output)
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as report_file:
        report_file.write(output + "\n")
    if not all(report["acceptance"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
