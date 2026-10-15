"""Scope, decision and code-hygiene policies: init defaults, routing, knowledge and doctor."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import run

from ai_project.catalog import Catalog, Selection, deployment_in_scope
from ai_project.code_hygiene import classify, scan_comments
from ai_project.context_cmd import ContextOptions, build_package
from ai_project.paths import kit_root

KIT = kit_root()
DEPLOYMENT_STACKS = {"docker", "kubernetes", "nginx", "ci-cd", "linux"}


def _lock(root: Path) -> dict:
    return json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))


def _stacks(root: Path) -> set[str]:
    return {p.name for p in (root / ".ai/stacks").iterdir()}


# Init defaults ---------------------------------------------------------------------------
def test_database_and_deployment_default_to_undecided(init_project) -> None:
    root = init_project("cells-api")
    selection = _lock(root)["selection"]
    assert selection["database"] == "undecided" and selection["deployment"] == "undecided"
    assert not _stacks(root) & (DEPLOYMENT_STACKS | {"postgresql", "clickhouse"})
    assert not (root / "deploy").exists()
    agents = (root / "AGENTS.md").read_text("utf-8")
    assert "Not decided - ask before adding persistence" in agents
    assert "Not in scope yet" in agents
    assert "deliverables are Docker images deployed to" not in agents


def test_frontend_has_no_database_by_default(init_project) -> None:
    assert _lock(init_project("ui", profile="frontend"))["selection"]["database"] == "none"


def test_explicit_deployment_brings_deployment_content(init_project) -> None:
    root = init_project("svc", "--technology", "python-flask", "--deployment", "kubernetes")
    assert {"docker", "kubernetes", "nginx", "ci-cd"} <= _stacks(root)
    assert (root / "deploy/.gitkeep").is_file()


def test_explicit_database_is_respected(init_project) -> None:
    root = init_project("kpi", "--database", "clickhouse")
    assert _lock(root)["selection"]["database"] == "clickhouse"
    assert "clickhouse" in _stacks(root)


def test_serving_stack_follows_deployment_scope() -> None:
    catalog = Catalog(KIT)
    assert deployment_in_scope("kubernetes") and deployment_in_scope("docker")
    assert not deployment_in_scope("undecided") and not deployment_in_scope("none")
    for deployment, expected in (("undecided", False), ("docker", True)):
        selection = Selection("backend-api", "python-fastapi", "none", deployment, ())
        resolved = catalog.resolve(selection)
        assert ("nginx" in resolved.stacks) is expected
        assert any(d == "deploy" for d in resolved.structure) is expected


# Context simulation ------------------------------------------------------------------------
def _stack_ids(task: str, **kw) -> set[str]:
    pkg = build_package(ContextOptions(task=task, profile="backend-api", **kw), Catalog(KIT))
    return {i.id for i in pkg.by_kind("stack")}


def test_simulation_without_deployment_loads_no_deployment_guides() -> None:
    assert not _stack_ids("Create an API for cells and equipment") & DEPLOYMENT_STACKS


def test_simulation_with_deployment_loads_its_guides() -> None:
    assert "kubernetes" in _stack_ids("Deploy service to Kubernetes", deployment="kubernetes")
    result = run(
        "context",
        "--profile",
        "backend-api",
        "--deployment",
        "kubernetes",
        "--task",
        "Deploy service to Kubernetes",
        "--json",
    )
    assert result.code == 0
    assert "kubernetes" in {s["id"] for s in json.loads(result.out)["selected_stacks"]}


def test_scope_rules_are_routed_for_new_api_work() -> None:
    pkg = build_package(
        ContextOptions(task="Create an API for cells and equipment", profile="backend-api"),
        Catalog(KIT),
    )
    selected = {item["id"]: item for item in pkg.to_dict()["selected"]}
    concepts = selected["rule.architecture"]["concepts"]
    assert "concept.architecture.scope-and-decisions" in concepts


# Knowledge -----------------------------------------------------------------------------------
def _read(rel: str) -> str:
    return (KIT / rel).read_text("utf-8")


@pytest.mark.parametrize(
    ("rel", "ids"),
    [
        ("rules/architecture.md", [f"ARCH-{n}" for n in range(42, 48)]),
        ("rules/coding.md", ["CODE-45", "CODE-46", "CODE-47"]),
        ("rules/documentation.md", ["DOC-30", "DOC-31", "DOC-32"]),
    ],
)
def test_policy_rules_exist(rel: str, ids: list[str]) -> None:
    text = _read(rel)
    for rule_id in ids:
        assert f"**{rule_id}**" in text, rule_id


def test_rule_ids_are_unique() -> None:
    for rule in (KIT / "rules").glob("*.md"):
        found = re.findall(r"\*\*([A-Z]+-\d+)\*\*", rule.read_text("utf-8"))
        assert len(found) == len(set(found)), rule.name


def test_deployment_rules_are_scoped() -> None:
    architecture = _read("rules/architecture.md")
    section = architecture.split("## Deployment target", 1)[1].split("\n## ", 1)[0]
    assert "Applies when deployment is in scope" in section
    assert "only when deployment is requested or required" in architecture


def test_knowledge_does_not_contradict_the_policies() -> None:
    master = _read("agents/00-master.md")
    assert "Adding a new major dependency, framework" not in master
    assert "ARCH-42" in master and "dry runs change nothing" in master
    workflow = _read("workflows/new-project.md")
    assert "Create the project on git.netsf.fr" not in workflow
    assert "The skeleton is deployed to Kubernetes (RKE) Staging" not in workflow
    assert "only after approval" in workflow and "only when deployment is in scope" in workflow
    assert "ask which one to use" in _read("agents/03-database.md")
    assert "ARCH-46" in _read("agents/12-devops.md")


def test_every_rule_section_has_routing_metadata() -> None:
    sections = json.loads(_read("catalog/context.json"))["rules"]
    for rule in (KIT / "rules").glob("*.md"):
        headings = re.findall(r"^## (.+)$", rule.read_text("utf-8"), re.MULTILINE)
        assert set(headings) <= set(sections[rule.stem]["sections"]), rule.name


# Code hygiene ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "comment",
    [
        "Updated after the meeting with the client",
        "Client requested this behaviour",
        "Previously this returned a list",
        "New implementation of the parser",
        "Changed in v1.2",
        "fallback: direct (v1.1) routing",
    ],
)
def test_history_comments_are_detected(comment: str) -> None:
    assert classify(comment) == "history"


@pytest.mark.parametrize(
    "comment", ["Calcula el total de los elementos", "La función devuelve el total"]
)
def test_non_english_comments_are_detected(comment: str) -> None:
    assert classify(comment) == "non-english"


@pytest.mark.parametrize(
    "comment",
    [
        "Validate that the equipment belongs to the selected cell.",
        "Retry up to 3 times (see ADR-0004).",
        "Supports Python 3.9 and OpenAPI 3.1.",
        "Use the same value as before the retry.",
        "ai-kit: allow-comment Calcula el total",
    ],
)
def test_normal_comments_are_not_flagged(comment: str) -> None:
    assert classify(comment) is None


def test_scan_reads_comments_and_docstrings_not_strings(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        '"""Calcula el total de los elementos."""\n'
        'PATTERNS = ["que para los", "previously"]  # Load the patterns.\n'
        "def total(items):\n"
        "    # Updated after the meeting\n"
        "    return sum(items)\n",
        encoding="utf-8",
    )
    (tmp_path / "ui.ts").write_text("// Previously used a class\nconst x = 1;\n", encoding="utf-8")
    findings, files = scan_comments(tmp_path)
    assert files == 2
    assert {(f.path, f.line, f.kind) for f in findings} == {
        ("app.py", 1, "non-english"),
        ("app.py", 4, "history"),
        ("ui.ts", 1, "history"),
    }


def test_kit_and_plugin_code_follow_the_comment_rules() -> None:
    for target in (
        "cli/ai_project",
        "tests",
        "plugins/netsf-ai-software-engineering/scripts",
        "plugins/netsf-ai-software-engineering/tests",
    ):
        path = KIT / target
        if path.is_dir():
            findings, _ = scan_comments(path)
            assert findings == [], [f"{target}/{f.path}:{f.line} {f.kind}" for f in findings]


# Doctor --------------------------------------------------------------------------------------
def _doctor_lines(root: Path) -> str:
    return run("doctor", "--path", str(root)).out


def test_doctor_warns_about_history_comments(init_project) -> None:
    root = init_project("hygiene-app")
    (root / "src" / "app.py").parent.mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("# Changed after the meeting\nX = 1\n", encoding="utf-8")
    out = _doctor_lines(root)
    assert "Code comments (English, current behaviour)" in out and "src/app.py:1 (history)" in out


def test_doctor_reports_parent_repository_and_ci_scope(init_project, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    root = init_project("child-app")
    out = _doctor_lines(root)
    assert "no repository of its own: inside the parent repository" in out
    assert "not configured (deployment not in scope)" in out


def test_json_and_status_codes_classify_as_api_work() -> None:
    task = "Retrieve a cell by ID: return it as JSON, or 404 when it does not exist"
    pkg = build_package(ContextOptions(task=task, profile="backend-api"), Catalog(KIT))
    assert "api" in pkg.to_dict()["classification"]
    assert "02-backend" in {a["id"] for a in pkg.to_dict()["selected_agents"]}
