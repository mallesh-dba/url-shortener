# Brownfield Requirement: Optional Custom Aliases

**Scenario:** Extend the existing URL-shortener without breaking callers that
use generated short codes.  
**Status:** Contract accepted and implemented; validation details are recorded
separately.

## Requirement

Add an optional `custom_alias` field to `POST /api/v1/shorten`. When omitted,
the existing generated Base62 code behavior and API response contract remain
unchanged. Aliases and generated codes share the same short-code namespace.

## Accepted alias contract

| ID | Requirement |
|---|---|
| BF-1 | Accept aliases containing 3–16 lowercase ASCII letters, digits, or hyphens. |
| BF-2 | Require the first and last alias characters to be ASCII letters or digits; reject uppercase and all other characters. |
| BF-3 | Reserve `api`, `health`, `metrics`, `docs`, `redoc`, and `openapi.json`. |
| BF-4 | Return HTTP `409 Conflict` with error code `short_code_conflict` when the requested alias is already in use, including a collision with a generated code. |
| BF-5 | Keep aliases optional. Requests without one continue generating codes and preserve existing response behavior. |
| BF-6 | Enforce uniqueness through the existing `short_links.code` unique constraint. No schema migration is required for the implemented schema. |
| BF-7 | Do not add link expiration as part of this change. |

## Acceptance checks

- Requests with no alias retain the existing generated-code behavior.
- Valid aliases can be created and resolved by the existing redirect route.
- Invalid length, character, case, boundary-character, and reserved-name cases
  are rejected before persistence.
- Duplicate aliases return the documented `409` response.
- Regression and integration tests verify compatibility and persistence.

## Traceability and evidence

The user accepted this extension on 2026-10-12. It is separate from the
[greenfield requirements](Greenfield_requirement.MD). See the
[brownfield AI analysis](../evidence/brownfield/ai-analysis.md),
[human review](../evidence/brownfield/human-review.md), and
[validation record](../evidence/brownfield/validation.md). Implementation and
task status are summarized under T-112/T-113 in the
[engineering breakdown](04-engineering-breakdown.md).
