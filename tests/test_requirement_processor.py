import json
from pathlib import Path

import pytest

from requirement_processor.cli import analyze, main


@pytest.mark.parametrize(
    ("filename", "expected_scenario", "expected_tasks"),
    [
        ("greenfield.txt", "greenfield", {"T-101", "T-110", "T-111"}),
        ("brownfield.txt", "brownfield", {"T-112", "T-113"}),
        ("ambiguous.txt", "ambiguous", {"T-114"}),
    ],
)
def test_analyze_examples_returns_reviewable_scenario_draft(
    filename: str,
    expected_scenario: str,
    expected_tasks: set[str],
) -> None:
    requirement = (Path("examples") / filename).read_text(encoding="utf-8")

    result = analyze(requirement, filename)

    assert result["scenario"] == expected_scenario
    assert result["human_review"]["status"] == "pending"
    assert result["generation"]["live_ai_model_used"] is False
    assert expected_tasks <= {task["id"] for task in result["ordered_tasks"]}
    assert all("dependencies" in task for task in result["ordered_tasks"])
    assert isinstance(result["acceptance_checks"], list)


def test_analyze_cli_writes_json_draft_and_rejects_empty_input(tmp_path: Path) -> None:
    source = tmp_path / "requirement.txt"
    output = tmp_path / "nested" / "draft.json"
    source.write_text("Build a scalable URL shortener from scratch.", encoding="utf-8")

    assert main(["analyze", str(source), "--output", str(output)]) == 0
    draft = json.loads(output.read_text(encoding="utf-8"))
    assert draft["scenario"] == "greenfield"
    assert draft["human_review"]["status"] == "pending"

    source.write_text(" \n", encoding="utf-8")
    assert main(["analyze", str(source), "--output", str(output)]) == 2


def test_review_cli_records_human_acceptance_without_overwriting_draft(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    reviewed_path = tmp_path / "reviewed.json"
    draft_path.write_text(
        json.dumps(analyze("Build from scratch", str(draft_path))),
        encoding="utf-8",
    )

    assert main([
        "review",
        str(draft_path),
        "--decision",
        "accept",
        "--reviewer",
        "Candidate",
        "--notes",
        "Reviewed and accepted for the scenario.",
        "--output",
        str(reviewed_path),
    ]) == 0

    assert json.loads(draft_path.read_text(encoding="utf-8"))["human_review"]["status"] == "pending"
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    assert reviewed["human_review"]["decision"] == "accept"
    assert reviewed["human_review"]["reviewer"] == "Candidate"
    assert reviewed["human_review"]["notes"] == "Reviewed and accepted for the scenario."
