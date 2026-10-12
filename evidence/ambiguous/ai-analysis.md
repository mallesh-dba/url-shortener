# Ambiguous Requirement AI-Assisted Analysis

**Evidence date:** 2026-10-12  
**Input:** “Make tracking secure and safe.” Analysis generated for this evidence capture.

## Reproducible prompt

> Analyze “Make tracking secure and safe” against the current URL-shortener requirements, engineering design, and implementation. Do not implement changes or guess intent. Separate verified design facts from assumptions. Identify clarifying questions covering tracking fields, privacy and retention, access, abuse/threat model, acceptable event loss/delay, and exposure of the service. Do not recommend collecting IP addresses or user-agent values or replacing Redis Streams unless a human-approved requirement supports it. Return a draft interpretation, known facts, open questions, risks, candidate task breakdown with dependencies, tests, and acceptance checks. Keep the result pending human review.

## AI response

### Draft interpretation

The request is too broad to translate safely into implementation tasks without
clarification. “Secure and safe” may refer to privacy/data minimization,
event integrity, analytics access, abuse prevention, retention/deletion, or
delivery reliability. Treat these as alternatives to clarify, not approved
requirements.

### Verified baseline facts

- The current design uses Redis Streams and an asynchronous analytics worker.
- Events carry event ID, link identity, and UTC click time.
- PostgreSQL stores click events and aggregate counts; event processing is
  idempotent and acknowledges after transaction commit.
- Click publication after the redirect response is best effort. A process
  failure before publication may lose an event; aggregate analytics may lag.
- The baseline does not require collecting IP addresses or user-agent values.
- The service has no documented production authentication/rate-limiting policy;
  deployment is not claimed production ready.

### Assumptions (not approvals)

- “Tracking” refers to click analytics unless the requester clarifies otherwise.
- Existing data minimization and best-effort delivery remain in force until
  decisions change them.
- No extra personal data, access controls, retention behavior, or delivery
  guarantees should be introduced speculatively.

### Clarifying questions

1. Which concern is the priority: data privacy, event tampering, unauthorized
   analytics access, abuse of redirects, retention/deletion, or event loss?
2. What event fields are strictly needed, and are IP address or user-agent data
   explicitly required? What is the purpose and legal basis?
3. Who should access analytics, and is authentication/authorization required?
4. What retention period, deletion workflow, and backup deletion obligations
   apply?
5. Is the service public? Which abuse cases and request-rate limits must be
   addressed?
6. What click loss and reporting delay are acceptable? Must redirects wait for
   durable event publication, or is best-effort tracking acceptable?

### Risks

- Guessing could add unnecessary personal data and retention obligations.
- Leaving access policy undefined may expose analytics if deployed publicly.
- Current best-effort publication can lose clicks in a process-failure window.
- Adding synchronous work or an outbox changes complexity and redirect
  behavior; do so only if the required durability warrants it.

### Candidate tasks and dependencies

| ID | Candidate task | Dependencies |
|---|---|---|
| T-101 | Clarify the request and threat model | — |
| T-106 | Review the current event pipeline and delivery guarantees | T-101 |
| T-107 | Review the analytics API and access surface | T-101 |
| T-114 | Clarify and approve analytics privacy/durability requirements | T-101, T-106, T-107 |
| T-108 | Implement approved security/reliability controls | T-114 |
| T-115 | Implement approved analytics privacy/durability controls, if any | T-114, T-106 |
| T-109 | Verify approved behavior with tests/failure injection | T-108 and/or T-115 |
| T-111 | Document decisions, evidence, and remaining limitations | T-109 |

### Validation and acceptance checks

- Before decisions: inspect current schema, stream fields, API responses, logs,
  and metric labels; verify no unapproved data was introduced.
- After decisions: test only the explicitly approved fields, access policy,
  retention, and failure/recovery behavior.
- If durability changes are approved, inject failures and verify recovery,
  idempotency, and commit-before-ack behavior.
- Do not mark this request accepted for implementation until the relevant
  questions are answered by a human and captured in the requirements/design.

The preceding section records the initial clarification analysis. The later
human decision and implementation work are recorded below; requirements
acceptance is separate from implementation and validation acceptance.

## Subsequent human decision and implementation work

The user later accepted a concrete requirements scope, recorded in
[human-review.md](human-review.md) and
[`output/ambiguous-reviewed.json`](../../output/ambiguous-reviewed.json).
That acceptance did not itself certify implementation.

**Implementation prompt summary (retrospective, not verbatim):** Implement only
the accepted privacy, retention, analytics-access, rate-limit, and trusted-proxy
requirements. Preserve the existing Redis Streams worker and best-effort
redirect behavior; add the schema changes, focused tests, and truthful
documentation/evidence. Do not claim deployment approval or durable tracking.

**AI-assisted output:** Reviewed the analytics models, worker, API, middleware,
settings, migration chain, tests, docs, and scenario evidence. Implemented
daily retained aggregates and event-ID deduplication, changed new raw events
and Redis Stream payloads to event ID/code/UTC timestamp, retained compatibility
with already-pending legacy `link_id` stream entries, added the shared analytics
Bearer key and Redis fixed-window limits, and added trusted-proxy client-address
resolution. Added migrations and updated focused coverage/documentation.

**Human review/refinement:** Kept redirect publication asynchronous and
best-effort as accepted; did not add IP/user-agent event fields or replace
Redis Streams. Preserved pre-existing aggregate totals by seeding one baseline
bucket at migration-time UTC date because the old lifetime counter has no
per-click dates; this transitional baseline is disclosed and remains visible
for up to 12 months after migration. Live migration and service integration
remain pending; see [validation.md](validation.md).
