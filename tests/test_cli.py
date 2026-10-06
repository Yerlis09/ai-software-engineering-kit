from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import run

from ai_project import __version__

REPO = Path(__file__).resolve().parent.parent


def test_version_command() -> None:
    result = run("version")
    assert result.code == 0
    assert f"ai-project {__version__}" in result.out
    assert "Kit:" in result.out and "Python:" in result.out


def test_version_flag(capsys) -> None:
    assert run("--version").code == 0
    assert __version__ in capsys.readouterr().out


def test_help_lists_all_commands() -> None:
    for argv in ([], ["help"]):
        result = run(*argv)
        assert result.code == 0
        for command in ("init", "doctor", "update", "version", "help", "list"):
            assert command in result.out


def test_help_for_a_command(capsys) -> None:
    assert run("help", "init").code == 0
    assert "--non-interactive" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("what", "expected"),
    [
        ("profiles", "backend-api"),
        ("technologies", "python-fastapi"),
        ("databases", "clickhouse"),
        ("deployments", "RKE"),
        ("assistants", "claude-code"),
        ("stacks", "kubernetes"),
        ("agents", "Master"),
    ],
)
def test_list(what: str, expected: str) -> None:
    result = run("list", what)
    assert result.code == 0 and expected in result.out


def test_unknown_command_is_usage_error(capsys) -> None:
    assert run("deploy").code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_invalid_kit_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_KIT_HOME", str(tmp_path))
    result = run("list")
    assert result.code == 1 and "does not contain a kit" in result.err


def test_module_entry_point_runs_as_subprocess() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ai_project", "--version"],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONPATH": str(REPO / "cli")},
    )
    assert completed.returncode == 0, completed.stderr
    assert __version__ in completed.stdout
