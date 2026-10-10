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
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/shorten `
  -ContentType application/json `
  -Body '{"destination_url":"https://example.com/path"}'
```

The API returns the generated code, its public short URL, and creation time.
Creation errors use `{"error":{"code":"...","message":"...","details":...}}`.

Run the current tests with:

```powershell
pytest
```

Apply the PostgreSQL schema migration after configuring `.env`:

```powershell
alembic upgrade head
```

For a disposable development/test database, reverse the current migration with:

```powershell
alembic downgrade base
```

Database and Redis pool settings are per application process. Size them against
the database/server connection budgets multiplied by the number of deployed
processes; the example values are starting defaults, not load-tested capacity
recommendations.
