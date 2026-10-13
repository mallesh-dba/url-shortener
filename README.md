# URL Shortener

Build a scalable URL shortener service with APIs, persistence, and analytics.

## Requirement-processing prototype

The repository includes a local, deterministic requirement-processing CLI for
the greenfield, brownfield, and ambiguous demonstration inputs. It creates
structured JSON drafts and deliberately leaves them pending human review. It
does not call an AI model; use an AI assistant separately for analysis, then
review/refine the draft before recording a decision.

After installing the project with `python -m pip install -e ".[dev]"`, run
these commands from the project root:

```powershell
python -m requirement_processor analyze examples\greenfield.txt --output output\greenfield.json
python -m requirement_processor analyze examples\brownfield.txt --output output\brownfield.json
python -m requirement_processor analyze examples\ambiguous.txt --output output\ambiguous.json
```

Review and refine a generated JSON draft before recording a human decision.
The review command writes a separate reviewed artifact and leaves the original
draft unchanged:

```powershell
python -m requirement_processor review output\greenfield.json `
  --decision accept --reviewer "Candidate" `
  --notes "Reviewed and accepted for the greenfield scenario." `
  --output output\greenfield-reviewed.json
```

Use `--decision reject` to record rejection. The CLI records the supplied
decision but does not verify that the draft was edited or determine whether
acceptance is appropriate. Run its focused checks with
`python -m pytest -q tests/test_requirement_processor.py`.

Captured AI-assisted prompts and analyses, human review outcomes, and
validation evidence are kept separately in [evidence/](evidence/README.md).
These files distinguish assistant-generated analysis from deterministic CLI
templates; the ambiguous scenario's requirements are accepted, while live
database/integration validation remains pending.

## Development setup

Requires Python 3.11 or newer. Install the project and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and update the PostgreSQL, Redis, and public base
URL settings for your environment. `URL_SHORTENER_PUBLIC_BASE_URL` is the
HTTP(S) origin used to construct returned short URLs. The example values are
for local development only; do not use them as production credentials.
Set `URL_SHORTENER_ANALYTICS_API_KEY` to a private random token of at least 32
characters before making requests. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. The API uses it
to protect analytics and to key short-lived pseudonymous rate-limit buckets;
never commit the token. The service reports not-ready and rejects limited
routes until the token is configured.
If deployed behind a trusted reverse proxy, set
`URL_SHORTENER_TRUSTED_PROXY_CIDRS` to a JSON array of the proxy IP addresses or
CIDR ranges, for example `["10.0.0.0/8"]`. Forwarded client addresses are only
used when the immediate peer matches one of these configured networks;
otherwise `X-Forwarded-For` is ignored.
This repository does not include a container-orchestration file; provision
PostgreSQL and Redis separately. The analytics worker requires Redis 6.2 or
newer.

Apply the PostgreSQL schema migration before using the link-creation API
(especially when setting up a fresh database):

```powershell
alembic upgrade head
```

Start the API:

```powershell
uvicorn url_shortener.main:app --reload --app-dir src
```

`GET /health/live` reports whether the process is running and does not contact
external services. `GET /health/ready` checks PostgreSQL, Redis, and presence
of the analytics authentication token; it returns `503` if a dependency is
unavailable or the token is not configured. The readiness response reports
dependency status without exposing connection details. The PostgreSQL readiness
probe has a configurable two-second deadline by default
(`URL_SHORTENER_DB_READINESS_TIMEOUT_SECONDS`).
The API exposes low-cardinality Prometheus metrics on a separate listener,
configured by `URL_SHORTENER_API_METRICS_HOST` and
`URL_SHORTENER_API_METRICS_PORT` (default `127.0.0.1:9100`). Scrape
`http://127.0.0.1:9100/` locally by default; `/metrics` is not a public scrape
route.
The public API reserves `/metrics` and returns `404` there; it does not serve
the scrape output on the public listener.
For a remote Prometheus server, bind the listener only to a private interface
and allow access only from the monitoring network using host/network firewall
rules. Do not publish or proxy this listener through the public API gateway.
Metric labels use route templates and do not include short codes, destination
URLs, client IP addresses, or user agents.

Create a short link with an automatically generated code:

```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/shorten `
  -ContentType application/json `
  -Body '{"destination_url":"https://example.com/path"}'
```

The API returns the generated code, its public short URL, and creation time.
Creation errors use `{"error":{"code":"...","message":"...","details":...}}`.

To request a custom alias, include the optional `custom_alias` field:

```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/shorten `
  -ContentType application/json `
  -Body '{"destination_url":"https://example.com/sale","custom_alias":"summer-sale"}'
```

