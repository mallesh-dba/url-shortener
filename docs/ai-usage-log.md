# AI-Assisted Work Log

Use this log to track meaningful AI-assisted tasks, engineer review, edge cases, resulting changes, and validation. Record exact prompts when available; otherwise label them as summaries. Mark entries added after completion as retrospective. Do not invent missing details or include secrets.

## Completed Tasks

| Task | Prompt summary and AI contribution | Engineer review, edge cases, and resulting changes | Validation and artifacts |
|---|---|---|---|
| Business requirement and analysis (retrospective, 2026-10-08) | Asked AI to turn the assignment into business requirements and a requirement analysis, keeping unspecified implementation choices open. AI drafted scope, requirements, acceptance checks, and assumptions. | Compared with the assignment. Identified that “scalable” has no numeric target, no stack or external approver is specified, and test criteria should be planned before coding while tests run during or after implementation. Kept stack open, labeled approval simulated, and clarified test timing. | Compared against the assignment brief; editor diagnostics reported no errors. [Business requirement](01-business-requirement.md); [Requirement analysis](02-requirement-analysis.md). Exact prompt and model details were not recorded. |
| URL-shortener engineering design (2026-10-08) | Prompt summary: design for Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, and Redis; include creation/redirect flows, schema/indexes, cache TTL, telemetry, trade-offs, and workload/latency targets. AI drafted the architecture and performance rationale. | Compared with the analysis. Added supplied 100:1 ratio, ~1,000 redirect RPS, ~10 creation RPS, and endpoint P95 limits as Q-6/Q-7. Aligned the creation route to `POST /api/v1/shorten`. Documented analytics delivery risks and that performance targets still need benchmarking. | Design reviewed and merged; Markdown diagnostics passed. Load testing was not part of this task. The performance targets remain unverified. [Requirement analysis](02-requirement-analysis.md); [Engineering design](03-engineering-design.md). |
| Task breakdown and scenario mapping (2026-10-09) | Asked AI to derive a chronological implementation plan and greenfield, brownfield, and ambiguous workflows from the requirements and design. AI drafted dependency-linked tasks, example prompts, and validation criteria. | Standardized task titles as imperative, verb-first deliverables under sequential `T-NNN` IDs. Checked task order and behavior against REQ-1–REQ-10, Q-1–Q-7, the proposed API/schema, and analytics flow. Kept aliases, expiration, retention, extra tracking fields, and loss-resistant delivery conditional on approval; separated analytics requirement clarification from implementation. Distinguished example prompts and proposed tests from historical work and actual results. | Cross-checked against [Business requirement](01-business-requirement.md), [Requirement analysis](02-requirement-analysis.md), and [Engineering design](03-engineering-design.md). No `pytest` or load test was run because this workspace contains no implementation or test suite. [Engineering breakdown](04-engineering-breakdown.md). |

## In-Progress Tasks

| Task | Prompt summary and AI contribution | Engineer review, edge cases, and resulting changes | Validation and artifacts |
|---|---|---|---|
| None currently | Add a row when a task starts. | Record review decisions and edge cases as they are found. | Record checks performed and link relevant artifacts. |

## Planned Tasks

| Task | Prompt / AI contribution to record | Engineer review / edge cases to record | Validation / artifacts to record |
|---|---|---|---|
| Core service implementation (T-102–T-108) | Record the prompt and AI-assisted scaffold, schema, endpoint, redirect, analytics, and hardening work for each task as it starts. | Record reviewed diffs, edge cases, accepted/rejected suggestions, and deviations from the approved design. | Record focused tests, integration evidence, and code/migration links; do not claim unrun checks. |
| Verification and delivery (T-109–T-111) | Record AI assistance with test coverage, load-test analysis, and final documentation. | Record coverage gaps, actual measured outcomes, limitations, and corrections to AI-generated claims. | Record exact test and benchmark commands, environment, results, and final documentation links. |
| Approved conditional work (T-112–T-115) | Add an entry only if alias, expiration, or analytics privacy/durability scope is approved. | Record the approval and ensure implementation does not exceed it. | Record updated contract, migration/schema review, targeted tests, and integration results. |
