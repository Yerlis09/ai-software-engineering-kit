from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

from ai_project import cli
from ai_project.catalog import Catalog
from ai_project.console import Console
from ai_project.paths import kit_root

KIT_DIRS = (
    "agents",
    "rules",
    "workflows",
    "stacks",
    "profiles",
    "catalog",
    "templates",
    "integrations",
)
VERSIONED_MODULES = (
    "ai_project.generator",
    "ai_project.updater",
    "ai_project.init_cmd",
    "ai_project.doctor",
    "ai_project.cli",
)


class Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.code, self.out, self.err = code, out, err


def run(*argv: str, answers: list[str] | None = None) -> Result:
    """Run the CLI in-process with captured output and scripted interactive answers."""
    out, err = io.StringIO(), io.StringIO()
    feed = iter(answers or [])

    def fake_input(_prompt: str) -> str:
        try:
            return next(feed)
        except StopIteration:
            raise EOFError from None

    code = cli.main(list(argv), console=Console(out, err), input_fn=fake_input)
    return Result(code, out.getvalue(), err.getvalue())


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(kit_root())


@pytest.fixture
def init_project(tmp_path: Path):
    """Factory: generate a project non-interactively and return its path."""

    def _make(name: str = "demo-app", *extra: str, profile: str = "backend-api") -> Path:
        target = tmp_path / name
        result = run("init", str(target), "-y", "--name", name, "--profile", profile, *extra)
        assert result.code == 0, result.out + result.err
        return target

    return _make


@pytest.fixture
def kit_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private, writable copy of the kit, selected through AI_KIT_HOME."""
    source = kit_root()
    copy = tmp_path / "kit-copy"
    for name in KIT_DIRS:
        shutil.copytree(source / name, copy / name)
    monkeypatch.setenv("AI_KIT_HOME", str(copy))
    return copy


@pytest.fixture
def set_version(monkeypatch: pytest.MonkeyPatch):
    """Pretend the installed kit has another version (simulates a kit upgrade)."""
    import importlib

    def _set(version: str) -> None:
        for module_name in VERSIONED_MODULES:
            monkeypatch.setattr(importlib.import_module(module_name), "__version__", version)

    return _set
