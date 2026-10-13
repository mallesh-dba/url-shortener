# Greenfield Validation Evidence

Validation is split between the scenario-processing workflow and the service
implementation. The baseline task-by-task human verification record for
T-101–T-111 is included below; a passing test suite does not establish Q-6/Q-7.

- Requirement processor: `python -m pytest -q tests\test_requirement_processor.py`
  passed **9 tests** after the non-object JSON validation case was added.
- Latest user-run integration command:
  `URL_SHORTENER_RUN_INTEGRATION=1 python -m pytest -q tests\test_service_integration.py`
  — **2 passed** against PostgreSQL and Redis.
- Latest user-run full suite, with the integration opt-in still enabled:
  `URL_SHORTENER_RUN_INTEGRATION=1 python -m pytest -q` — **128 passed, no
  skips**. This run followed the worker invalid-event and reserved-route
  rate-limit review fixes.
- T-110 local diagnostic validation is complete for assignment delivery, with
  the missed Q-6/Q-7 targets disclosed below. Formal capacity acceptance
  remains deferred; the analytics persistence-versus-acknowledgement
  discrepancy must be reconciled before another acceptance run.
- CLI-generated JSON is not evidence of a live model call; see
  [the CLI evidence note](../README.md).

## Baseline Human Validation T-101 through T-111

This record cross-checks the **Human validation / verification check** for
each baseline task in
[the engineering breakdown](../../docs/04-engineering-breakdown.md) against
the human evidence recorded so far. “Partial” means the available evidence
confirms only part of the check; it must not be read as a complete sign-off.
Automated tests are called out separately and do not substitute for manual or
deployment verification.

