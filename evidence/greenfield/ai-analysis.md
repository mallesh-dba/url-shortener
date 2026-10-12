# Greenfield AI-Assisted Analysis

**Evidence date:** 2026-10-12  
**Source:** AI assistant analysis generated for this evidence capture, separate from the local template CLI.

## Reproducible prompt

> Analyze the greenfield URL-shortener requirement using `docs/01-business-requirement.md`, `docs/02-requirement-analysis.md`, and `docs/03-engineering-design.md`. Preserve Python 3.11+, FastAPI, async SQLAlchemy 2.x, PostgreSQL, Redis, and the documented API contracts. Return a structured draft with summary, functional and quality requirements, assumptions, open questions, risks, ordered tasks with dependencies, tests, and acceptance checks. Do not claim Q-6/Q-7 pass without measurements. Mark it pending human review.

## AI response

### Summary

Build the documented URL-shortener baseline: create and persist a short code,
redirect known codes, and record/retrieve click analytics asynchronously. This
is an engineering plan, not external stakeholder approval or proof that
performance targets pass.

### Functional requirements

- `POST /api/v1/shorten` validates an absolute HTTP(S) destination and returns
  `201` with `code`, `short_url`, and `created_at`.
- Persist mappings in PostgreSQL; treat it as the source of truth.
- `GET /{code}` returns `302` for a known code, `404` only after PostgreSQL
  confirms it is missing, and `503` when lookup cannot be completed.
- Record click events asynchronously and expose `code` and `clicks_total` from
  `GET /api/v1/links/{code}/analytics`; recent counts may lag.
- Do not dereference destination URLs during creation.

### Quality requirements

- Preserve Python 3.11+, FastAPI, async SQLAlchemy 2.x, PostgreSQL, and Redis.
- Make event persistence idempotent and acknowledge stream entries only after
  database commit.
- Validate Q-6 at approximately 1,000 redirects/s and 10 creations/s (100:1).
- Validate Q-7 at redirect P95 <= 50 ms and creation P95 <= 200 ms under that
  workload; report measured outcomes without treating targets as met in
  advance.

### Assumptions

- The engineering design defines the API and stack for this use case.
- Only HTTP(S) destination URLs are accepted.
- Alias support, expiration, authentication, deletion, and IP/user-agent
  collection are outside this baseline.
- Click delivery is best effort; a process failure before background
  publication can lose a click.

### Open questions

- What auth, rate limiting, and abuse controls are needed before any public
  deployment?
- What representative test environment and separate load generator will be
  used for formal Q-6/Q-7 acceptance?
- Is the documented best-effort click-loss window acceptable for the intended
  prototype?

### Risks

- Local load-generator and service co-location do not establish deployed
  performance.
- Background click publication can lose events if the process fails before
  publication; asynchronous processing can delay analytics.
- Exposing an unauthenticated shortener publicly can enable abuse.

### Ordered tasks

**Part 1 task mapping:** T-101 through T-111, in order.

| ID | Task | Dependencies |
|---|---|---|
| T-101 | Define baseline requirements and acceptance criteria | — |
| T-102 | Set up async application and configuration | T-101 |
| T-103 | Create link and click-event schema | T-102 |
| T-104 | Implement link creation and persistence | T-103 |
| T-105 | Implement cached redirects and database fallback | T-104 |
| T-106 | Implement Redis Stream analytics pipeline | T-103, T-105 |
| T-107 | Implement analytics API | T-103, T-106 |
| T-108 | Implement security, reliability, and observability controls | T-104–T-107 |
| T-109 | Add automated and integration tests | T-104–T-108 |
| T-110 | Measure capacity and latency targets | T-108, T-109 |
| T-111 | Document and sign off engineering deliverables | T-109, T-110 |

AI can accelerate traceability, scaffold/test drafts, and failure-case review;
the engineer must inspect schema constraints, cache fallback, event commit/ack
ordering, URL validation, and every claimed test/benchmark result.

### Tests and acceptance checks

- Run `python -m pytest -q`; enable the PostgreSQL/Redis integration test after
  configuring dependencies and applying migrations.
- Verify creation, durable persistence, 302 redirect, 404/503 distinction,
  asynchronous analytics, event idempotency, and dependency-failure behavior.
- Inspect the applied PostgreSQL schema and verify unique code/event constraints.
- Record actual workload, environment, cache mode, throughput, latency, errors,
  event drain, and cleanup for load tests.
- Accept Q-6/Q-7 only if measured throughput/ratio and client-observed P95
  thresholds pass in a representative environment.
- Keep AI-generated output pending until a human reviews and records a decision.
