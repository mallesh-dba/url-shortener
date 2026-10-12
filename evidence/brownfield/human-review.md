# Brownfield Human Review

- **Decision:** Accepted; the user confirmed the alias rules during the
  conversation. See `output/brownfield-reviewed-accepted.json` and
  `output/brownfield-reviewed.json`.
- **Accepted rules:** 3–16 lowercase ASCII letters/digits/hyphens,
  alphanumeric first/last characters; reserve `api`, `health`, `metrics`,
  `docs`, `redoc`, and `openapi.json`; duplicates return HTTP 409
  `short_code_conflict`.
- **Compatibility:** `custom_alias` is optional. Requests omitting it retain
  generated-code behavior. Expiration is not included.
- **Part 1 task mapping:** T-112 approves the contract; T-113 implements it;
  T-109 covers regression/integration validation; T-111 records the decision
  and evidence. These tasks are defined in `docs/04-engineering-breakdown.md`.
- **Human implementation review:** Existing `VARCHAR(16)` and unique
  `uq_short_links_code` support the rules; no migration was needed. The
  implementation validates before persistence and maps requested-alias
  unique conflicts to 409.
- **Review scope:** This records feature acceptance and implementation review,
  not external business approval or capacity acceptance.
