# Requirement Analysis

**Source:** [Business Requirement](01-business-requirement.md)  
**Status:** Analysis baseline for assignment prototype  
**Purpose:** Convert business outcomes into verifiable requirements without prematurely selecting an implementation stack.

## Interpretation

The assignment has two related outcomes:

1. A runnable prototype that accepts a software requirement and produces structured engineering outputs through an engineer-directed workflow.
2. An engineering demonstration that applies this approach to the URL-shortener use case and validates the resulting code, API contracts, tests, and documentation.

The prototype must not imply that AI autonomously owns or approves engineering decisions. The implementation and evidence must make human review visible.

## Functional Requirements

| ID | Requirement | Source | Priority |
|---|---|---|---|
| REQ-1 | The runnable prototype shall accept a software requirement as input. | BR-1 | Must |
| REQ-2 | For an input requirement, the prototype shall produce structured outputs sufficient to review the requirement interpretation and proposed engineering work. | BR-1 | Must |
| REQ-3 | The workflow shall let the engineer review, refine, or reject AI suggestions before treating them as accepted outputs. | BR-2 | Must |
| REQ-4 | The URL-shortener example shall provide an API operation to create a short link from a valid destination URL. | BR-3 | Must |
| REQ-5 | The URL-shortener implementation shall persist the short-link mapping. | BR-3 | Must |
| REQ-6 | A request to a known short link shall redirect to its stored destination. | BR-3 | Must |
| REQ-7 | The URL-shortener implementation shall record link usage and expose analytics through a documented API or interface. | BR-3 | Must |
| REQ-8 | Invalid input and unknown short links shall produce documented error behavior. | BR-3 | Must |
| REQ-9 | The solution shall include greenfield, brownfield, and ambiguous examples. Each example shall show the input, task breakdown, AI-assisted work, and validation. | BR-4 | Must |
| REQ-10 | The solution shall include an architecture overview, setup instructions, testing approach, and an engineering summary of artifacts, decisions, risks, assumptions, and limitations. | BR-5 | Must |

## Quality and Engineering Requirements

| ID | Requirement | Source | Priority |
|---|---|---|---|
| Q-1 | Generated or AI-assisted code and documentation shall be reviewed by the candidate before acceptance. | BR-2 | Must |
| Q-2 | Automated tests shall cover the URL-shortener's core create, persistence, redirect, analytics, and error behaviors. | BR-3 | Must |
| Q-3 | The solution shall document how correctness and output quality were validated, including test commands and results. | BR-5 | Must |
| Q-4 | The design shall discuss scalability, security, and performance considerations and disclose known limitations. | BR-3, BR-5 | Must |
| Q-5 | The solution shall be maintainable and understandable to a reviewer, with clear separation of responsibilities and readable documentation. | BR-5 | Should |
| Q-6 | Under the specified peak workload, the URL-shortener shall support a 100:1 redirect-to-creation request ratio, with approximately 1,000 redirect requests per second and 10 link-creation requests per second. | Performance targets supplied for the architecture | Must |
| Q-7 | At the specified peak workload, redirect latency for `GET /{short_code}` shall be P95 <= 50 ms and shortening latency for `POST /api/v1/shorten` shall be P95 <= 200 ms. | Performance targets supplied for the architecture | Must |

## Acceptance Checks

- A reviewer can start the prototype using the documented setup instructions.
- The prototype accepts a requirement and returns structured, reviewable outputs.
- The engineer's role in directing and validating AI assistance is demonstrated; no autonomous approval is implied.
- A valid URL can be shortened, persisted, and later resolved through a redirect.
- Analytics are recorded and retrievable using the documented API or interface.
- Invalid input and unknown short codes return the documented errors.
- Automated tests exercise the core URL-shortener behaviors and can be run using the documented command.
- Performance validation reports the workload, test duration, environment, and cache state, and evaluates Q-6 and Q-7 against the specified peak request rates and P95 limits.
- Each of the three required example scenarios includes task decomposition, AI-assisted execution, and validation evidence.
- Architecture, trade-offs, risks, assumptions, and limitations are documented.

## Clarifications, Assumptions, and Decisions

| Topic | Current interpretation or assumption | Status / follow-up |
|---|---|---|
| Performance targets | The architecture input specifies a 100:1 redirect-to-creation ratio, peak rates of about 1,000 redirects/s and 10 creations/s, and P95 limits of 50 ms and 200 ms respectively. | Treat as required targets; benchmark environment, duration, and cache-state methodology still need to be defined. |
| Analytics scope | At minimum, analytics means recording and retrieving usage for a short link. Exact metrics and granularity are not specified. | Assumption; state the chosen scope in design. |
| AI integration | AI tools must assist development tasks. The assignment does not explicitly require embedding a live AI provider in the runnable prototype. | Design decision; explain the selected demonstration approach. |
| Technology stack | The assignment itself does not mandate a stack. The architecture input specifies Python 3.11+, FastAPI, async SQLAlchemy 2.0, PostgreSQL, and Redis for this design. | Treat as architecture constraints for this use case; record separately if they become approved project-wide requirements. |
| Short-link behavior | The assignment does not specify custom aliases, expiration, deletion, or authentication. | Out of scope unless chosen and documented. |
| Analytics privacy | Collection of IP addresses, user-agent strings, or other personal data is not required by the assignment. | Avoid unless justified; document any collection and retention. |
| Approval | No actual business stakeholder is provided for the interview assignment. | Baseline approval is simulated by the candidate and must be described as such. |

## Traceability to Next Artifacts

- **Engineering design:** Documents architecture, selected technologies, API/data approach, and trade-offs for REQ-1 through REQ-10.
- **Task breakdown:** Converts requirements into ordered tasks with dependencies, AI-assistance points, and validation checks.
- **Testing and validation:** Define verification criteria during requirements and design; create and run tests alongside or after implementation, then record results before accepting deliverables.

## Analysis Sign-Off

This analysis is ready to inform engineering design and task decomposition. Technology selection and detailed implementation sequencing remain engineering decisions for the next stage; they are not implied to have received stakeholder approval.
