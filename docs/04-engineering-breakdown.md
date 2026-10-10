# URL Shortener — Engineering Breakdown

**Status:** Proposed implementation plan  
**Scope:** Core URL-shortener service and three AI-assisted engineering scenarios  
**Sources:** [Business requirement](01-business-requirement.md), [requirement analysis](02-requirement-analysis.md), [engineering design](03-engineering-design.md)  

This document translates the requirements and proposed design into a dependency-ordered implementation plan. It is a plan, not evidence that the service has been implemented or that tests or performance targets have passed. The stack in the engineering design is treated as a design constraint for this use case, not as externally approved business policy.

## Part 1: Project-Wide Task Decomposition

Tests should be developed alongside each behavior. T-109 is the cross-feature integration and regression gate, not a reason to defer testing until development ends.

**Task naming convention:** Use sequential `T-NNN` identifiers and an imperative, verb-first title describing one deliverable. Keep task IDs stable when titles are clarified; assign new IDs only to newly approved work.

### Phase 1 — Confirm scope and prepare the service

#### T-101: Define Baseline Requirements and Acceptance Criteria

- **Status:** Accepted as the implementation baseline on 2026-10-09, at the user's direction. This is not external stakeholder approval and does not mean implementation, tests, or performance targets are complete.
- **Description & scope:** Turn REQ-4–REQ-8 and Q-6/Q-7 into API contracts, error responses, functional acceptance checks, and a benchmark protocol. Use Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, and Redis as the constraints in this design. Keep custom aliases, expiration, authentication, retention, and loss-resistant analytics out of baseline scope until approved.
- **Dependencies:** None.
- **AI-assistance point:** Ask AI to trace each behavior to a requirement ID, identify gaps and ambiguity, and draft acceptance criteria without silently deciding open product questions.
- **Human validation / verification check:** Check traceability against the requirements, approve endpoint/error contracts, and record unresolved decisions. Treat approximately 1,000 redirects/s, 10 creations/s, and the P95 limits as targets to measure, not results already achieved.

##### T-101 Traceability and Acceptance Record

| Baseline behavior | Requirement | Accepted contract / criterion |
|---|---|---|
| Create a short link from a valid destination | REQ-4 | `POST /api/v1/shorten` accepts `destination_url`; returns `201` with `code`, `short_url`, and `created_at`. Only absolute HTTP(S) URLs are accepted; the service does not fetch them. |
| Persist the mapping | REQ-5 | PostgreSQL is authoritative for the short-code-to-destination mapping. A successful creation remains available after cache loss/restart. |
| Redirect a known short code | REQ-6 | `GET /{code}` returns `302` with a `Location` header containing the stored destination. |
| Record and retrieve usage | REQ-7 | A redirect schedules click-event publication; a worker persists events idempotently and updates the aggregate. Analytics returns at least `code` and `clicks_total`. The design's baseline delivery is best effort and the aggregate may be eventually consistent. |
| Document invalid and unknown-resource errors | REQ-8 | Invalid creation input returns `422`; unknown redirect and analytics codes return `404`; creation persistence failure returns `503`. Error bodies use one consistent JSON shape to be finalized before API implementation. |
| Meet peak request rates | Q-6 | Validate approximately 1,000 redirects/s and 10 creations/s (100:1) in a measured load test. These are targets, not current results. |
| Meet endpoint latency | Q-7 | At the Q-6 workload, measure redirect P95 against 50 ms and creation P95 against 200 ms; do not claim success without benchmark evidence. |

The prototype-level requirements REQ-1–REQ-3 and REQ-9–REQ-10, and cross-cutting quality requirements Q-1–Q-5, remain applicable to the overall deliverable but are not URL-shortener endpoint behaviors owned solely by T-101. They are addressed through the prototype, implementation, testing, and documentation work.

**Open decisions retained without a silent default:**

- Final JSON error-body fields and the public/base URL used to construct `short_url`.
- Detailed destination-URL validation edge cases and the bounded code-collision retry limit.
- Analytics freshness expectations and whether best-effort click loss is acceptable beyond this prototype baseline.
- Benchmark duration, warm-up, environment, concurrency model, traffic distribution, and acceptable error rate. Before T-110, record these in the benchmark plan; separately report warm-cache, cold-cache, and Redis-failure runs.
- Authentication, rate limiting, abuse controls, analytics retention, custom aliases, expiration, updates/deletion, and any collection of personal data are not part of the accepted baseline; obtain explicit approval before adding them.

