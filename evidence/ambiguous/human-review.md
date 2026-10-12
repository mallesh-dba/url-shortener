# Ambiguous Scenario Human Review

- **Decision:** Requirements accepted by the user on 2026-10-12, as recorded in
  [the reviewed scenario artifact](../../output/ambiguous-reviewed.json).
- **Accepted scope:** “Tracking” means click analytics. Store only event ID,
  short-link code, and UTC click timestamp; collect no IP address, user-agent,
  or other personal data. Delete raw click events after 90 days and retain
  aggregate counts for 12 months. Require authenticated, authorized analytics
  access. Use a shared Bearer API key and Redis-backed per-client-IP limits of
  10 creations, 120 redirects, and 60 analytics requests per minute. Honor
  forwarded client addresses only when the immediate peer is in an explicitly
  configured trusted-proxy CIDR. Redirects remain independent of analytics;
  publication is best effort, may be delayed, and may lose a click if the API
  process fails before publishing.
- **Acceptance boundary:** This decision accepts requirements only. It is not
  implementation or validation acceptance and does not approve public
  deployment. The shared token has no per-user or per-link authorization.
- **Task mapping:** Initial clarification and code/design review map to T-101,
  T-106, and T-107; explicit requirements acceptance completes T-114;
  implementation is T-115 (with schema changes under T-103); automated and
  live verification are T-109; documentation/evidence is T-111.
- **Remaining production decisions:** Destination-abuse reporting/blocking,
  link ownership and administrative access, secret rotation/operations,
  backup/restore, and deployment/network review.