| Task | Engineering-breakdown human check | Human evidence and current status | Remaining validation |
|---|---|---|---|
| T-101 — Define baseline requirements | Trace requirements, approve API/error contracts, record open decisions, and treat Q-6/Q-7 as targets. | **Recorded/accepted for assignment planning.** The requirements and design were reviewed into baseline contracts and open decisions; the user accepted the baseline for implementation planning. See [business requirement](../../docs/01-business-requirement.md), [requirement analysis](../../docs/02-requirement-analysis.md), and [greenfield review](human-review.md). | No external stakeholder approval is recorded. Keep Q-6/Q-7 as unaccepted until representative measurement passes. |
| T-102 — Set up async application | Start service; verify health/readiness, cleanup, invalid configuration, secret handling, and async I/O behavior. | **Substantially verified.** The user completed the local setup and manual API checks described below: liveness returned `alive`; readiness returned `ready` with PostgreSQL and Redis available; stopping dependencies produced `503`/`not_ready` with failed dependency flags. The user also reports the automated suite passed **11 tests**, covering configuration validation and secret redaction, session/lifespan cleanup, health/readiness, and a PostgreSQL readiness probe that exceeds its deadline. | No separate manual secret-log inspection or direct event-loop-blocking check is recorded. The timeout branch is verified by the automated hanging-probe test, not by creating a real half-open database connection. |
| T-103 — Create schema | Apply migrations; inspect columns, constraints, indexes; verify unique codes/event IDs and foreign keys. | **Complete for assignment validation.** The baseline schema was applied/inspected in PostgreSQL at revision `20261010_01` on 2026-10-10, including its uniqueness and foreign-key checks. On 2026-10-12, the user applied revisions `20261012_01` and `20261012_02`, confirmed the current revision, and inspected that `click_events.code` references `short_links.code`, daily aggregate and deduplication tables exist, and the lifetime `short_links.clicks_total` column is absent. Current model/schema tests and PostgreSQL/Redis integration tests also pass. | The supplied original-schema SQL procedure is historical: it expects `click_events.link_id` and `short_links.clicks_total`, which do not match revision `20261012_02`. No assignment blocker remains; direct manual duplicate-event and invalid-FK checks against the latest schema are optional additional evidence. |
| T-104 — Implement link creation | Verify validation, commit ordering, retries, error contract, Redis outage behavior, and mapping survival after API restart. | **Substantially verified.** Human evidence records `201` creation, `422` for invalid FTP input, PostgreSQL mapping and Redis TTL inspection, successful create/persistence during Redis outage, and mapping survival after API restart. Focused tests cover collision retries, persistence failures, and commit-before-cache behavior. | No current unresolved baseline check identified; benchmark-level behavior is tracked under T-110. |
| T-105 — Implement redirects | Exercise cache/DB paths and ensure Redis failures do not become false `404`s. | **Verified for recorded cases.** Human checks confirmed cache-hit `302` with PostgreSQL stopped, unknown-code `404`, and DB-fallback `302` with Redis stopped. A DB-unavailable check exposed and led to correction of a `500`; after restart, lookup returned the documented `503`, not `404`/`500`. | No separate deployment-environment verification is recorded. |
| T-106 — Implement stream analytics | Simulate pre/post-commit failures and retries; verify idempotency, acknowledgement order, pending recovery, and disclose best-effort delivery. | **Complete for assignment validation.** Manual local checks recorded on 2026-10-10 verified duplicate-event idempotency, a database-failure pending entry being recovered after PostgreSQL restarted, and successful redirects while Redis was stopped. The 2026-10-12 live integration/manual smoke checks verified the current worker-to-aggregate path. Current automated failure tests verify commit-before-ack, retry after DB/commit failures, pending recovery, and idempotent replay after commit/ack failure. Best-effort event loss during Redis outage is explicitly documented. | No assignment blocker remains. The older manual SQL uses the pre-`20261012_02` schema (`link_id`, lifetime `clicks_total`); use the current code-based event/daily-aggregate schema for any repeat exercise. |
| T-107 — Implement analytics API | Check known/unknown codes, response shape, aggregate after processing, and index use if time-series is added. | **Complete for assignment validation.** The 2026-10-11 transcript records a known-code response at zero before a click and `clicks_total: 1` after redirect processing, matching one stored event, plus an unknown-code `404`. The later authenticated aggregate endpoint was manually observed at `clicks_total: 1` and validated against PostgreSQL/Redis integration tests, which also cover the current response shape and unknown-code behavior. Automated contract tests verify missing/invalid bearer authentication and database-failure `503`. | No assignment blocker remains. The 2026-10-11 unauthenticated request and SQL query refer to the pre-`20261012_02` lifetime-counter implementation, not current access control/schema. Query-plan inspection is not applicable because time-series reporting is not in scope. |
| T-108 — Security, reliability, observability | Inspect data/log fields, exercise DB/Redis failures, verify metric cardinality, review T-115 controls and public-exposure risks. | **Complete for assignment validation.** The user’s 2026-10-11 PowerShell transcript inspected Redis event fields and API logs/metrics for code and destination markers; exercised PostgreSQL-unavailable readiness, lookup, and creation behavior; confirmed a known redirect still returned `302` during Redis outage; and inspected bounded route-template, operation/outcome, pool, and worker metrics. T-115’s accepted analytics-authentication and rate-limit controls are separately implemented and covered by the current integration/manual evidence and tests. | Deployment/network scrape isolation remains to be checked in the target deployment. The transcript’s historical request to `/metrics` on port 8000 returned metrics at that time; current code now rejects that public route and automated tests verify the `404`, but this does not replace a deployment/network review. Abuse reporting/destination controls, ownership, and administrative flows remain open before public exposure. |
| T-109 — Automated and integration tests | Run full regular and service-backed suites against PostgreSQL/Redis; record commands and results. | **Verified for the current tested configuration.** The user ran these commands from PowerShell with PostgreSQL and Redis configured: `$python = 'D:\assignment\.venv\Scripts\python.exe'`; `$env:URL_SHORTENER_RUN_INTEGRATION = "1"`; `& $python -m pytest -q tests/test_service_integration.py` (**2 passed**); `& $python -m pytest -q` (**128 passed, no skips**); `Remove-Item Env:URL_SHORTENER_RUN_INTEGRATION`. The test path uses forward slashes and is valid in PowerShell. | Re-run when material code or environment changes; set the opt-in environment variable before both commands and remove it afterward. |
| T-110 — Capacity and latency | Run diagnostic warm/cold benchmarks, inspect reports/cleanup, then require representative results for Q-6/Q-7 acceptance. | **Local diagnostic validation complete; sufficient for assignment delivery with limitations disclosed.** The latest local warm/cold runs achieved about 34.5 redirects/s and 9.9 creations/s, with an achieved ratio of about 3.5:1. Client-observed P95 was 5.8–7.8 seconds for redirects and 5.7–7.4 seconds for creations. All recorded responses were successful, and benchmark fixture cleanup was confirmed. The results missed the 1,000 redirects/s, 100:1 ratio, 50 ms redirect P95, and 200 ms creation P95 targets. | Formal Q-6/Q-7 acceptance remains deferred, not an assignment hand-in blocker. Re-run on a production-like topology/resource configuration with a separate load generator; first reconcile the persisted-versus-acknowledged analytics discrepancy. |
| T-111 — Document and sign off | Follow setup in a clean environment; rerun suites; inspect schema; verify API/worker metrics and smoke behavior; review benchmark limits. | **Assignment-level sign-off complete in a newly created Python 3.12 virtual environment.** The user reinstalled the project, confirmed PostgreSQL/Redis availability and migration head `20261012_02`, inspected the current schema, ran the integration and full suites (**2 passed**, **128 passed with no skips**), verified readiness and both private metrics listeners, confirmed the public `/metrics` path returns `404`, and completed create → redirect → authenticated analytics (`clicks_total: 1`) with one stored event and zero pending events. | The transcript used the existing checkout and database; it does not establish a fresh-checkout or empty-database migration run. Deployment/network review and backup/restore planning remain production follow-ups. Q-6/Q-7 are separately deferred and not claimed as accepted. No production-readiness or external approval is claimed. |

