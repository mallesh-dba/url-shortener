# AI-Assisted Work Log

Use this log to track meaningful AI-assisted tasks, engineer review, edge cases, resulting changes, and validation. Record exact prompts when available; otherwise label them as summaries. Mark entries added after completion as retrospective. Do not invent missing details or include secrets.

## Completed Tasks

| Task | Prompt summary and AI contribution | Engineer review, edge cases, and resulting changes | Validation and artifacts |
|---|---|---|---|
| Business requirement and analysis (retrospective, 2026-10-08) | Asked AI to turn the assignment into business requirements and a requirement analysis, keeping unspecified implementation choices open. AI drafted scope, requirements, acceptance checks, and assumptions. | Compared with the assignment. Identified that “scalable” has no numeric target, no stack or external approver is specified, and test criteria should be planned before coding while tests run during or after implementation. Kept stack open, labeled approval simulated, and clarified test timing. | Compared against the assignment brief; editor diagnostics reported no errors. [Business requirement](01-business-requirement.md); [Requirement analysis](02-requirement-analysis.md). Exact prompt and model details were not recorded. |

## In-Progress Tasks

| Task | Prompt summary and AI contribution | Engineer review, edge cases, and resulting changes | Validation and artifacts |
|---|---|---|---|
| None currently | Add a row when a task starts; summarize the prompt and AI contribution. | Record review decisions and edge cases as they are found. | Record checks performed and link relevant artifacts. |

## Planned Tasks

| Task | Prompt / AI contribution to record | Engineer review / edge cases to record | Validation / artifacts to record |
|---|---|---|---|
| Engineering design | Prompt, alternatives, and AI suggestions considered. | Design decisions, trade-offs, assumptions, and rejected suggestions. | Design review and links to design artifacts. |
| Task breakdown | Prompt and AI-suggested tasks or dependencies. | Correctness, missing dependencies, sequencing changes, and scope decisions. | Review against requirements and links to the task plan. |
| Implementation | Prompt and AI-assisted code, debugging, or refactoring. | Code review, edge cases, changes, and rejected suggestions. | Relevant tests, results, and code links. |
| Testing, examples, and documentation | Prompt and AI-assisted tests, scenarios, or documentation. | Coverage gaps, accuracy checks, and edits. | Test commands/results and links to final artifacts. |