**Acceptance record:** Baseline scope and criteria above are marked accepted for implementation planning at the user's direction on 2026-10-09. This is not external stakeholder sign-off. The open decisions remain visible follow-ups and do not constitute evidence that code, automated tests, or Q-6/Q-7 performance targets have been completed.

#### T-102: Set Up Async Application and Configuration

- **Status:** Implemented and validated on 2026-10-10. Automated tests cover startup/shutdown, configuration, and health behavior. The user reports manually validating with PostgreSQL and Redis running; exact commands and observed responses were not provided.
- **Description & scope:** Set up the Python/FastAPI application, dependency management, settings and secret loading, health/readiness behavior, async SQLAlchemy engine and request-scoped sessions, and reusable async Redis client. Configure bounded connection pools and operation timeouts.
- **Dependencies:** T-101.
- **AI-assistance point:** Ask AI for a minimal scaffold and lifecycle wiring that follows project conventions, including an explanation of resource cleanup and pool assumptions.
- **Human validation / verification check:** Start the service and check health/readiness. Verify resources close on shutdown, invalid configuration fails explicitly, secrets are not logged or committed, and network I/O is not performed synchronously on the event loop.
- **Implementation record:** App scaffold, environment settings, async resource lifecycle, `/health/live`, `/health/ready`, setup instructions, and focused tests are present. Defaults are 10 DB pooled connections plus up to 20 overflow and 50 Redis connections per process; these are configurable starting assumptions, not load-tested sizing. Readiness checks PostgreSQL and Redis and returns only status booleans; the PostgreSQL probe has a configurable two-second deadline. Liveness does not contact dependencies. The user reports successful live validation with PostgreSQL and Redis running; record exact commands/responses if available.

### Phase 2 — Persist and serve short links

#### T-103: Create Link and Click-Event Schema

- **Description & scope:** Define SQLAlchemy models and migrations for `short_links` and `click_events`: identity and foreign keys, unique code, destination, timestamps, aggregate click count, event UUID idempotency, and the `(link_id, clicked_at DESC)` index. PostgreSQL is the source of truth.
- **Dependencies:** T-102.
- **AI-assistance point:** Have AI draft typed models and migrations from the design and review the constraints, indexes, and migration reversibility.
- **Human validation / verification check:** Apply migrations to a clean PostgreSQL database and inspect actual columns, constraints, and indexes. Verify duplicate codes and event IDs are rejected and the event foreign key is enforced.
- **Implementation record:** Added typed SQLAlchemy models and an Alembic migration for the design's columns, unique code and event-ID keys, event foreign key, and descending `(link_id, clicked_at)` index. Added a nonnegative aggregate-count check. Upgrade and downgrade SQL render successfully offline. The user reports that PostgreSQL schema inspection and constraint tests were completed and looked good; exact commands and individual test details were not provided.

#### T-104: Implement Link-Creation API

- **Description & scope:** Implement `POST /api/v1/shorten`: validate an absolute HTTP(S) URL without fetching it, generate an 8-character random Base62 code, persist with bounded unique-collision retries, and return `201` with code, short URL, and creation time. Populate `short:v1:{code}` in Redis after commit as best effort.
- **Dependencies:** T-103.
- **AI-assistance point:** Generate request/response schemas, service and endpoint drafts, and focused tests; ask AI to explore malformed URLs, collision retries, and database/cache failures.
- **Human validation / verification check:** Review URL validation, commit ordering, bounded retries, response/error formats, and behavior after Redis failure. Verify the mapping survives application restart.

#### T-105: Implement Cached Redirects and Database Fallback

- **Description & scope:** Implement `GET /{code}` using Redis cache-first lookup, PostgreSQL fallback, and cache population on a miss. Return `302` with `Location` for a known link and `404` only after PostgreSQL confirms no mapping.
- **Dependencies:** T-103 and T-104.
- **AI-assistance point:** Ask AI to draft the lookup flow and tests for cache hits, misses, cold starts, unknown codes, and Redis outages; specifically review for false `404`s.
- **Human validation / verification check:** Exercise every path in PostgreSQL/Redis integration tests. Confirm Redis read/write failures fall back to PostgreSQL and do not return a false not-found response.

