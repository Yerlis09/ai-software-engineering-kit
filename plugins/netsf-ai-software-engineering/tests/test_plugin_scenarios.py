"""Integration scenarios: detection, routing, unnecessary-context avoidance, plans, impact."""

from __future__ import annotations

from pathlib import Path

import pytest
from netsf_testkit import bridge_json, run_bridge, tree_digest
from netsf_testkit import kit_project as kit_project  # pytest fixture
from scenarios import SCENARIOS, build

from netsf.detect import detect, kit_selection


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_detection(tmp_path: Path, name: str) -> None:
    project = build(tmp_path, name)
    det = detect(project)
    assert det.mode == "existing"
    expect = SCENARIOS[name]["expect"]
    for category in ("frameworks", "databases", "deployment", "libraries"):
        for value in expect.get(category, []):
            finding = det.findings[category][value]
            assert finding.confidence >= 0.5 and finding.evidence, (name, category, value)
    if "profile" in expect:
        assert kit_selection(det)["profile"] == expect["profile"]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_routing_selects_only_relevant_specialists(tmp_path: Path, name: str) -> None:
    project = build(tmp_path, name)
    for task, must, must_not in SCENARIOS[name]["tasks"]:
        code, data = bridge_json("context", "--path", str(project), "--task", task)
        assert code == 0, data
        chosen = set(data["specialists"])
        assert must <= chosen, (name, task, chosen)
        assert not (must_not & chosen), (name, task, chosen)
        assert "context-optimizer" not in chosen  # agent 15: never for normal tasks


def test_fastapi_task_avoids_unrelated_stacks(tmp_path: Path) -> None:
    project = build(tmp_path, "fastapi")
    _, data = bridge_json(
        "context", "--path", str(project), "--task", "Create a FastAPI endpoint to retrieve cells"
    )
    stacks = {s["id"] for s in data["selected"] if s["kind"] == "stack"}
    assert "stack.fastapi" in stacks
    assert not stacks & {"stack.react", "stack.angular", "stack.kubernetes"}


def test_context_optimizer_only_for_optimisation_tasks(tmp_path: Path) -> None:
    project = build(tmp_path, "fastapi")
    _, data = bridge_json(
        "context", "--path", str(project), "--task", "Improve context routing to reduce tokens"
    )
    assert "context-optimizer" in data["specialists"]


def test_new_project_mode(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# idea\n", encoding="utf-8")
    det = detect(tmp_path)
    assert det.mode == "new"


def test_kit_project_mode(kit_project: Path) -> None:
    assert detect(kit_project).mode == "kit"


def test_detection_is_bounded_and_skips_vendor_dirs(tmp_path: Path, monkeypatch) -> None:
    from netsf import detect as detect_module

    project = build(tmp_path, "frontend")
    vendor = project / "node_modules" / "react"
    vendor.mkdir(parents=True)
    (vendor / "package.json").write_text('{"dependencies": {"express": "1"}}', encoding="utf-8")
    det = detect(project)
    assert "Express" not in det.values("frameworks")
    monkeypatch.setattr(detect_module, "MAX_ENTRIES", 3)
    assert detect(project).truncated


def test_uncertain_findings_are_reported_as_uncertain(tmp_path: Path) -> None:
    (tmp_path / "notes.sql").write_text("select 1;\n", encoding="utf-8")
    (tmp_path / "x.py").write_text("print(1)\n", encoding="utf-8")
    data = detect(tmp_path).to_dict()
    assert all(f["evidence"] for findings in data["findings"].values() for f in findings)


def test_plan_never_modifies_files(tmp_path: Path) -> None:
    project = build(tmp_path, "fastapi")
    before = tree_digest(project)
    code, text = run_bridge(
        "plan",
        "--path",
        str(project),
        "--task",
        "Add validation to the cells endpoint",
        "--change",
        "app/api/cells.py",
    )
    assert code == 0 and "dry run" in text.lower()
    assert tree_digest(project) == before


def test_plan_impact_analysis_on_existing_project(tmp_path: Path) -> None:
    project = build(tmp_path, "fastapi")
    _, plan = bridge_json(
        "plan",
        "--path",
        str(project),
        "--task",
        "Change the cells endpoint response",
        "--change",
        "app/api/cells.py",
    )
    refs = plan["impact"]["references"]["app/api/cells.py"]
    assert "app/main.py" in refs and "tests/test_cells.py" in refs
    assert "tests/test_cells.py" in plan["impact"]["affected_tests"]
    assert plan["project"]["mode"] == "existing"
    assert "Keep the existing architecture" in plan["architecture"]


def test_high_risk_plan_requires_approval(tmp_path: Path) -> None:
    project = build(tmp_path, "python_backend")
    _, plan = bridge_json(
        "plan",
        "--path",
        str(project),
        "--task",
        "Add a column to the invoices table with a migration",
    )
    assert plan["risk"]["level"] == "HIGH" and plan["approval_required"] is True


def test_no_overengineering_for_a_simple_new_api(tmp_path: Path) -> None:
    _, plan = bridge_json(
        "plan", "--path", str(tmp_path), "--task", "Create an API that returns three fields"
    )
    assert plan["project"]["mode"] == "new"
    guidance = plan["architecture"].lower()
    assert "simple modular" in guidance and "no microservices" in guidance
    assert "devops" not in plan["specialists"] and "context-optimizer" not in plan["specialists"]
    assert plan["risk"]["level"] in ("LOW", "MEDIUM")
