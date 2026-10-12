"""Command-line interface for creating and recording requirement drafts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASKS: dict[str, dict[str, Any]] = {
    "greenfield": {
        "summary": "Plan the baseline URL-shortener service from the approved assignment documents.",
        "functional_requirements": [
            "Create short links from valid absolute HTTP(S) destination URLs.",
            "Persist short-code mappings in PostgreSQL.",
            "Redirect known codes and return 404 only after confirming an unknown code.",
            "Record click events asynchronously and expose aggregate link analytics.",
        ],
        "quality_requirements": [
            "Use Python 3.11+, FastAPI, async SQLAlchemy 2.x, PostgreSQL, and Redis.",
            "Keep click processing idempotent and disclose the best-effort publication window.",
            "Measure Q-6/Q-7; do not claim performance acceptance without benchmark evidence.",
        ],
        "assumptions": [
            "The existing engineering design is the stack and API contract source for this scenario.",
            "Custom aliases, expiration, authentication, and collection of IP/user-agent data are out of baseline scope.",
        ],
        "open_questions": [
            "Are additional URL-validation, authentication, rate-limiting, or abuse controls required before deployment?",
            "What representative environment and separate load generator will be used for formal Q-6/Q-7 acceptance?",
        ],
        "risks": [
            "Local benchmark results do not establish deployed capacity or satisfy Q-6/Q-7.",
            "A process failure before background event publication can lose a click.",
        ],
        "tasks": [
            ("T-101", "Define baseline requirements and acceptance criteria", []),
            ("T-102", "Set up async application and configuration", ["T-101"]),
            ("T-103", "Create link and click-event schema", ["T-102"]),
            ("T-104", "Implement link creation and persistence", ["T-103"]),
            ("T-105", "Implement cached redirects and database fallback", ["T-104"]),
            ("T-106", "Implement Redis Stream analytics pipeline", ["T-103", "T-105"]),
            ("T-107", "Implement analytics API", ["T-103", "T-106"]),
            ("T-108", "Implement security, reliability, and observability controls", ["T-104", "T-105", "T-106", "T-107"]),
            ("T-109", "Add automated and integration tests", ["T-104", "T-105", "T-106", "T-107", "T-108"]),
            ("T-110", "Validate capacity and latency targets", ["T-108", "T-109"]),
            ("T-111", "Document and sign off engineering deliverables", ["T-109", "T-110"]),
        ],
        "tests": [
            "python -m pytest -q",
            "Run the opt-in PostgreSQL/Redis integration suite after configuring services and migrations.",
            "Measure warm- and cold-cache load behavior; report actual rates, client P95s, event drain, and cleanup.",
        ],
        "acceptance_checks": [
            "Create, persist, redirect, and retrieve analytics for a short link using the documented contracts.",
            "Confirm invalid URLs, unknown codes, and dependency failures return documented errors.",
            "Record benchmark evidence and mark Q-6/Q-7 accepted only if measured thresholds pass.",
        ],
    },
    "brownfield": {
        "summary": "Assess an optional custom-alias enhancement to the existing URL-shortener without silently approving it.",
        "functional_requirements": [
            "Keep generated codes working when a caller omits a custom alias.",
            "If approved, accept an optional alias when creating a link and preserve existing redirects and analytics.",
        ],
        "quality_requirements": [
            "Preserve backward compatibility for existing API clients.",
            "Enforce alias uniqueness safely under concurrent creation requests.",
            "Document and test validation and duplicate-alias behavior.",
        ],
        "assumptions": [
            "Alias support is a proposed enhancement, not part of the currently accepted baseline.",
            "No expiration behavior is included in this request.",
        ],
        "open_questions": [
            "What characters, length bounds, case sensitivity, and reserved aliases are allowed?",
            "What response should a duplicate alias produce?",
            "Is a database migration required, or can the existing unique code column support aliases?",
        ],
        "risks": [
            "Unapproved alias rules could create incompatible API behavior.",
            "A migration or uniqueness implementation could invalidate existing mappings if not tested against current data.",
        ],
        "tasks": [
            ("T-101", "Approve the alias contract and acceptance criteria", []),
            ("T-112", "Define alias requirements and reserved values", ["T-101"]),
            ("T-113", "Implement approved alias behavior", ["T-112", "T-103"]),
            ("T-109", "Add compatibility, validation, and integration tests", ["T-113"]),
            ("T-111", "Document the approved behavior and migration", ["T-109"]),
        ],
        "tests": [
            "Run focused creation and redirect tests plus the full python -m pytest -q suite.",
            "Test omitted aliases, accepted aliases, malformed/reserved aliases, and duplicate aliases.",
            "Apply and inspect any migration against both a clean schema and the current schema.",
        ],
        "acceptance_checks": [
            "Existing request bodies without aliases continue to create generated codes.",
            "Only human-approved alias rules are accepted and persisted.",
            "Existing links remain resolvable and concurrent duplicates follow the documented conflict contract.",
        ],
    },
    "ambiguous": {
        "summary": "Clarify what “make tracking secure and safe” means before proposing implementation changes.",
        "functional_requirements": [],
        "quality_requirements": [
            "Do not add tracking fields or security controls until their requirements and trade-offs are approved.",
            "Keep the existing minimal click-event design and best-effort delivery limitation visible.",
        ],
        "assumptions": [
            "The current event contains an event ID, link identity, and UTC click time.",
            "The baseline does not collect IP addresses or user-agent values.",
            "The existing analytics pipeline uses Redis Streams and an asynchronous worker.",
        ],
        "open_questions": [
            "Which threat or failure does “secure and safe” refer to: privacy, data integrity, access, abuse, retention, or delivery reliability?",
            "Which event fields are necessary, and who may access analytics?",
            "What retention/deletion policy and acceptable event loss or delay are required?",
            "Will the service be exposed publicly, and are authentication, rate limits, or abuse controls required?",
        ],
        "risks": [
            "Guessing the requirement could add unnecessary personal-data collection or controls that do not address the actual threat.",
            "The current best-effort publication path can lose a click if the API process fails before publishing.",
        ],
        "tasks": [
            ("T-101", "Clarify the security and tracking requirement", []),
            ("T-106", "Review the current analytics pipeline and delivery guarantees", ["T-101"]),
            ("T-107", "Review the analytics API and access surface", ["T-101"]),
            ("T-114", "Approve privacy, retention, access, and durability requirements", ["T-101", "T-106", "T-107"]),
            ("T-108", "Implement only approved security and reliability controls", ["T-114"]),
            ("T-109", "Verify approved behavior with tests and failure injection", ["T-108"]),
            ("T-111", "Document decisions, evidence, and remaining limitations", ["T-109"]),
        ],
        "tests": [
            "Inspect click_events schema, Redis Stream fields, API responses, logs, and metric labels for unapproved data.",
            "Run analytics integration tests against PostgreSQL and Redis.",
            "If durability changes are approved, inject failures and verify recovery and idempotency.",
        ],
        "acceptance_checks": [
            "Human decisions explicitly define required data, access, retention, and delivery expectations.",
            "No unapproved personal data is added to storage, streams, logs, API responses, or metrics.",
            "Only approved behavior is implemented and verified against the clarified requirement.",
        ],
    },
}

_TASK_DETAILS = {
    "T-101": ("Define requirements and acceptance criteria; separate confirmed scope from assumptions and open decisions.", "Use AI to trace statements to source requirements and identify gaps without silently deciding them.", "Human review confirms scope, dependencies, and acceptance checks against the source documents."),
    "T-102": ("Set up the asynchronous application, configuration, and resource lifecycle.", "Use AI to draft a minimal scaffold that follows project conventions.", "Start the service and verify health, readiness, and explicit configuration failures."),
    "T-103": ("Define the PostgreSQL models, constraints, indexes, and reversible migration.", "Ask AI to derive schema and constraints from the engineering design.", "Apply the migration and inspect tables, indexes, and constraint behavior."),
    "T-104": ("Implement validated short-link creation and durable persistence.", "Use AI to draft typed request handling and focused contract tests.", "Verify valid/invalid inputs, response contract, persistence, and cache behavior."),
    "T-105": ("Implement redirect lookup, cache fallback, and documented not-found behavior.", "Ask AI to enumerate cache and database failure paths and tests.", "Verify 302/404/503 behavior with cache and database failure cases."),
    "T-106": ("Implement asynchronous click-event transport and idempotent worker processing.", "Use AI to draft event processing and failure-injection tests.", "Verify duplicate delivery, commit-before-ack, pending recovery, and disclosed loss window."),
    "T-107": ("Expose the documented aggregate analytics response.", "Use AI to draft a typed response and contract tests.", "Verify response shape, unknown-link behavior, and eventual aggregate updates."),
    "T-108": ("Apply approved security, reliability, and observability controls.", "Use AI to inspect relevant code paths and suggest targeted tests.", "Inspect collected fields, error handling, privacy, and metric cardinality."),
    "T-109": ("Add focused regression and cross-service integration tests.", "Use AI to derive test cases from requirements and failure modes.", "Run the regular suite and configured integration suite; inspect failures."),
    "T-110": ("Measure target request rates, latency, errors, and analytics drain.", "Use AI to plan reproducible runs and interpret actual measurements.", "Run the benchmark and report measured Q-6/Q-7 results without extrapolation."),
    "T-111": ("Document implementation, setup, validation, decisions, risks, and limitations.", "Use AI to draft documentation from verified code and captured test output.", "Follow clean setup instructions and verify claims against code and evidence."),
    "T-112": ("Define and approve alias rules before implementation.", "Use AI to identify product decisions and compatibility impacts.", "Record human approval of syntax, bounds, reserved words, and duplicate behavior."),
    "T-113": ("Implement only the approved alias behavior and any required migration.", "Use AI to trace impacted schemas, routes, storage, and tests.", "Verify compatibility, uniqueness, migration safety, and redirect behavior."),
    "T-114": ("Clarify and approve tracking privacy, access, retention, and durability requirements.", "Use AI to organize interpretations, risks, and focused questions.", "Record explicit human decisions; leave unresolved controls unimplemented."),
}


def _classify(requirement: str) -> str:
    text = requirement.casefold()
    if any(term in text for term in ("secure and safe", "make tracking", "unclear", "ambiguous")):
        return "ambiguous"
    if any(term in text for term in ("custom alias", "add alias", "brownfield", "existing codebase")):
        return "brownfield"
    if any(term in text for term in ("from scratch", "greenfield", "build a scalable url shortener")):
        return "greenfield"
    return "ambiguous"


def _task_record(task_id: str, title: str, dependencies: list[str]) -> dict[str, Any]:
    description, ai_point, verification = _TASK_DETAILS[task_id]
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "dependencies": dependencies,
        "ai_assistance_point": ai_point,
        "human_validation": verification,
    }


def analyze(requirement: str, source: str) -> dict[str, Any]:
    if not requirement.strip():
        raise ValueError("requirement input is empty")

    scenario = _classify(requirement)
    template = TASKS[scenario]
    task_list = [
        _task_record(task_id, title, dependencies)
        for task_id, title, dependencies in template["tasks"]
    ]
    return {
        "schema_version": "1.0",
        "scenario": scenario,
        "classification_note": (
            "Scenario is inferred by simple local keyword rules and must be confirmed by a human."
        ),
        "source_file": source,
        "requirement": requirement.strip(),
        "summary": template["summary"],
        "functional_requirements": template["functional_requirements"],
        "quality_requirements": template["quality_requirements"],
        "assumptions": template["assumptions"],
        "open_questions": template["open_questions"],
        "risks": template["risks"],
        "ordered_tasks": task_list,
        "tests": template["tests"],
        "acceptance_checks": template["acceptance_checks"],
        "generation": {
            "method": "local scenario template",
            "live_ai_model_used": False,
            "notice": "This CLI structures a draft; it does not call an AI model or make approval decisions.",
        },
        "human_review": {
            "status": "pending",
            "decision": None,
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        },
    }


def _write_json(data: dict[str, Any], destination: Path, source: Path) -> None:
    if destination.resolve() == source.resolve():
        raise ValueError("output path must not overwrite the input file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _analyze_command(args: argparse.Namespace) -> None:
    source = Path(args.input)
    requirement = source.read_text(encoding="utf-8")
    result = analyze(requirement, str(source))
    _write_json(result, Path(args.output), source)
    print(f"Draft written to {args.output}; human review is pending.")


def _review_command(args: argparse.Namespace) -> None:
    source = Path(args.draft)
    draft = json.loads(source.read_text(encoding="utf-8"))
    review = draft.get("human_review")
    if not isinstance(review, dict) or review.get("status") != "pending":
        raise ValueError("draft must have human_review.status set to 'pending'")
    if Path(args.output).resolve() == source.resolve():
        raise ValueError("review output must not overwrite the draft")

    review.update({
        "status": "reviewed",
        "decision": args.decision,
        "reviewer": args.reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "notes": args.notes,
    })
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Reviewed draft written to {args.output} with decision '{args.decision}'.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m requirement_processor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="create a structured requirement draft")
    analyze_parser.add_argument("input", help="path to a UTF-8 requirement text file")
    analyze_parser.add_argument("--output", required=True, help="path for the JSON draft")
    analyze_parser.set_defaults(handler=_analyze_command)

    review_parser = subparsers.add_parser("review", help="record a human decision on a draft")
    review_parser.add_argument("draft", help="path to the JSON draft")
    review_parser.add_argument("--decision", choices=("accept", "reject"), required=True)
    review_parser.add_argument("--reviewer", required=True, help="human reviewer name or role")
    review_parser.add_argument("--notes", default="", help="review notes, including requested refinements")
    review_parser.add_argument("--output", required=True, help="path for the reviewed JSON record")
    review_parser.set_defaults(handler=_review_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"requirement_processor: {exc}", file=sys.stderr)
        return 2
    return 0