### Phase 3 — Record and expose usage

#### T-106: Implement Redis Stream Analytics Pipeline

- **Description & scope:** Publish minimal click events (`event_id`, link identity, UTC click time) to a Redis Stream and consume them in an independent async worker group. In one PostgreSQL transaction, insert each event idempotently and increment `clicks_total` only for a newly inserted event. Acknowledge only after commit; provide pending-event recovery and worker-lag monitoring. The current design is best effort: a process failure before publication can lose a click.
- **Dependencies:** T-103 and T-105.
- **AI-assistance point:** Have AI draft producer/consumer logic and failure-injection tests, focusing on duplicate delivery, crash windows, pending recovery, and safe stream trimming.
- **Human validation / verification check:** Simulate retries and failures before and after database commit. Confirm no duplicate counter increments, no acknowledgement before commit, pending items can be recovered, and the best-effort limitation is disclosed.

#### T-107: Implement Analytics API

- **Description & scope:** Implement `GET /api/v1/links/{code}/analytics`, returning at least `code` and `clicks_total`, or `404` for an unknown link. Add time-series reporting only if required by the approved API contract.
- **Dependencies:** T-103 and T-106.
- **AI-assistance point:** Ask AI to draft a response schema, query, and contract tests and to distinguish eventually consistent aggregates from synchronous counts.
- **Human validation / verification check:** Verify known/unknown link behavior, response shape, aggregate behavior after worker processing, and index usage for time-range reporting if included.

### Phase 4 — Harden, verify, and deliver

#### T-108: Implement Security, Reliability, and Observability Controls

- **Description & scope:** Use parameterized SQL, safe secret handling, bounded DB/Redis timeouts, explicit service errors, structured logs, and metrics for latency/status, cache outcomes, collision retries, database pool utilization, event publication failures, and worker lag. Do not collect IP addresses or user agents in the baseline; avoid logging full destination URLs and avoid short codes/URLs as high-cardinality labels.
- **Dependencies:** T-104, T-105, T-106, and T-107.
- **AI-assistance point:** Have AI review the actual implementation against the design’s security and operational concerns and suggest targeted tests.
- **Human validation / verification check:** Inspect stored and emitted fields, exercise DB/Redis failure behavior, and verify metric cardinality. Resolve authentication, rate limits, and abuse controls before public exposure.

#### T-109: Add Automated and Integration Tests

- **Description & scope:** Add and run unit/integration coverage for validation, creation and persistence, collisions, cache hit/miss/outage, redirects, analytics idempotency, error contracts, and async resource lifecycle. Build tests alongside feature implementation; use this task for the cross-feature regression gate.
- **Dependencies:** Feature-specific tests begin with T-103–T-107; final integration depends on T-108.
- **AI-assistance point:** Ask AI for test matrices, fixtures, and negative cases, then review generated tests for meaningful behavioral assertions rather than implementation coupling.
- **Human validation / verification check:** Run `pytest -q` and service-backed tests against PostgreSQL and Redis. Review failures and record exact commands, environment, and results; do not report unrun commands as passing.

#### T-110: Validate Capacity and Latency Targets

- **Description & scope:** Load test approximately 1,000 redirects/s and 10 creations/s at a 100:1 ratio using a realistic distribution, including popular links. Measure redirect and creation P95 independently, plus errors, cache state, analytics throughput/lag, and database pool utilization.
- **Dependencies:** T-108, T-109, and a representative deployed test environment.
- **AI-assistance point:** Use AI to develop a reproducible load-test plan and analyze actual measurements and bottlenecks; estimates are not measurements.
- **Human validation / verification check:** Record environment, test duration, warm-up, concurrency model, and cache state. Claim Q-6/Q-7 only if measured results meet the specified rates and P95 limits.

#### T-111: Document and Sign Off Engineering Deliverables

