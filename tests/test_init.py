from __future__ import annotations

import json
from pathlib import Path

from conftest import run

from ai_project.lockfile import content_hash


def test_non_interactive_backend_project(init_project) -> None:
    root = init_project(
        "billing-api",
        "--technology",
        "python-fastapi",
        "--database",
        "postgresql",
        "--description",
        "Bill customers.",
    )
    lock = json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))
    assert lock["selection"]["profile"] == "backend-api"
    assert lock["kit_version"] == "1.0.0"
    assert (root / "AGENTS.md").read_text("utf-8").startswith("# AGENTS.md — billing-api")
    assert "Bill customers." in (root / ".ai/context/project.md").read_text("utf-8")
    assert (root / ".ai/agents/02-backend.md").is_file()
    assert (root / ".ai/agents/03-database.md").is_file()
    assert not (root / ".ai/agents/01-frontend.md").exists()
    assert (root / ".ai/stacks/fastapi/README.md").is_file()
    assert (root / ".ai/stacks/postgresql/README.md").is_file()
    assert (root / "src/billing_api/domain/.gitkeep").is_file()
    assert (root / ".gitignore").read_text("utf-8").startswith("# Secrets")
    for rel, digest in lock["managed_files"].items():
        assert content_hash((root / rel).read_text("utf-8")) == digest


def test_database_none_drops_database_agent(init_project) -> None:
    root = init_project("ui", "--technology", "react", "--database", "none", profile="frontend")
    assert (root / ".ai/agents/01-frontend.md").is_file()
    assert not (root / ".ai/agents/03-database.md").exists()


def test_assistant_selection(init_project) -> None:
    root = init_project("only-claude", "--assistants", "claude-code")
    assert (root / "CLAUDE.md").is_file()
    assert not (root / ".github/copilot-instructions.md").exists()
    assert not (root / ".cursor").exists()


def test_files_use_lf_line_endings(init_project) -> None:
    root = init_project()
    assert b"\r\n" not in (root / "AGENTS.md").read_bytes()


def test_interactive_wizard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    answers = [
        "bad name!",  # invalid -> asked again
        "automation-hub",  # project name
        "4",  # Python Automation
        "1",  # Python (scripts, automation)
        "3",  # ClickHouse
        "",  # deployment: default (kubernetes)
        "1,2",  # assistants: claude-code, copilot
        "Automate weekly reporting.",
        "y",  # detailed questions
        "Manual reports take 2 days",
        "Finance team",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",  # confirm generation (default yes)
    ]
    result = run("init", answers=answers)
    assert result.code == 0, result.out + result.err
    assert "Invalid project name" in result.out
    root = tmp_path / "automation-hub"
    lock = json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))
    assert lock["selection"] == {
        "profile": "python-automation",
        "technology": "python",
        "database": "clickhouse",
        "deployment": "kubernetes",
        "assistants": ["claude-code", "copilot"],
        "extra_stacks": [],
    }
    context = (root / ".ai/context/project.md").read_text("utf-8")
    assert "Manual reports take 2 days" in context and "Finance team" in context
    assert (root / ".ai/stacks/clickhouse/README.md").is_file()


def test_interactive_decline_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = run("init", answers=["demo", "1", "1", "1", "1", "", "", "n", "n"])
    assert result.code == 0, result.out + result.err
    assert "nothing was written" in result.out
    assert not (tmp_path / "demo").exists()


def test_eof_aborts_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = run("init", answers=[])
    assert result.code == 2
    assert "Input aborted" in result.err


def test_refuses_already_initialised(init_project) -> None:
    root = init_project()
    result = run("init", str(root), "-y", "--profile", "backend-api")
    assert result.code == 2
    assert "already initialised" in result.err


def test_existing_project_is_preserved(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "README.md").write_text("# Legacy\nkeep me\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("my own instructions\n", encoding="utf-8")
    result = run("init", str(root), "-y", "--profile", "backend-api")
    assert result.code == 0, result.err
    assert (root / "README.md").read_text("utf-8") == "# Legacy\nkeep me\n"
    assert (root / "AGENTS.md").read_text("utf-8") == "my own instructions\n"
    assert (root / "AGENTS.md.kit-new").is_file()
    assert "differs from the kit version" in result.out


def test_force_keeps_backup(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "AGENTS.md").write_text("old\n", encoding="utf-8")
    result = run("init", str(root), "-y", "--profile", "backend-api", "--force")
    assert result.code == 0, result.err
    assert (root / "AGENTS.md.kit-backup").read_text("utf-8") == "old\n"
    assert "AGENTS.md — legacy" in (root / "AGENTS.md").read_text("utf-8")


def test_invalid_choices_are_rejected(tmp_path: Path) -> None:
    cases = [
        (["--profile", "nope"], "Unknown profile"),
        (["--profile", "frontend", "--technology", "python-django"], "not offered"),
        (["--profile", "backend-api", "--database", "oracle"], "Unknown database"),
        (["--profile", "backend-api", "--stacks", "cobol"], "Unknown stack"),
        (["--profile", "backend-api", "--assistants", "clippy"], "Unknown assistant"),
    ]
    for extra, message in cases:
        result = run("init", str(tmp_path / "x"), "-y", "--name", "x", *extra)
        assert result.code == 2, (extra, result.err)
        assert message in result.err
    assert not (tmp_path / "x").exists()


def test_non_interactive_requires_name_and_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert "--name is required" in run("init", "-y", "--profile", "frontend").err
    assert "--profile is required" in run("init", "-y", "--name", "x").err


def test_target_that_is_a_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    result = run("init", str(target), "-y", "--name", "x", "--profile", "frontend")
    assert result.code == 2
    assert "not a directory" in result.err


def test_custom_technology_with_extra_stacks(init_project) -> None:
    root = init_project(
        "custom-app", "--technology", "custom", "--stacks", "react,nginx", profile="custom"
    )
    assert (root / ".ai/stacks/react/README.md").is_file()
    assert (root / ".ai/stacks/nginx/README.md").is_file()
    assert len(list((root / ".ai/agents").glob("*.md"))) == 15
