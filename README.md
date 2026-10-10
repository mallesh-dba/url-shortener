# URL Shortener

Build a scalable URL shortener service with APIs, persistence, and analytics.

## Development setup

Requires Python 3.11 or newer. Install the project and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and update the PostgreSQL, Redis, and public base
URL settings for your environment. `URL_SHORTENER_PUBLIC_BASE_URL` is the
HTTP(S) origin used to construct returned short URLs. The example values are
for local development only; do not use them as production credentials.

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
external services. `GET /health/ready` checks PostgreSQL and Redis and returns
`503` if either dependency cannot be reached. The readiness response reports
dependency status without exposing connection details. The PostgreSQL readiness
probe has a configurable two-second deadline by default
(`URL_SHORTENER_DB_READINESS_TIMEOUT_SECONDS`).

Create a short link with:

```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/shorten `
  -ContentType application/json `
  -Body '{"destination_url":"https://example.com/path"}'
```

The API returns the generated code, its public short URL, and creation time.
Creation errors use `{"error":{"code":"...","message":"...","details":...}}`.

Follow a returned short URL to test redirect behavior:

```powershell
curl.exe -i $response.short_url
```

The redirect endpoint returns `302` with the destination in the `Location`
header. An unknown code returns `404` only after PostgreSQL confirms it does
not exist; Redis outages fall back to PostgreSQL.

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
event to the configured Redis Stream. The worker stores events idempotently
and increments `clicks_total` in the same PostgreSQL transaction, then
acknowledges the stream entry. If processing or acknowledgement fails, the
entry remains pending and can be reclaimed after
`URL_SHORTENER_ANALYTICS_PENDING_IDLE_MS`. The worker logs consumer-group
pending count and lag periodically.

The worker checks trimming every
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
aggregate, and pending queue:

```powershell
curl.exe -i $response.short_url
$sql = "SELECT l.code, l.clicks_total, COUNT(e.event_id) AS stored_events FROM short_links l LEFT JOIN click_events e ON e.link_id = l.id WHERE l.code = '$($response.code)' GROUP BY l.id, l.code, l.clicks_total;"
docker exec url-shortener-postgres psql -U postgres -d url_shortener -c $sql
docker exec url-shortener-redis redis-cli XPENDING clicks:v1 click-analytics:v1
```

After the asynchronous worker catches up, expect one stored event and a count
of `1` for the new link, with no pending event. The count is eventually
consistent; rerun the inspection if the worker has not processed the event yet.

Run the current tests with:

```powershell
pytest
```

For a disposable development/test database, reverse the current migration with:

```powershell
alembic downgrade base
```

Database and Redis pool settings are per application process. Size them against
the database/server connection budgets multiplied by the number of deployed
processes; the example values are starting defaults, not load-tested capacity
recommendations.