- **Description & scope:** Document setup, APIs, architecture, migrations, test and benchmark commands/results, decisions, risks, assumptions, and limitations. Explicitly state analytics delivery guarantees and remaining production decisions.
- **Dependencies:** T-109 and T-110.
- **AI-assistance point:** Ask AI to draft documentation from final code and captured test/benchmark output.
- **Human validation / verification check:** Follow setup instructions from a clean environment, rerun documented checks, and verify each claim against implementation and evidence.

### Conditional Tasks — Require Scope Approval

These are not baseline features. Create them only after the relevant behavior is approved.

- **T-112: Define Alias and Expiration Requirements.** **Dependencies:** T-101. Decide whether to support custom aliases, expiration, or both; define syntax and bounds, reserved aliases, collision response, expiry semantics and time zone, expired-link response, and compatibility expectations. Validate with an updated, approved contract.
- **T-113: Implement Approved Alias and Expiration Behavior.** **Dependencies:** T-112 and T-103. Add only the approved migration, constraints/indexes, API validation, and response behavior. Validate migration behavior, API compatibility, and feature-specific tests.
- **T-114: Clarify Analytics Privacy and Durability Requirements.** **Dependencies:** T-101 and T-106. Define allowed event fields, access, retention/deletion, and acceptable event loss. Validate through updated requirements and an approved analytics policy; this task does not itself add data collection or change delivery guarantees.
- **T-115: Implement Approved Analytics Privacy and Durability Controls.** **Dependencies:** T-114 and T-106. Implement only approved retention, collection, access, or loss-resistant delivery changes, such as an outbox. Validate privacy/retention behavior and failure/recovery guarantees.

## Part 2: Example Scenarios Mapped to Project-Wide Tasks

The prompts and outputs below are examples for future implementation, not historical verbatim prompts or evidence that the complete URL-shortener has been implemented or validated. A minimal application/configuration scaffold for T-102 and its focused tests are present; later service tasks remain outstanding.

### 1. Greenfield Requirement — Build the Core URL Shortener

- **Map to Part 1 Tasks:** T-101 → T-102 → T-103 → T-104 → T-105 → T-106 → T-107 → T-108 → T-109 → T-110 → T-111. Run T-109 checks incrementally as features are added.
- **AI-assisted execution — example prompt:**

  > Implement the URL shortener defined in `docs/01-business-requirement.md`, `docs/02-requirement-analysis.md`, and `docs/03-engineering-design.md`. Use Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, and Redis. First propose a requirement-to-code-and-test plan and list open decisions. Then implement persistence, `POST /api/v1/shorten`, cached `GET /{code}` redirects, Redis Stream click processing, and `GET /api/v1/links/{code}/analytics`. Accept only absolute HTTP(S) destinations and do not fetch them. Preserve documented error behavior, make event processing idempotent, and add tests alongside features. Report exact commands/results and do not claim performance targets without load-test evidence.

- **Expected AI output:** A traceable plan, typed models and migrations, service/API/worker drafts, focused tests, and an explicit list of assumptions and unresolved decisions.
- **Human code review/refinement loop:** Approve the plan before code generation. Inspect schema constraints, URL validation, code collision bounds, transaction and stream-ack ordering, cache fallback, event idempotency, and log contents. Reject false `404` behavior and unapproved personal-data collection. Review each diff and run feature-specific tests before accepting it.
- **Output validation — proposed commands:** `pytest -q`; `pytest -q tests/integration` with PostgreSQL and Redis configured; apply migrations and inspect the resulting schema; run the project load test at the specified rates.
- **Validation criteria:** Valid URLs create durable mappings; invalid/non-HTTP(S) URLs return documented validation errors; known codes return `302` and the correct `Location`; unknown codes return `404`; cache failure falls back to PostgreSQL; events persist idempotently and analytics returns the aggregate. Performance acceptance requires measured redirect P95 ≤ 50 ms and creation P95 ≤ 200 ms at the target rates.

### 2. Brownfield Requirement — Add Optional Custom Aliases