Latest reported verification: **2 integration tests passed** and the full
integration-enabled suite passed **128 tests with no skips**. The analytics
key was rotated by the user after exposure; its value is intentionally not
recorded. See [ambiguous-scenario validation](../ambiguous/validation.md) and
[risk/assumption status](../../docs/05-risk-assumptions-database-design.md).

### T-102 Execution Evidence

The user reports completing the local PowerShell verification on 2026-10-13:

- Installed the project with `python -m pip install -e ".[dev]"` using the
  configured Python 3.12 environment and ran the automated checks, reporting
  **11 passed** for the T-102 coverage.
- Configured `.env` from `.env.example` and ran PostgreSQL and Redis locally.
  The example credentials were used only for local development.
- Started Uvicorn from the repository root. `GET /health/live` succeeded
  independently of dependency availability.
- With PostgreSQL and Redis running, `GET /health/ready` returned `ready`
  with both dependency flags true. When a dependency was unavailable,
  readiness returned HTTP `503` and marked the unavailable dependency false.
- The automated hanging-PostgreSQL-probe check returned not-ready after the
  configured deadline (two seconds by default); no real half-open connection
  was required.
- Stopped Uvicorn and any optional local containers after the checks.

The reported test coverage also exercises explicit invalid-configuration and
secret-redaction behavior, along with request-session and application
shutdown cleanup. This records the user's validation report; the test command
output was not independently recaptured while documenting this evidence.

### T-111 Clean-Environment Sign-Off Evidence

The user-provided PowerShell transcript records an assignment-level setup and
sign-off on 2026-10-13 using a newly created Python 3.12 virtual environment
in the existing repository checkout:

- Installed the editable project and development dependencies successfully.
  Recreated `.env` from `.env.example` and configured local settings without
  recording secret values.
- Confirmed PostgreSQL accepted connections and Redis returned `PONG`.
  `alembic upgrade head` completed, `alembic current` reported
  `20261012_02 (head)`, and the user inspected `short_links`, `click_events`,
  `daily_click_aggregates`, and `processed_click_event_ids`. The current
  code-based click-event foreign key and indexes were present.
- With `URL_SHORTENER_RUN_INTEGRATION=1`, the integration test file passed
  **2 tests** and the full test suite passed **128 tests with no skips**.
- Readiness returned `ready` with PostgreSQL, Redis, and analytics
  authentication ready. The API and worker metrics listeners returned
  Prometheus output; the public API `/metrics` route returned `404`.
- A newly created link returned HTTP `302` with the expected `Location`.
  Authenticated analytics reached `clicks_total: 1`; PostgreSQL showed one
  aggregate click and one stored event, while Redis `XPENDING` returned zero.

This is clean application-environment validation, not a clean checkout or
empty-database test: the transcript shows an existing repository and database,
and `alembic upgrade head` did not show migration operations. It therefore
confirms the current install, database revision/schema, tests, operational
metrics, and smoke flow, but does not claim migrations were applied from base
to head on a newly provisioned database. Capacity acceptance and production
readiness remain separate and are not claimed.

### T-106 Execution Evidence

