# Business Requirement: AI-Assisted Engineering Prototype

**Status:** Approved baseline for assignment planning (simulated)<br>
**Approval authority:** Candidate acting as business and engineering owner  
**External stakeholder approval:** Not obtained

## Business context and need

The assignment evaluates whether the candidate can use AI-assisted software
engineering while retaining engineering judgment and ownership. AI may help
analyze requirements, draft implementation, and identify tests, but a human
must review, refine, reject, and validate outputs before acceptance.

The mandatory engineering example is a URL-shortener service with APIs,
persistence, and analytics.

## Desired outcomes

1. A reviewer can run the prototype and provide a requirement for processing.
2. The prototype returns structured, reviewable engineering outputs.
3. The URL-shortener example demonstrates API behavior, persistence,
   analytics, tests, and supporting documentation.
4. Greenfield, brownfield, and ambiguous scenarios show how the workflow
   handles different kinds of requirements.
5. The candidate explains AI usage, design rationale, validation, risks,
   assumptions, and limitations.

## High-level business requirements

| ID | Requirement |
|---|---|
| BR-1 | Provide a runnable demonstration that accepts a software requirement and produces structured engineering outputs. |
| BR-2 | Demonstrate human-directed AI assistance; the candidate remains accountable for reviewing and accepting outputs. |
| BR-3 | Use the URL-shortener scenario to demonstrate a service with APIs, persistence, and analytics. |
| BR-4 | Include greenfield, brownfield, and ambiguous scenarios, each with execution and validation evidence. |
| BR-5 | Provide architecture, setup, testing, risk, implementation, and limitation documentation sufficient for evaluation. |

## Scenario requirement documents

The scenario-specific requirements are split across these documents:

| Scenario | Requirement document | Scope |
|---|---|---|
| Greenfield | [Greenfield requirements](Greenfield_requirement.MD) | Core URL-shortener requirements and architecture-specific performance targets. |
| Brownfield | [Brownfield requirements](Brownfield_requirement.MD) | Optional custom aliases, preserving generated-code compatibility. |
| Ambiguous | [Ambiguous requirements](Ambiguous_requirement.MD) | Clarified analytics privacy, retention, access, rate limiting, and event-delivery behavior. |

The [requirement analysis](02-requirement-analysis.md) keeps the shared
requirement IDs and maps them to scenario docs, implementation records, and
validation evidence.

## Scope boundaries

This is an interview-assignment prototype, not a commitment to launch or
operate a production service. The assignment itself does not prescribe a
programming language, framework, database, hosting provider, API routes, or
numeric performance targets. Technology choices and detailed service targets
are engineering design decisions and must not be presented as externally
approved business constraints.

## Business acceptance

The assignment baseline is accepted for prototype planning when the outcomes
and scope above are understood. The prototype is ready for evaluation when it
runs using documented instructions, demonstrates the required scenarios and
URL-shortener use case, and presents evidence of testing and engineering
review.

## Approval record

This is simulated approval for the interview assignment only; it is not
external stakeholder sign-off.

| Role | Name | Decision | Date |
|---|---|---|---|
| Business / Engineering owner (simulated) | Candidate | Approved as assignment baseline | 2026-10-08 |
| External stakeholder | Not applicable | No external approval obtained | Not applicable |
