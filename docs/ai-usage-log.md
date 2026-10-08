# AI-Assisted Work Log

This log records meaningful AI-assisted tasks and the engineer's review of the resulting work. Record what AI was asked to do, what it contributed, what the engineer checked or changed, edge cases found, and how the final result was validated.

For entries written after a task is complete, mark them **Retrospective**. Label a prompt as a summary unless the exact prompt was preserved. Do not invent missing prompts, model details, review actions, or validation results. Do not include secrets or sensitive data.

## Task Entry Template

### [Task ID] - [Task name]

- **Date:**
- **Status:** Planned / In progress / Reviewed / Validated
- **Record type:** Contemporaneous / Retrospective
- **AI tool/model:** Record only what is known
- **Task objective:**
- **Inputs and context:** Requirements, files, or constraints supplied to AI
- **Prompt:** Exact prompt or clearly labeled summary
- **AI contribution:** Suggestions, analysis, code, tests, or documentation produced
- **Engineer review:** Checks performed; what was accepted, changed, or rejected and why
- **Edge cases or gaps found:**
- **Resulting changes:**
- **Validation:** Checks performed and actual results
- **Related artifacts:** Links to files, commits, tests, or review evidence

## Completed Tasks

### DOC-1 - Business requirement and requirement analysis

- **Date:** 2026-10-08
- **Status:** Reviewed
- **Record type:** Retrospective
- **AI tool/model:** GitHub Copilot; model details not recorded
- **Task objective:** Produce assignment-aligned business requirements and a requirement analysis for the URL-shortener engineering assignment.
- **Inputs and context:** Assignment brief and project README.
- **Prompt:** Summary, not verbatim: create business requirement and requirement analysis Markdown documents for the assignment, keeping unspecified implementation decisions open.
- **AI contribution:** Drafted the business scope, outcomes, functional and quality requirements, acceptance checks, assumptions, and traceability to later design and delivery artifacts.
- **Engineer review:** Reviewed the content against the assignment and asked for clarification about simulated approval, stack selection, task sequencing, testing timing, and evidence of AI usage.
- **Edge cases or gaps found:**
  - The word “scalable” has no numeric traffic, latency, or availability target in the assignment.
  - The assignment does not prescribe a technology stack; proposed choices must not be described as stakeholder-approved.
  - Verification criteria should be defined before implementation, while tests are run during or after implementation.
  - No external stakeholder is available to provide actual approval.
- **Resulting changes:** Left technology choices open for engineering design; documented scalability as a design concern without claiming numeric guarantees; labeled approval as simulated; clarified testing timing; and identified AI usage evidence as a supporting artifact.
- **Validation:** Compared the documents with the assignment brief. Editor diagnostics reported no errors for the created Markdown files.
- **Related artifacts:** [Business requirement](01-business-requirement.md), [Requirement analysis](02-requirement-analysis.md)

## Future Tasks

Add a separate entry for each meaningful AI-assisted design, task breakdown, implementation, testing, or documentation task. Update its status as work progresses and record actual review and validation results before marking it validated.
