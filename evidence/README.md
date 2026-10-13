# Scenario Evidence

This folder preserves requirement inputs/prompts, AI-assisted analyses, human
review outcomes, and validation evidence for REQ-9. These analyses were
prepared by the AI assistant against the project documents and current code;
they are distinct from the deterministic local templates produced by
`python -m requirement_processor analyze`.

The prompts are reproducible prompts written for this evidence capture; the
analyses were generated for and captured in this task. They are not claimed to
be verbatim transcripts of earlier assistant turns that were not saved.

| Scenario | AI analysis | Human review | Validation |
|---|---|---|---|
| Greenfield | [Prompt and response](greenfield/ai-analysis.md) | [Review record](greenfield/human-review.md) | [Checks](greenfield/validation.md) |
| Brownfield | [Prompt and response](brownfield/ai-analysis.md) | [Review record](brownfield/human-review.md) | [Checks](brownfield/validation.md) |
| Ambiguous | [Prompt and response](ambiguous/ai-analysis.md) | [Review record](ambiguous/human-review.md) | [Checks](ambiguous/validation.md) |

For baseline task-by-task human verification, see the
[T-101–T-111 record in greenfield validation](greenfield/validation.md#baseline-human-validation-t-101-through-t-111).
Human decisions are recorded only when supported by review artifacts or user
confirmation. The ambiguous tracking migrations, live PostgreSQL/Redis
integration tests, and manual worker-to-aggregate smoke check are complete.
Local benchmark results do not meet Q-6/Q-7 and are not represented as accepted;
assignment-level setup/sign-off has been completed in a newly created Python
environment; production deployment and capacity sign-off remain pending.