Aliases must contain 3–16 lowercase ASCII letters, digits, or hyphens, and
must begin and end with a letter or digit. Uppercase, reserved route names
(`api`, `health`, `metrics`, `docs`, `redoc`, `openapi.json`), and duplicate
codes are rejected. A duplicate code returns `409` with error code
`short_code_conflict`; invalid aliases return `422`. The alias and generated
codes share the existing unique `short_links.code` namespace and database
constraint. The current `VARCHAR(16)` column already supports these rules, so
no schema migration is required. Omitting `custom_alias` preserves generated
Base62 code behavior and the existing response shape.

Follow a returned short URL to test redirect behavior:

```powershell
curl.exe -i $response.short_url
```

The redirect endpoint returns `302` with the destination in the `Location`
header. An unknown code returns `404` only after PostgreSQL confirms it does
not exist; Redis outages fall back to PostgreSQL.

Retrieve the aggregate click count for a short code:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/links/$($response.code)/analytics" `
  -Headers @{ Authorization = "Bearer $env:URL_SHORTENER_ANALYTICS_API_KEY" }
```

Analytics requires the configured bearer token. It authorizes access to all
links for any holder of the shared token; this prototype has no per-user or
per-link identity/authorization model. The response contains `code` and
`clicks_total`, the aggregate over the trailing 12 calendar months; an unknown
code returns `404`. The API reads daily aggregate rows from PostgreSQL. Since
the analytics worker updates them asynchronously from Redis Streams, they may
not include the most recent redirects until those events are processed.

The API rate limits each client address in a 60-second fixed window: 10 link
creations, 120 redirects, and 60 analytics requests. Exceeded requests receive
`429` and `Retry-After`. Address values are HMACed with the configured token
before being used as Redis keys; keys expire with the window and are not added
to click events or application logs. Rate limiting fails closed with `503` if
Redis or the required token is unavailable. Configure the trusted-proxy CIDRs
carefully; never trust forwarded-address headers from untrusted peers.

The analytics worker exposes its Prometheus metrics on the configured
`URL_SHORTENER_ANALYTICS_METRICS_HOST` and
`URL_SHORTENER_ANALYTICS_METRICS_PORT` (default `127.0.0.1:9101`). The worker
serves scrape output at `http://127.0.0.1:9101/` by default. It reports
pending-event count and stream lag; a lag value of `-1` means the Redis server
did not provide a lag value. The metrics include request latency/status, cache
outcomes, code-collision retries, current and high-water database pool
utilization, event publication failures, acknowledged event throughput, and
worker processing/retry health. Keep the worker metrics listener
private as well: use a private interface and monitoring-network firewall
allowlist for remote scraping, and do not publish it through the public API
gateway.

## Click analytics worker

Run the worker in a separate terminal from the API after applying the database
migrations. The analytics worker requires Redis 6.2 or newer for pending-entry
recovery and safe `MINID` trimming:

```powershell
python -m url_shortener.analytics_worker
```

If Redis is unavailable during startup, the worker logs the failure and retries
consumer-group initialization using `URL_SHORTENER_ANALYTICS_RETRY_DELAY_SECONDS`
instead of exiting.

Each successful redirect schedules best-effort publication of a minimal click
event (`event_id`, short-link `code`, and UTC `clicked_at`) to the configured
Redis Stream. The worker stores eligible raw events and updates the daily
aggregate idempotently in the same PostgreSQL transaction, then acknowledges
the stream entry. Malformed events and events referencing an unknown link are
logged and acknowledged so they do not remain pending indefinitely. Transient
database or Redis failures remain pending and can be reclaimed after
`URL_SHORTENER_ANALYTICS_PENDING_IDLE_MS`. The worker logs consumer-group
pending count and lag periodically.

The worker deletes raw click rows older than 90 days, aggregate day buckets
older than 12 calendar months, and event-ID deduplication markers after the
aggregate retention window. Cleanup runs hourly by default using
`URL_SHORTENER_ANALYTICS_RETENTION_INTERVAL_SECONDS`. The deduplication markers
contain only event IDs and processing timestamps so redelivered events cannot
re-increment aggregates after their raw event row expires.

The worker checks stream trimming every
`URL_SHORTENER_ANALYTICS_STREAM_TRIM_INTERVAL_SECONDS` (default 60 seconds),
not after each batch. It trims only old entries before the oldest pending entry
across all consumer groups (or each group's last-delivered entry when nothing
is pending), and retains the recent configured stream window. If the safe
boundary has not advanced since the previous trim check, the worker skips
fetching the retention window again. A stalled pending entry can therefore keep
the stream above its configured maximum rather than being deleted. Click
tracking is best effort: a process failure before the redirect background task
publishes can lose that click.

For a live smoke check, start the API and worker, create a fresh short link
using the example above, and request it once. Then inspect the persisted event,
daily aggregate, and pending queue:

```powershell
curl.exe -i $response.short_url
$sql = "SELECT l.code, COALESCE((SELECT SUM(a.clicks_total) FROM daily_click_aggregates a WHERE a.link_id = l.id), 0) AS clicks_total, (SELECT COUNT(*) FROM click_events e WHERE e.code = l.code) AS stored_events FROM short_links l WHERE l.code = '$($response.code)';"
docker exec url-shortener-postgres psql -U postgres -d url_shortener -c $sql
docker exec url-shortener-redis redis-cli XPENDING clicks:v1 click-analytics:v1
```

After the asynchronous worker catches up, expect one stored event and a daily
aggregate count of `1` for the new link, with no pending event. The count is
eventually consistent; rerun the inspection if the worker has not processed
the event yet.

Run the current tests with:

```powershell
python -m pytest -q
```

The PostgreSQL/Redis-backed cross-service test is opt-in. Configure the
development `.env`, start the PostgreSQL and Redis services, then run:

```powershell
$env:URL_SHORTENER_RUN_INTEGRATION = '1'
try {
    python -m pytest -q
}
finally {
    Remove-Item Env:URL_SHORTENER_RUN_INTEGRATION -ErrorAction SilentlyContinue
}
```

The integration tests create short links, check PostgreSQL persistence, Redis
cache and stream publication, redirect behavior, analytics/error contracts,
custom-alias uniqueness/redirect behavior, and analytics authentication. They
use unique test data and remove their test link/cache/stream data afterward.
The tests require all schema migrations to be applied.

## Implementation and acceptance status

The baseline URL-shortener implementation is present. `src/url_shortener`
contains the FastAPI app and health checks, link creation/redirect/analytics
routes, async persistence and Redis cache access, the Redis Stream analytics
worker, and metrics/logging. Alembic revision `20261010_01` creates
`short_links` and `click_events`; it can be applied with `alembic upgrade head`.
The documented API contracts and operational details are in this README and
the [engineering design](docs/03-engineering-design.md).
For a quick standalone reference to assumptions, risks, and PostgreSQL schema,
see [Risks, Assumptions, and Database Design](docs/05-risk-assumptions-database-design.md).

Latest regular-suite evidence: `python -m pytest -q` passed **98 tests** and
skipped **2 opt-in PostgreSQL/Redis integration tests** because the integration
variable was not set. An earlier integration-enabled run passed **76 tests**
against configured local PostgreSQL and Redis, before the custom-alias
integration case was added. That new live database check still needs to be run
with the integration environment configured. The command and evidence are in
the [engineering breakdown](docs/04-engineering-breakdown.md) and
[AI-assisted work log](docs/ai-usage-log.md).

T-110 benchmark code and local warm/cold measurements are recorded in the
[benchmark reports](docs/t110-local-load-test.json),
[additional warm report](docs/t110-warm-results.json), and
[additional cold report](docs/t110-cold-results.json). These local runs missed
Q-6/Q-7. The latest pair reported incomplete analytics draining; its benchmark
fixtures were subsequently removed with the cleanup-only command. The
persisted-versus-acknowledged event-count discrepancy still needs investigation.
The local benchmark task is complete for assignment delivery as a diagnostic
measurement; it does not demonstrate or claim that Q-6/Q-7 are met. Formal
capacity acceptance remains deferred until the discrepancy is reconciled and
the warm/cold workloads are repeated on a production-like environment with
comparable service topology, resource sizing, configuration, and cache/data
characteristics, using a separate load generator. That run must demonstrate the
target throughput and 100:1 ratio, plus client-observed redirect P95 at or
below 50 ms and creation P95 at or below 200 ms.

This remains an assignment prototype, not a production-ready public service.
Analytics bearer authentication, endpoint rate limits, and click/aggregate
retention are implemented per the accepted ambiguous scenario. A shared key
does not provide per-link authorization, and rate limiting is not destination
abuse review or link ownership/admin controls. Validate proxy configuration and
operational secrets before public exposure. Backup/restore, deployment strategy,
and loss-resistant click delivery still require separate decisions. Click
publication is best effort after the redirect response; recent analytics may
lag, and a process failure before publication can lose a click. The current
simulated baseline approval is documented in the [business requirement](docs/01-business-requirement.md);
there is no external stakeholder approval. Human sign-off from a clean setup
has not been performed.

## Capacity and latency benchmark

