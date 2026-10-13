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
- Local recorded capacity runs missed Q-6/Q-7; performance acceptance remains
  unverified/not accepted. Analytics persistence-versus-acknowledgement
  discrepancy remains open.
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
| T-102 — Set up async application | Start service; verify health/readiness, cleanup, invalid configuration, secret handling, and async I/O behavior. | **Partial.** Human requests observed liveness `alive`, readiness with PostgreSQL and Redis ready, and not-ready when dependencies were unavailable. The current readiness check also reported all dependencies, including analytics authentication, ready after key configuration. Automated lifecycle tests cover resource cleanup. | No separately recorded manual invalid-configuration, secret-log, or event-loop-blocking check. |
| T-103 — Create schema | Apply migrations; inspect columns, constraints, indexes; verify unique codes/event IDs and foreign keys. | **Partial; current migrations verified live.** The user applied revisions `20261012_01` and `20261012_02`; PostgreSQL reported `20261012_02`. Inspection confirmed `click_events.code` references `short_links.code`, daily aggregate and deduplication tables exist, and the lifetime `short_links.clicks_total` column is absent. Earlier baseline PostgreSQL inspection and automated constraint tests are recorded in the breakdown. | No evidence that every current-revision constraint/index was manually exercised against a clean database. |
| T-104 — Implement link creation | Verify validation, commit ordering, retries, error contract, Redis outage behavior, and mapping survival after API restart. | **Substantially verified.** Human evidence records `201` creation, `422` for invalid FTP input, PostgreSQL mapping and Redis TTL inspection, successful create/persistence during Redis outage, and mapping survival after API restart. Focused tests cover collision retries, persistence failures, and commit-before-cache behavior. | No current unresolved baseline check identified; benchmark-level behavior is tracked under T-110. |
| T-105 — Implement redirects | Exercise cache/DB paths and ensure Redis failures do not become false `404`s. | **Verified for recorded cases.** Human checks confirmed cache-hit `302` with PostgreSQL stopped, unknown-code `404`, and DB-fallback `302` with Redis stopped. A DB-unavailable check exposed and led to correction of a `500`; after restart, lookup returned the documented `503`, not `404`/`500`. | No separate deployment-environment verification is recorded. |
| T-106 — Implement stream analytics | Simulate pre/post-commit failures and retries; verify idempotency, acknowledgement order, pending recovery, and disclose best-effort delivery. | **Partially verified.** The manual end-to-end test created a link, received `302`, and later observed analytics `clicks_total: 1`. Live integration tests confirmed Redis event publication and persistence. Failure/retry windows and acknowledgement ordering are principally covered by automated failure-injection tests; best-effort delivery is documented and accepted for this prototype. | No separate current manual fault-injection/recovery exercise is recorded. |
| T-107 — Implement analytics API | Check known/unknown codes, response shape, aggregate after processing, and index use if time-series is added. | **Partially verified.** The user observed an authenticated response with the expected code and `clicks_total: 1`. Live integration tests cover response shape and unknown-code `404`; automated tests cover missing/invalid authentication and DB failure. | Manual authentication-failure behavior and query-plan/index inspection are not recorded; no time-series endpoint is in scope. |
| T-108 — Security, reliability, observability | Inspect data/log fields, exercise DB/Redis failures, verify metric cardinality, review T-115 controls and public-exposure risks. | **Partially verified.** Earlier human checks for the original T-108 controls are summarized in the breakdown. Current integration/manual checks confirm privacy-minimal event fields and functioning authenticated analytics. Automated tests cover safe fields, metrics labels, failure contracts, rate limits, proxy resolution, and reserved routes. | Deployment/network scrape isolation has not been verified. Abuse reporting/destination controls, ownership, and administrative flows remain open before public exposure. |
| T-109 — Automated and integration tests | Run full regular and service-backed suites against PostgreSQL/Redis; record commands and results. | **Verified for the current tested configuration.** User ran `URL_SHORTENER_RUN_INTEGRATION=1 python -m pytest -q tests\\test_service_integration.py` (**2 passed**) and then `python -m pytest -q` with the opt-in still enabled (**128 passed, no skips**) after review fixes. The variable was removed afterward. | Re-run when material code or environment changes; preserve the exact opt-in setting for reproducibility. |
| T-110 — Capacity and latency | Run diagnostic warm/cold benchmarks, inspect reports/cleanup, then require representative results for Q-6/Q-7 acceptance. | **Diagnostic validation complete; acceptance not met.** Local warm/cold runs and a later human rerun are recorded in the breakdown and report files. The later rerun missed throughput, ratio, and P95 targets; fixture cleanup was confirmed. | Investigate the persisted-versus-acknowledged discrepancy. Run against representative non-production resources with a separate load generator before accepting Q-6/Q-7. |
| T-111 — Document and sign off | Follow setup in a clean environment; rerun suites; inspect schema; verify API/worker metrics and smoke behavior; review benchmark limits. | **Documentation and evidence updated; final sign-off partial.** The user applied and inspected migrations, ran integration/full tests, and completed the create/redirect/analytics smoke flow. Benchmark results and limitations are recorded. | A full clean-environment setup/sign-off, deployment/network review, backup/restore plan, and Q-6/Q-7 acceptance remain open. No production-readiness or external approval is claimed. |

Latest reported verification: **2 integration tests passed** and the full
integration-enabled suite passed **128 tests with no skips**. The analytics
key was rotated by the user after exposure; its value is intentionally not
recorded. See [ambiguous-scenario validation](../ambiguous/validation.md) and
[risk/assumption status](../../docs/05-risk-assumptions-database-design.md).
