# Requirement Analysis

**Source:** [Business requirement](01-business-requirement.md)<br>
**Status:** Cross-scenario analysis baseline for the assignment prototype<br>
**Purpose:** Turn business outcomes into verifiable requirements and preserve
traceability without treating engineering choices as business approval.

## Interpretation

The assignment has two connected outcomes:

1. A runnable, engineer-directed workflow that accepts a requirement and
   produces structured engineering outputs for review.
2. A URL-shortener example that demonstrates implementation, tests,
   documentation, and evidence across greenfield, brownfield, and ambiguous
   scenarios.

The candidate retains ownership of AI-assisted output. No AI response, local
template, or generated artifact is automatically an approved requirement.

## Cross-cutting functional requirements

| ID | Requirement | Source | Priority |
|---|---|---|---|
| REQ-1 | The runnable prototype accepts a software requirement as input. | BR-1 | Must |
| REQ-2 | For an input, the prototype produces structured outputs sufficient to review interpretation and proposed engineering work. | BR-1 | Must |
| REQ-3 | In the overall engineer-directed workflow, the engineer reviews, refines, or rejects AI-assisted suggestions before treating them as accepted outputs. The local CLI itself uses deterministic templates and does not call an AI model. | BR-2 | Must |
| REQ-9 | The solution includes greenfield, brownfield, and ambiguous examples, each showing input, task breakdown, AI-assisted work, human review, and validation. | BR-4 | Must |
| REQ-10 | The solution includes architecture, setup, testing, and a summary of artifacts, decisions, risks, assumptions, and limitations. | BR-5 | Must |

## Scenario requirements

### Greenfield: URL-shortener baseline

| ID | Requirement | Priority |
|---|---|---|
| REQ-4 | Provide an API operation to create a short link from a valid destination URL. | Must |
| REQ-5 | Persist the short-link mapping. | Must |
| REQ-6 | Redirect a request to a known short code to its stored destination. | Must |
| REQ-7 | Record link usage and expose analytics through a documented API or interface. | Must |
| REQ-8 | Document and return appropriate error behavior for invalid input and unknown short links. | Must |

Details and the architecture-specific Q-6/Q-7 targets are in the
[greenfield requirements](Greenfield_requirement.MD).

### Brownfield: optional custom aliases

The alias contract is a separately accepted extension; it does not change
greenfield requirements for callers that omit an alias. The detailed
validation, reserved names, conflict response, and acceptance checks are in
the [brownfield requirements](Brownfield_requirement.MD). Implementation is
tracked by T-112/T-113.

### Ambiguous: tracking privacy and safety

The initial request “Make tracking secure and safe” required clarification
before implementation. Its accepted interpretation covers minimal click-event
fields, retention, analytics access, rate limiting, trusted proxies, and
best-effort event delivery. See the [ambiguous requirements](Ambiguous_requirement.MD);
implementation and validation are tracked by T-114/T-115.

## Quality and engineering requirements

| ID | Requirement | Source | Priority / status |
|---|---|---|---|
| Q-1 | Candidate reviews AI-assisted code and documentation before acceptance. | BR-2 | Must |
| Q-2 | Automated tests cover core URL-shortener creation, persistence, redirect, analytics, and error behavior. | BR-3 | Must |
| Q-3 | Validation approach, commands, and results are documented. | BR-5 | Must |
| Q-4 | Design discusses security, scalability, and performance and discloses known limitations. | BR-3, BR-5 | Must |
| Q-5 | Deliverables are understandable and maintainable, with clear responsibilities and readable documentation. | BR-5 | Should |
| Q-6 | For the architecture-supplied workload, support approximately 1,000 redirects/s and 10 creations/s (100:1 ratio). | Engineering design input | Unverified validation target |
| Q-7 | At the Q-6 workload, redirect P95 <= 50 ms and `POST /api/v1/shorten` P95 <= 200 ms. | Engineering design input | Unverified validation target |

Q-6/Q-7 are engineering targets, not numeric targets supplied by the
assignment or approved by an external stakeholder. "Unverified validation
target" means these values must be tested; it does not mean they have passed
or are accepted commitments. Acceptance requires measurements under a
representative workload and environment. Current local results miss the
targets; see [performance evidence](04-engineering-breakdown.md) and
[risk/assumption reference](05-risk-assumptions-database-design.md).

## Acceptance checks

- A reviewer can start the prototype using documented setup instructions.
- The prototype accepts a requirement and emits structured, reviewable
  output.
- The local requirement-processing CLI produces deterministic drafts without
  making live AI calls; any separate AI-assisted analysis is reviewed by a
  human before acceptance. No autonomous approval is implied.
- A valid URL can be shortened, persisted, and resolved through a redirect.
- Analytics are recorded and retrievable through the documented interface.
- Invalid input and unknown codes return documented errors.
- Automated tests cover core behavior and can be run with documented commands.
- Each scenario has input, AI-assisted work, human decision, and validation
  evidence.
- The architecture, trade-offs, risks, assumptions, limitations, and current
  validation state are documented.
- Q-6/Q-7 remain unaccepted unless measured throughput, workload ratio, and
  client-observed latency meet the stated thresholds.

## Decisions and assumptions

| Topic | Analysis | Status |
|---|---|---|
| AI integration | AI assists engineering tasks; a live AI provider is not required inside the runnable prototype. | Local requirement-processing CLI is deterministic and explicitly does not call an AI model. |
| Technology | The assignment does not mandate a stack. PostgreSQL/Redis and detailed APIs are selected for this engineering design. | Design constraint for this use case; not externally approved policy. |
| Analytics | Baseline requires recording and retrieving link usage. The detailed accepted collection, retention, and access rules are scenario-specific. | See [ambiguous requirements](Ambiguous_requirement.MD). |
| Requirement-processing CLI | The runnable local CLI structures scenario inputs into drafts using deterministic templates; it does not provide live AI analysis. | AI-assisted analysis and human review are documented separately from CLI output. |
| Custom aliases | Not part of baseline; accepted separately as an extension. | See [brownfield requirements](Brownfield_requirement.MD). |
| Performance | Numeric Q-6/Q-7 values come from the architecture input, not business approval. | Targets remain unaccepted pending representative measurement. |
| Approval | No external stakeholder is provided for the assignment. | Approval is simulated by the candidate and must be described as such. |

## Traceability to implementation and evidence

| Requirement area | Implementation / plan | Evidence |
|---|---|---|
| Prototype workflow, REQ-1–REQ-3 | `src/requirement_processor/` | `tests/test_requirement_processor.py`, README usage |
| Greenfield, REQ-4–REQ-8 and Q-6/Q-7 | `docs/03-engineering-design.md`; T-101–T-111 in `docs/04-engineering-breakdown.md` | `evidence/greenfield/` and benchmark reports |
| Brownfield aliases | T-112/T-113 in `docs/04-engineering-breakdown.md` | `evidence/brownfield/` |
| Ambiguous tracking | T-114/T-115 in `docs/04-engineering-breakdown.md` | `evidence/ambiguous/` |
| Cross-cutting quality, Q-1–Q-5 | Engineering review, tests, and documentation | `docs/ai-usage-log.md` and the scenario validation records |

## Analysis sign-off

This analysis organizes the accepted assignment baseline and the separately
accepted scenario extensions. It does not imply external stakeholder
approval, production readiness, or performance acceptance.