The reproducible fixed-rate benchmark uses `httpx` from the development
dependencies and writes a JSON report. It refuses non-local API targets unless
`--allow-remote` is explicitly supplied. A local-only run is supported and is
useful for exercising the harness, checking telemetry/cleanup, and establishing
a machine-specific baseline. It is diagnostic only: local hardware,
co-located services, and a co-located load generator do not establish deployed
capacity or satisfy Q-6/Q-7 acceptance. Keep PostgreSQL, Redis, the API, and the
analytics worker running, apply migrations, and confirm the API and worker
metrics endpoints are reachable at `127.0.0.1:9100` and `127.0.0.1:9101`.
Avoid unrelated traffic during the measurement. Never run a capacity test
against production.

From the project root, after starting the local services and applying
migrations, start or restart the API in its own PowerShell session with
temporary elevated rate-limit thresholds. These variables must be set in the
API process environment; setting them only in the load-generator shell has no
effect on the running API:

```powershell
$env:URL_SHORTENER_RATE_LIMIT_REDIRECT_REQUESTS_PER_MINUTE = "120000"
$env:URL_SHORTENER_RATE_LIMIT_CREATE_REQUESTS_PER_MINUTE = "1200"
uvicorn url_shortener.main:app --app-dir src
```

In a separate PowerShell session, run the warm-cache workload (15-second
warm-up, then 60-second measurement at 1,000 redirects/s and 10 creations/s):

```powershell
python scripts\load_test.py --cache-mode warm `
  --duration-seconds 60 --warmup-seconds 15 `
  --redirects-per-second 1000 --creations-per-second 10 `
  --concurrency 500 --output docs\t110-warm-results.json
```

Then run the cold-cache workload:

```powershell
python scripts\load_test.py --cache-mode cold `
  --duration-seconds 60 --warmup-seconds 15 `
  --redirects-per-second 1000 --creations-per-second 10 `
  --concurrency 500 --output docs\t110-cold-results.json
```

Keep these elevated thresholds confined to a disposable, isolated benchmark
environment; never use them as public-service production limits.

The cold-cache run seeds one mapping per scheduled redirect so each redirect
is a PostgreSQL-backed miss rather than warming into a repeated hit. Benchmark
fixtures are isolated by a unique destination marker and are removed after the
worker has persisted and acknowledged all expected events. If analytics does
not drain before the configured timeout, the report says cleanup was not
completed and leaves the records intact for investigation. Reports include
separate client and API histogram latencies, response/error counts, actual
rates and ratio, cache outcomes, database pool high-water mark, PostgreSQL and
Redis probe latency, worker lag/pending metrics, acknowledged event
throughput, environment, warm-up, duration, and concurrency.

If a report has `"cleanup_done": false`, do not start another load run yet.
Keep PostgreSQL and Redis available, then run cleanup-only once for that
report's `run_id` (the unique `bench-...` marker), for example:

```powershell
python scripts\load_test.py --cleanup-marker bench-aad4840e769745baa410aaaaca4c312d
```

Repeat with the other run's marker if needed. Cleanup removes only benchmark
data tagged with that exact marker. Confirm the command reports successful
cleanup and inspect the database/Redis to ensure no matching test links or
pending events remain. If cleanup fails, preserve the report and investigate
before retrying or starting another benchmark.

Review the report's actual rates, redirect/creation ratio, client-observed
P95s, errors, cache mode, analytics drain, and cleanup status. The target
acceptance thresholds are approximately 1,000 redirects/s and 10 creations/s
at a 100:1 ratio, redirect client P95 no greater than 50 ms, and creation
client P95 no greater than 200 ms. Do not use API middleware histogram values
as a substitute for client-observed latency. If a local run misses these
thresholds, record the result as a local diagnostic and investigate; do not
describe it as a capacity failure or pass for a representative deployment.
A representative capacity claim requires representative deployed resources
and a load generator separate from the services. Defer formal capacity
acceptance until such an environment is available.

Run Redis-outage behavior as a separate, short diagnostic after collecting
normal-cache results: preserve a known link in PostgreSQL, stop Redis, request
the short URL without following redirects, and confirm `302` with the stored
destination while readiness reports Redis unavailable. Restart Redis promptly;
confirm readiness recovers and inspect the API cache-lookup error and
click-publication failure counters. Do not use outage measurements to claim
the normal-cache Q-6/Q-7 targets.

For a disposable development/test database, reverse the current migration with:

```powershell
alembic downgrade base
```

Database and Redis pool settings are per application process. Size them against
the database/server connection budgets multiplied by the number of deployed
processes; the example values are starting defaults, not load-tested capacity
recommendations.

The accepted ambiguous-scenario requirements implement a shared Bearer key for
analytics and per-client rate limits for creation, redirects, and analytics.
They do not supply per-user/per-link authorization, destination abuse review,
link ownership, abuse reporting, or administrative controls. Keep the service
off public deployment until those remaining controls, trusted-proxy settings,
secret management, and deployment safeguards are reviewed and implemented.
