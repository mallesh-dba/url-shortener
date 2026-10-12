# Brownfield AI-Assisted Analysis

**Evidence date:** 2026-10-12  
**Scenario:** Optional custom alias for the existing URL-shortener. Analysis generated for this evidence capture.

## Reproducible prompt

> Analyze and implement the accepted brownfield enhancement: add optional `custom_alias` to `POST /api/v1/shorten`. Rules confirmed by the user: 3–16 lowercase ASCII letters, digits, or hyphens; first and last characters alphanumeric; reserve `api`, `health`, `metrics`, `docs`, `redoc`, and `openapi.json`; duplicate code returns 409 `short_code_conflict`. Preserve generated Base62 codes when the alias is omitted and preserve existing API response behavior. Inspect schema before deciding whether a migration is needed. Do not add expiration.

## AI response

### Summary and requirements

The alias is an optional caller-selected value stored as the public `code`.
Requests that omit it continue to use the generated Base62 code path. Alias
and generated codes must occupy the same namespace; a database uniqueness
constraint must arbitrate concurrent duplicate claims.

### Confirmed decisions

- Accept 3–16 lowercase ASCII letters, digits, and hyphens.
- First and last characters must be alphanumeric; uppercase is rejected.
- Reserve `api`, `health`, `metrics`, `docs`, `redoc`, and `openapi.json`.
- Return HTTP 409 using the standard error envelope and
  `short_code_conflict` for a duplicate code.
- Keep `custom_alias` optional; preserve the existing response fields.
- Do not add expiration.

### Implementation assessment

The existing `short_links.code` is `VARCHAR(16)` with unique constraint
`uq_short_links_code`. Those existing schema properties support the approved
alias contract and generated-code namespace; no database migration is needed.
Validate alias input before persistence. On a unique violation for a supplied
alias, return 409 rather than retrying another value. Keep bounded code
regeneration only for generated-code collisions. Cache and redirect continue
to use the same `code` key.

### Risks and compatibility

- A requested alias can conflict with a previously generated code; return the
  same documented conflict rather than changing the alias.
- Validation must happen before database writes.
- Existing requests without `custom_alias` must continue to work unchanged.
- Reserved paths must not shadow application routes.

### Task mapping

| ID | Work | Dependency |
|---|---|---|
| T-112 | Agree alias syntax, reserved values, duplicate contract, and compatibility | T-101 |
| T-113 | Add optional schema field, validation, persistence, and conflict mapping | T-112, T-103, T-104 |
| T-109 | Add regression and PostgreSQL/Redis integration coverage | T-113 |
| T-111 | Document accepted contract and validation evidence | T-112, T-113, T-109 |

### Validation and acceptance

- Test omitted alias, valid alias, invalid length/characters/case, first/last
  character rules, every reserved alias, and duplicate alias.
- With PostgreSQL and Redis, verify alias creation, cache-backed redirect,
  and duplicate conflict from the real unique constraint.
- Run focused tests and the full regular suite. Existing behavior must remain
  compatible for callers omitting the alias.

AI contribution: repository/schema impact analysis, implementation outline,
and failure-oriented test cases. Human validation is required for the actual
contract, implementation, and test results.
