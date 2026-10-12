# Ambiguous Scenario Validation Evidence

- The reviewed requirements record is `output/ambiguous-reviewed.json`; the
  local CLI's original `output/ambiguous.json` remains a separate deterministic
  template draft and is not a live-model output.
- Implementation added daily aggregate and deduplication tables, raw-event
  retention, short-code-only event payloads, analytics Bearer authentication,
  trusted-proxy-aware client resolution, and Redis-backed request limits.
- Latest focused validation: the analytics/model/redirect suite passed
  **39 tests**, with 2 PostgreSQL/Redis integration tests skipped.
- Latest full-suite validation: `python -m pytest -q` — **123 passed, 2
  skipped**. The two skipped tests require a live, configured PostgreSQL/Redis
  environment.
- Alembic upgrade SQL for revisions `20261012_01` and `20261012_02` rendered
  successfully offline. The revisions have not yet been applied to a live
  PostgreSQL database, and the integration tests were not run against the new
  schema. Therefore live migration/schema behavior remains unverified.
- Automated tests cover event field shape, legacy pending-stream compatibility,
  event idempotency, retention cutoff behavior, authentication, request limits,
  proxy trust, and readiness. They do not establish deployment security,
  public readiness, durable click delivery, or loss-free analytics.