- **Map to Part 1 Tasks:** Extend T-101 to approve the alias contract, T-103 for schema changes if needed, T-104 for creation behavior, T-105 to preserve redirect behavior, T-109 for regression tests, and T-111 for documentation. If accepted as new scope, complete T-112 and T-113 before implementation.
- **AI-assisted execution — example prompt:**

  > In the existing URL shortener, add an optional custom alias to `POST /api/v1/shorten` without breaking callers that provide only `destination_url`. First inspect the models, migration history, API schemas, services, and tests. Summarize the smallest compatible change and list decisions needing approval. Do not edit until I approve alias syntax, reserved words, collision response, maximum length, and case sensitivity. After approval, implement validation and persistence using the unique code constraint, preserve generated Base62 codes when no alias is supplied, document duplicate-alias behavior, and add regression and integration tests. Report changed files and exact validation results.

- **Expected AI output:** A repository-specific impact analysis and proposed tests/migration, followed only after approval by a focused, backward-compatible patch.
- **Human code refinement:** Approve syntax, reserved values, and case sensitivity. Verify the uniqueness constraint handles concurrent claims, old links remain resolvable, invalid aliases are not persisted, and migration rollback/compatibility is safe. Do not include expiration unless separately approved.
- **Output validation — proposed commands:** `pytest -q tests/test_shortening.py tests/test_redirects.py tests/test_custom_aliases.py` (adjust selectors to the actual suite), followed by `pytest -q`. Apply the migration to both an empty database and a database at the current schema version.
- **Validation criteria:** Existing request payloads still work; accepted aliases follow the approved rules and redirect correctly; malformed/reserved aliases are rejected; duplicate aliases return the documented conflict even under concurrent requests; generated codes and existing rows remain valid.

### 3. Ambiguous Requirement — “Make Tracking Secure and Safe”

- **Map to Part 1 Tasks:** Start with T-101 to clarify intent. Review baseline analytics in T-106 and the API in T-107. Complete T-114 to clarify and approve privacy, retention, access, or durability requirements; implement only approved changes through T-108 and/or T-115; verify via T-109 and update T-111. Revisit T-103 only if an approved change requires schema updates. T-106 is already part of baseline analytics and is not an instruction to collect more data.
- **AI-assisted execution — ambiguity-resolution prompt:**

  > The request is “make tracking secure and safe.” Do not implement changes or add data collection yet. Based on the URL-shortener design, identify possible interpretations: privacy/data minimization, analytics event integrity, access control, abuse prevention, retention/deletion, or delivery reliability. Ask focused questions about required event fields, who can access analytics, retention, acceptable click loss, and public-service exposure. Separate current design facts from assumptions, rank risks, and propose a minimal option and alternatives. Do not add IP addresses, user agents, authentication, rate limiting, or an outbox unless the corresponding requirement is approved.

- **Expected AI design output:** Clarifying questions and a decision table separating privacy, durability, access, and abuse controls. Current design facts include a minimal event of UUID, link ID, and UTC click time; no IP/user-agent collection; Redis Streams and idempotent worker processing; and best-effort click publication.
- **Human architectural refinement:** Have the product/security owner define protected assets, analytics readers, required fields, retention/deletion obligations, acceptable event loss, and whether the service is public. Record decisions in requirements/design before implementation. Add an outbox only if loss-resistant delivery is required; add access controls only if approved. Keep personal data out unless its need and handling are explicitly established.
- **Output validation — proposed checks:** Apply any approved migration and inspect `click_events` columns, constraints, and indexes—for example, `psql "$DATABASE_URL" -c "\d+ click_events"`. Run `pytest -q tests/integration/test_analytics.py` and the broader integration suite against PostgreSQL and Redis. For durability changes, inject failures and verify recovery and idempotency. For privacy changes, inspect schema, stream fields, API responses, and logs for only approved fields.
- **Validation criteria:** Schema and telemetry contain no unapproved personal data; event processing matches the approved loss/recovery and access policy; migrations and integration tests pass; retention and operational limitations are documented. Until clarified and tested, the request remains unresolved.

## Validation Status

The example commands in this breakdown are proposed for the corresponding service tasks. T-102 has been implemented and its focused tests passed; the user separately reported live validation with PostgreSQL and Redis running. T-103 models and reversible migration are implemented and unit/offline-SQL validated; the user reports successful PostgreSQL schema inspection and constraint tests. Exact commands and individual test details were not recorded. Load tests for Q-6/Q-7 have not been run; T-104 onward and the full service test suite remain outstanding.
