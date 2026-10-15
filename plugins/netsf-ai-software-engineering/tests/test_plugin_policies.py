"""Scope, project inference, Git context, Git risk and user-requested execution restrictions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from netsf_testkit import PLUGIN_ROOT, bridge_json, tree_digest
from scenarios import build

from netsf import readonly
from netsf.detect import detect, git_context
from netsf.guard import hook_output
from netsf.readonly import ALL, COMMIT, MODIFY, PUSH, apply_prompt, is_read_only_command
from netsf.risk import assess
from netsf.scope import assess_scope, infer_project

DEPLOYMENT_STACKS = {"stack.docker", "stack.kubernetes", "stack.nginx", "stack.ci-cd"}


# Scope: database ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("task", "decision", "value"),
    [
        ("I need an API to manage cells and equipment", "ask", "undecided"),
        ("Store the measurements history of each machine", "ask", "undecided"),
        ("Guardar el historial de pedidos", "ask", "undecided"),
        ("Create an API that stores orders in ClickHouse", "specified", "clickhouse"),
        ("Build a service on PostgreSQL for invoices", "specified", "postgresql"),
        (
            "An API that receives an Excel file, processes it and generates an output file",
            "none",
            "none",
        ),
        ("Convert uploaded CSV files to PDF reports", "none", "none"),
        ("An API to manage tickets without a database, it only works with files", "none", "none"),
        ("Add a health check endpoint", "not-applicable", "undecided"),
    ],
)
def test_database_scope(task: str, decision: str, value: str) -> None:
    scope = assess_scope(task)
    assert (scope.database, scope.database_value) == (decision, value), scope.database_reason
    asks = any("database" in q for q in scope.questions)
    assert asks is (decision == "ask")
    if decision == "ask":
        assert "ClickHouse" in scope.questions[0]


def test_existing_database_is_not_asked_again() -> None:
    scope = assess_scope("Add an endpoint to manage cells", detected_databases=["PostgreSQL"])
    assert scope.database == "specified" and scope.database_value == "postgresql"
    assert not scope.questions


# Scope: deployment ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("task", "in_scope", "target"),
    [
        ("Create an API for cells and equipment", False, "undecided"),
        ("Track the equipment of each production line", False, "undecided"),
        ("Build a data pipeline that loads sales into the warehouse", False, "undecided"),
        ("Deploy the service to Kubernetes", True, "kubernetes"),
        ("Containerise the app with Docker", True, "docker"),
        ("Deploy it to production", True, "undecided"),
        ("Despliega la API en RKE", True, "kubernetes"),
    ],
)
def test_deployment_scope(task: str, in_scope: bool, target: str) -> None:
    scope = assess_scope(task)
    assert (scope.deployment_in_scope, scope.deployment_target) == (in_scope, target)
    asks_target = any("target environment" in q for q in scope.questions)
    assert asks_target is (in_scope and target == "undecided")


def test_existing_deployment_is_known_but_not_in_scope() -> None:
    scope = assess_scope("Fix the cells endpoint", detected_deployment=["Kubernetes"])
    assert not scope.deployment_in_scope and scope.deployment_target == "kubernetes"


# Project-type inference ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("task", "details", "profile", "technology"),
    [
        ("API for cells", {"categories": ["api"], "technologies": []}, "backend-api", "custom"),
        (
            "Flask API",
            {"categories": ["api"], "technologies": ["flask"]},
            "backend-api",
            "python-flask",
        ),
        (
            "React dashboard",
            {"categories": ["frontend"], "technologies": ["react"]},
            "frontend",
            "react",
        ),
        (
            "React + FastAPI app",
            {"categories": ["frontend", "api"], "technologies": ["react", "fastapi"]},
            "fullstack",
            "react-fastapi",
        ),
        (
            "React + Flask app",
            {"categories": ["frontend", "api"], "technologies": ["react", "flask"]},
            "fullstack",
            "custom",
        ),
        (
            "Script that builds the weekly Excel report",
            {"categories": [], "technologies": []},
            "python-automation",
            "python",
        ),
        (
            "ETL that loads sales into the warehouse",
            {"categories": [], "technologies": []},
            "data-engineering",
            "python-data",
        ),
        ("Something", {}, "custom", "custom"),
    ],
)
def test_infer_project(task, details, profile, technology) -> None:
    inferred = infer_project(task, details)
    assert (inferred["profile"], inferred["technology"]) == (profile, technology)
    assert inferred["source"] == "request" and inferred["reasons"]


def test_empty_project_is_classified_from_the_request(tmp_path: Path) -> None:
    code, data = bridge_json(
        "context", "--path", str(tmp_path), "--task", "I need an API to manage cells and equipment"
    )
    assert code == 0
    assert data["project_type"]["profile"] == "backend-api"
    assert data["project_type"]["source"] == "request"
    assert data["scope"]["database"] == "ask"
    selected = {s["id"] for s in data["selected"]}
    assert not selected & DEPLOYMENT_STACKS
    assert "backend" in data["specialists"] and "devops" not in data["specialists"]


def test_empty_frontend_project(tmp_path: Path) -> None:
    _, data = bridge_json("context", "--path", str(tmp_path), "--task", "Build a React dashboard")
    assert (data["project_type"]["profile"], data["project_type"]["technology"]) == (
        "frontend",
        "react",
    )


def test_profile_override_is_still_available(tmp_path: Path) -> None:
    _, data = bridge_json(
        "context",
        "--path",
        str(tmp_path),
        "--task",
        "Build the service",
        "--profile",
        "microservice",
        "--technology",
        "python-flask",
    )
    assert data["project_type"]["source"] == "user override"
    assert data["project_type"]["profile"] == "microservice"


def test_existing_kubernetes_project_keeps_its_deployment_guides(tmp_path: Path) -> None:
    project = build(tmp_path, "kubernetes")
    _, data = bridge_json(
        "context", "--path", str(project), "--task", "Deploy service to Kubernetes"
    )
    assert data["scope"]["deployment_target"] == "kubernetes"
    assert "stack.kubernetes" in {s["id"] for s in data["selected"]}


def test_plan_shows_scope_questions_and_changes_nothing(tmp_path: Path) -> None:
    before = tree_digest(tmp_path)
    code, plan = bridge_json(
        "plan", "--path", str(tmp_path), "--task", "I need an API to manage cells and equipment"
    )
    assert code == 0 and plan["dry_run"] and not plan["modifies_files"]
    assert plan["scope"]["database"] == "ask"
    assert not plan["scope"]["deployment_in_scope"]
    assert any("ClickHouse" in q for q in plan["questions_for_user"])
    assert tree_digest(tmp_path) == before and not (tmp_path / ".git").exists()


# Git context -------------------------------------------------------------------------------
def test_git_context_own_and_parent_repository(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    child = tmp_path / "child"
    child.mkdir()
    own = git_context(tmp_path)
    assert own["own_repository"] and not own["parent_repository"]
    parent = git_context(child)
    assert parent["parent_repository"] and not parent["own_repository"]
    assert parent["repository_root"] == str(tmp_path.resolve())
    assert detect(child).git == parent


def test_plan_reports_the_parent_repository(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    child = tmp_path / "child"
    child.mkdir()
    _, plan = bridge_json("plan", "--path", str(child), "--task", "Fix a typo in the README")
    assert plan["git"]["parent_repository"]
    assert "not used for this project" in plan["git"]["note"]
    # Informational only: a task that does not involve Git must not stop for a Git question.
    assert not any("git init" in q for q in plan["questions_for_user"])
    _, git_plan = bridge_json("plan", "--path", str(child), "--task", "Commit the changes")
    assert any("git init" in q for q in git_plan["questions_for_user"])


# Git risk -------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "task",
    [
        "Commit the changes",
        "Initialize git and push to the remote",
        "git push origin main",
        "Create a release tag",
        "Haz commit de los cambios",
    ],
)
def test_git_actions_need_approval(task: str) -> None:
    risk = assess(task)
    assert risk.level in ("HIGH", "CRITICAL") and risk.approval_required, risk.reasons


def test_push_notifications_are_not_git() -> None:
    assert assess("Send push notifications to the operators").level == "MEDIUM"


# Execution restrictions: phrase handling --------------------------------------------------------
@pytest.mark.parametrize(
    "prompt",
    [
        "Do a dry run: analyse how to add the endpoint",
        "dry-run only, please",
        "Analysis only, do not modify anything",
        "Plan only",
        "Don't change any files, just tell me what you would do",
        "Solo análisis, no modifiques nada",
        "Hazlo sin modificar el proyecto",
        "/netsf-ai-software-engineering:plan add a region column",
    ],
)
def test_full_read_only_activation(prompt: str) -> None:
    prohibitions, trigger, released = apply_prompt(prompt, frozenset())
    assert prohibitions == ALL and trigger and not released


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Fix the bug but do not commit", {COMMIT}),
        ("Implement it and don't push", {PUSH}),
        ("Do not create files yet", {MODIFY}),
        ("No hagas commit ni push: no hagas push", {COMMIT, PUSH}),
    ],
)
def test_partial_restrictions(prompt: str, expected: set[str]) -> None:
    assert apply_prompt(prompt, frozenset())[0] == expected


@pytest.mark.parametrize(
    "prompt",
    [
        "Add a --dry-run option to the export command",
        "Implement a dry-run flag for the migration tool",
        "Write a function that does not modify its input",
        "Create the API for cells",
    ],
)
def test_normal_requests_do_not_activate(prompt: str) -> None:
    assert apply_prompt(prompt, frozenset())[0] == frozenset()


@pytest.mark.parametrize(
    "prompt",
    [
        "Exit dry-run and implement it",
        "You can modify the files now",
        "Apply the plan",
        "Ya puedes modificar",
        "Aplica el plan",
    ],
)
def test_release(prompt: str) -> None:
    prohibitions, _, released = apply_prompt(prompt, ALL)
    assert released and prohibitions == frozenset()


@pytest.mark.parametrize(
    "prompt", ["Do not exit dry-run yet", "No, you can't modify yet", "Explain the plan again"]
)
def test_restriction_is_sticky(prompt: str) -> None:
    prohibitions, _, released = apply_prompt(prompt, ALL)
    assert not released and prohibitions == ALL


def test_release_with_a_new_restriction() -> None:
    prohibitions, _, released = apply_prompt("You can modify now, but do not push", ALL)
    assert released and prohibitions == {PUSH}


# Execution restrictions: enforcement ------------------------------------------------------------
@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --oneline -5 | head -3",
        "git diff HEAD~1",
        "ls -la && cat README.md",
        "grep -rn TODO src",
        "Get-ChildItem -Recurse | Select-String TODO",
        'python "C:/p/scripts/netsf_bridge.py" plan --task "x"',
        "ai-project context --task x --json",
        "ai-project update --dry-run",
        "find . -name '*.py'",
        "git branch -a",
    ],
)
def test_read_only_commands(command: str) -> None:
    assert is_read_only_command(command), command


@pytest.mark.parametrize(
    "command",
    [
        "mkdir src",
        "echo x > app.py",
        "cat a >> b",
        "touch app.py",
        "rm build/x",
        "sed -i s/a/b/ f",
        "python script.py",
        "pytest -q",
        "git checkout -b feature",
        "git branch feature",
        "git stash",
        "find . -delete",
        "find . -name x -fprintf out.txt %p",
        "ls $(rm -rf x)",
        "ai-project init .",
        "ai-project context --rebuild-graph",
        "npm install",
        "New-Item app.py",
    ],
)
def test_modifying_commands_are_not_read_only(command: str) -> None:
    assert not is_read_only_command(command), command


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin-data"))
    return tmp_path / "plugin-data" / "readonly"


def _prompt(text: str, session: str = "s1") -> dict:
    return {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": text}


def _tool(tool: str, session: str = "s1", **tool_input) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "tool_name": tool,
        "tool_input": tool_input,
    }


def _decision(event: dict) -> str:
    out = hook_output(json.dumps(event))
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "none"


def test_dry_run_denies_changes_and_allows_reading(state_dir: Path) -> None:
    context = json.loads(readonly.prompt_hook(_prompt("Dry run: plan the cells API")))
    assert "restriction ON" in context["hookSpecificOutput"]["additionalContext"]
    assert (state_dir / "s1.json").is_file()
    assert _decision(_tool("Write", file_path="src/app.py", content="x")) == "deny"
    assert _decision(_tool("Edit", file_path="src/app.py")) == "deny"
    assert _decision(_tool("Bash", command="mkdir src")) == "deny"
    assert _decision(_tool("Bash", command="pip install fastapi")) == "deny"
    assert _decision(_tool("Bash", command="git init")) == "deny"
    assert _decision(_tool("Bash", command="git status")) == "none"
    assert _decision(_tool("Read", file_path="src/app.py")) == "none"
    assert _decision(_tool("Write", session="other", file_path="a.py", content="x")) == "none"


def test_release_restores_normal_flow(state_dir: Path) -> None:
    readonly.prompt_hook(_prompt("analysis only"))
    off = json.loads(readonly.prompt_hook(_prompt("exit dry-run, implement it")))
    assert "OFF" in off["hookSpecificOutput"]["additionalContext"]
    assert not (state_dir / "s1.json").exists()
    assert _decision(_tool("Write", file_path="src/app.py", content="x")) == "none"


def test_partial_restriction_only_blocks_that_action(state_dir: Path) -> None:
    readonly.prompt_hook(_prompt("Implement the endpoint but do not push"))
    assert _decision(_tool("Write", file_path="src/app.py", content="x")) == "none"
    assert _decision(_tool("Bash", command="git push origin feature")) == "deny"


def test_plan_permission_mode_is_read_only(state_dir: Path) -> None:
    event = _tool("Edit", file_path="src/app.py")
    event["permission_mode"] = "plan"
    assert _decision(event) == "deny"


def test_unreadable_state_asks(state_dir: Path) -> None:
    state_dir.mkdir(parents=True)
    (state_dir / "s1.json").write_text("{not json", encoding="utf-8")
    assert _decision(_tool("Write", file_path="a.py", content="x")) == "ask"


def test_hooks_end_to_end_as_processes(tmp_path: Path) -> None:
    script = PLUGIN_ROOT / "scripts" / "netsf_guard.py"
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path / "data"))

    def call(event: dict) -> subprocess.CompletedProcess:
        return subprocess.run(  # noqa: S603 - fixed argv
            [sys.executable, str(script)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=env,
        )

    prompt = call(_prompt("Solo análisis: no modifiques nada", session="p1"))
    assert prompt.returncode == 0 and "restriction ON" in prompt.stdout
    write = call(_tool("Write", session="p1", file_path="a.py", content="x"))
    assert json.loads(write.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    release = call(_prompt("ya puedes modificar", session="p1"))
    assert "OFF" in release.stdout
    again = call(_tool("Write", session="p1", file_path="a.py", content="x"))
    assert again.returncode == 0 and again.stdout.strip() == ""
    silent = call(_prompt("Create the API", session="p2"))
    assert silent.returncode == 0 and silent.stdout.strip() == ""
