# Ambiguous Requirement: Secure and Safe Tracking

**Scenario input:** “Make tracking secure and safe.”  
**Status:** Clarified requirements accepted on 2026-10-12; implementation and
validation are recorded separately.  
**Scenario type:** Ambiguous requirement applied to the URL-shortener baseline.

## Initial ambiguity

“Tracking” could mean click analytics, privacy, event integrity, access
control, abuse prevention, retention, or delivery reliability. No security,
privacy, collection, or durability behavior should be inferred from that
phrase alone.

## Accepted requirements

| ID | Requirement |
|---|---|
| AMB-1 | Treat tracking as per-link click analytics. Do not collect IP addresses, user-agent values, or other personal data in click events. |
| AMB-2 | Store only event ID, short-link code, and UTC click timestamp in raw click events. |
| AMB-3 | Retain raw click events for 90 days. Retain daily aggregate counts and event-deduplication markers for 12 calendar months. |
| AMB-4 | Protect analytics access with a configured shared API key. This is not per-user or per-link authorization. |
| AMB-5 | Apply Redis-backed per-client fixed-window limits of 10 link creations, 120 redirects, and 60 analytics requests per minute. Honor forwarded client addresses only when the immediate peer is in a configured trusted-proxy CIDR. |
| AMB-6 | Keep click publication asynchronous and best effort after the redirect response. Analytics may lag, and a process failure before publication or Redis data loss may lose clicks. Redirects must not wait for analytics persistence. |
| AMB-7 | Process events idempotently; acknowledge a Redis Stream item only after the database transaction commits. |

## Clarification and acceptance boundary

The user accepted the requirements above on 2026-10-12. This is requirements
acceptance for the assignment, not external stakeholder approval, production
deployment approval, or evidence that every behavior has passed validation.
Implementation and evidence are recorded in the
[ambiguous scenario evidence](../evidence/ambiguous/ai-analysis.md),
[human review](../evidence/ambiguous/human-review.md), and
[validation record](../evidence/ambiguous/validation.md).

## Open risks and out of scope

- The shared key does not provide fine-grained authorization.
- Destination-abuse review, link ownership/administration, and loss-resistant
  event delivery are not included.
- Secret rotation, deployment/network review, and backup/restore need separate
  operational decisions before production use.

## Traceability

This scenario supplements the
[greenfield requirements](Greenfield_requirement.MD); it does not replace or
rewrite the baseline. Its implementation is tracked by T-114/T-115 in the
[engineering breakdown](04-engineering-breakdown.md).
