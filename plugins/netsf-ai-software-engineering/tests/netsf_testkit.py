"""Helpers and fixtures shared by the plugin tests.

The plugin has no conftest.py on purpose: the core tests import helpers with
``from conftest import ...`` and a second conftest module would shadow theirs.
Test modules import the ``kit_project`` fixture from here instead.
"""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from netsf import bridge

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def kit_project(tmp_path: Path) -> Path:
    """A project initialised by the real Kit core (in-process call of its CLI)."""
    from ai_project import cli as kit_cli

    root = tmp_path / "kit-app"
    code = kit_cli.main(
        [
            "init",
            str(root),
            "-y",
            "--name",
            "kit-app",
            "--profile",
            "backend-api",
            "--technology",
            "python-fastapi",
        ]
    )
    assert code == 0
    return root


def run_bridge(*argv: str) -> tuple[int, str]:
    """Run a bridge command in-process and capture stdout."""
    out = io.StringIO()
    with redirect_stdout(out):
        code = bridge.main(list(argv))
    return code, out.getvalue()


def bridge_json(*argv: str) -> tuple[int, dict]:
    code, text = run_bridge(*argv, "--json")
    return code, json.loads(text)


def tree_digest(root: Path) -> dict[str, str]:
    """Content hash of every file under root (to prove a command modified nothing)."""
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
