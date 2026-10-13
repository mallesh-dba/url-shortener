# Ambiguous Scenario Validation Evidence

- The reviewed requirements record is `output/ambiguous-reviewed.json`; the
  local CLI's original `output/ambiguous.json` remains a separate deterministic
  template draft and is not a live-model output.
- Implementation added daily aggregate and deduplication tables, raw-event
  retention, short-code-only event payloads, analytics Bearer authentication,
  trusted-proxy-aware client resolution, and Redis-backed request limits.
- Human-applied migrations `20261012_01` and `20261012_02` successfully with
  `alembic upgrade head`. PostgreSQL reported revision `20261012_02`;
  `click_events` uses `code` as its foreign key to `short_links.code`,
  `daily_click_aggregates` and `processed_click_event_ids` exist, and
  `short_links.clicks_total` is no longer present.
- The first opt-in integration run exposed a test-fixture issue: Pydantic's
  `model_copy(update=...)` left its test analytics key as a plain string.
  Wrapping that key in `SecretStr` fixed the fixture; no service behavior was
  changed for this issue.
- Against the configured PostgreSQL and Redis services, the integration tests
  passed **2 tests**. The full suite with
  `URL_SHORTENER_RUN_INTEGRATION=1` initially passed **125 tests** with no
  skips. After the review fixes for invalid-event acknowledgement and reserved
  route rate-limit classification, the user reran the opt-in integration test
  file (**2 passed**) and full suite (**128 passed, no skips**).
- The integration run verifies link creation, redirect/event publication,
  analytics authentication/response before the click, Redis event fields, and
  database persistence.
- Manual API/worker flow confirmed readiness after configuring the analytics
  key; a new link was created, its short URL returned HTTP 302, and the
  authenticated analytics response reached `clicks_total: 1` after polling.
  This confirms the worker-to-aggregate path end to end. The user reported
  rotating the analytics key after an earlier shared-terminal exposure. After
  a later IDE exposure, no subsequent rotation is confirmed, so security
  remediation remains open until that rotation is confirmed. The key value is
  not recorded here.
- Automated tests cover event field shape, legacy pending-stream compatibility,
  event idempotency, retention cutoff behavior, authentication, request limits,
  proxy trust, and readiness. They do not establish deployment security,
  public readiness, durable click delivery, or loss-free analytics.