The attached PowerShell transcript records local worker-pipeline checks on
2026-10-10:

- A redirect returned HTTP `302`; PostgreSQL then showed one click and one
  stored event, and Redis `XPENDING` reported zero after processing.
- The same event ID was added to the stream twice. PostgreSQL still showed
  only one increment and one stored event, while `XPENDING` returned to zero,
  confirming duplicate-delivery idempotency.
- With PostgreSQL stopped, a new stream entry remained pending
  (`XPENDING` count 1). After PostgreSQL restarted, the worker persisted the
  event; the aggregate/lifetime count advanced, the event row was present,
  and the pending count returned to zero. This exercises transient-failure
  retry and pending recovery.
- With Redis stopped but the API and PostgreSQL running, the known short URL
  still returned HTTP `302` with the expected `Location`. Redis readiness
  returned after the container restarted. Analytics publication can be lost
  during that Redis outage; redirect delivery remains best effort.

The transcript includes an earlier request made while the API was not
running; that failed connection is not counted as a successful redirect
check. A subsequent run started the service and successfully completed the
redirect, persistence, and Redis-outage checks.

The 2026-10-10 SQL statements target the then-current schema
(`click_events.link_id` and `short_links.clicks_total`). Those fields were
replaced by the migrations through `20261012_02`; the later live
PostgreSQL/Redis integration and manual analytics smoke checks verified
current event publication and worker aggregation. Current tests in
[`test_analytics.py`](../../tests/test_analytics.py) additionally verify
database commit before acknowledgement, unacknowledged retries on database
and commit failure, pending recovery, and idempotent replay when acknowledgement
fails after commit.

### T-108 Execution Evidence

The user-provided PowerShell transcript records local T-108 checks on
2026-10-11:

- Readiness reported PostgreSQL and Redis ready. With PostgreSQL stopped,
  readiness returned `503` with `postgres: false`; a link lookup returned
  `503 lookup_unavailable`. After restoring PostgreSQL, readiness returned
  ready. A valid link-creation request during a separate PostgreSQL outage
  returned `503 persistence_unavailable`.
- A known short link returned `302` with its expected destination while Redis
  was stopped; readiness returned ready after Redis restarted. This verifies
  redirect fallback, not analytics delivery during the outage.
- Redis stream inspection showed event fields only for event ID, link
  reference, and timestamp in that baseline schema. The API log was checked
  from the repository directory for the short code and destination marker and
  did not contain them. A first log read from the wrong working directory
  failed; that failed check is not treated as evidence.
- Metrics showed bounded route-template labels (`/{code}`, not a concrete
  code or URL), fixed cache operation/outcome labels, database-pool gauges,
  event-publication failures, worker failure, pending, and lag metrics. The
  captured metrics output was searched for the code and destination marker
  and did not contain them.

The transcript also records `/metrics` on the API port returning metrics at
the time of that run. Current code instead reserves that path and returns
`404`; the automated observability test verifies this current behavior.
Deployment/network isolation for the separate metrics listener remains an
operational check. These local checks complete T-108 for assignment scope,
but do not amount to production-readiness approval; public-exposure gates
remain open as stated above.

### T-107 Execution Evidence

The user-provided PowerShell transcript records the following analytics API
checks on 2026-10-11:

- Readiness reported PostgreSQL and Redis ready.
- A newly created link returned an analytics response with its code and
  `clicks_total: 0` before its first redirect.
- The short URL returned HTTP `302` with the expected `Location`. After
  polling the analytics endpoint, `clicks_total` became `1`; PostgreSQL
  showed one stored click event for the link.
- A request for unknown code `NoSuch107` returned HTTP `404` with
  `link_not_found`.

This transcript predates the accepted authenticated aggregate implementation.
Its analytics request did not include an Authorization header, and its SQL
uses the pre-`20261012_02` `link_id`/lifetime-counter schema; neither is
evidence of current authentication behavior or current schema. The current
authenticated aggregate endpoint was separately validated in the
2026-10-12 PostgreSQL/Redis integration run, and the user manually observed
the authenticated total reach `1`. Automated contract coverage in
[`test_link_analytics.py`](../../tests/test_link_analytics.py) verifies the
current response, unknown-code `404`, missing/invalid bearer-token `401`, and
database-failure `503`. A time-series query plan is out of scope, so no
separate query-plan inspection is required for T-107.
