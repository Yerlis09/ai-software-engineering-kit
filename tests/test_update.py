"""Kit upgrades are simulated with a writable kit copy (AI_KIT_HOME) and a patched version."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import run


def lock(root: Path) -> dict:
    return json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))


@pytest.fixture
def project(kit_copy: Path, init_project) -> Path:
    return init_project("svc", "--technology", "python-fastapi", "--database", "postgresql")


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text("utf-8") + text, encoding="utf-8")


def test_up_to_date(project: Path) -> None:
    result = run("update", "--path", str(project))
    assert result.code == 0
    assert "Current Kit: 1.0.0" in result.out and "Latest Kit:  1.0.0" in result.out
    assert "Already up to date" in result.out


def test_pristine_files_are_updated(project: Path, kit_copy: Path, set_version) -> None:
    append(kit_copy / "rules" / "coding.md", "\n- CODE-99 MUST be new.\n")
    set_version("1.1.0")
    result = run("update", "--path", str(project))
    assert result.code == 0, result.err
    assert "CODE-99" in (project / ".ai/rules/coding.md").read_text("utf-8")
    assert "AI Software Engineering Kit v1.1.0" in (project / "AGENTS.md").read_text("utf-8")
    assert lock(project)["kit_version"] == "1.1.0"
    assert run("update", "--path", str(project)).out.count("Already up to date") == 1


def test_customisation_is_kept_when_kit_unchanged(project: Path, set_version) -> None:
    append(project / ".ai/rules/testing.md", "\nProject tweak.\n")
    set_version("1.0.1")
    result = run("update", "--path", str(project))
    assert result.code == 0
    assert "Project tweak." in (project / ".ai/rules/testing.md").read_text("utf-8")


def test_conflict_writes_kit_new(project: Path, kit_copy: Path, set_version) -> None:
    append(project / ".ai/rules/security.md", "\nLocal change.\n")
    append(kit_copy / "rules" / "security.md", "\nKit change.\n")
    set_version("1.1.0")
    result = run("update", "--path", str(project))
    assert result.code == 0
    assert "CONFLICT" in result.out
    local = (project / ".ai/rules/security.md").read_text("utf-8")
    assert "Local change." in local and "Kit change." not in local
    assert "Kit change." in (project / ".ai/rules/security.md.kit-new").read_text("utf-8")
    # Keeping the local version is a stable choice: the next update does not re-flag it.
    (project / ".ai/rules/security.md.kit-new").unlink()
    assert "CONFLICT" not in run("update", "--path", str(project)).out


def test_force_overwrites_with_backup(project: Path, kit_copy: Path, set_version) -> None:
    append(project / ".ai/rules/security.md", "\nLocal change.\n")
    append(kit_copy / "rules" / "security.md", "\nKit change.\n")
    set_version("1.1.0")
    assert run("update", "--path", str(project), "--force").code == 0
    assert "Kit change." in (project / ".ai/rules/security.md").read_text("utf-8")
    backup = project / ".ai/rules/security.md.kit-backup"
    assert "Local change." in backup.read_text("utf-8")


def test_new_agent_added_and_removed_agent_deleted(project, kit_copy, set_version) -> None:
    profile_path = kit_copy / "profiles" / "backend-api.json"
    profile = json.loads(profile_path.read_text("utf-8"))
    profile["agents"] = [a for a in profile["agents"] if a != "07-oop"] + ["01-frontend"]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    set_version("1.1.0")
    result = run("update", "--path", str(project))
    assert result.code == 0, result.err
    assert (project / ".ai/agents/01-frontend.md").is_file()
    assert not (project / ".ai/agents/07-oop.md").exists()
    assert ".ai/agents/07-oop.md" not in lock(project)["managed_files"]


def test_missing_core_file_is_restored(project: Path) -> None:
    (project / ".ai/workflows/bug-fix.md").unlink()
    result = run("update", "--path", str(project))
    assert result.code == 0
    assert (project / ".ai/workflows/bug-fix.md").is_file()
    assert "restored" in result.out


def test_seed_files_are_never_touched(project: Path, kit_copy: Path, set_version) -> None:
    (project / "README.md").write_text("# mine\n", encoding="utf-8")
    append(kit_copy / "templates" / "base" / "README.md", "\nNew kit README line.\n")
    set_version("1.1.0")
    run("update", "--path", str(project))
    assert (project / "README.md").read_text("utf-8") == "# mine\n"


def test_check_and_dry_run_do_not_write(project: Path, kit_copy: Path, set_version) -> None:
    append(kit_copy / "rules" / "coding.md", "\nNEW\n")
    set_version("1.1.0")
    before = (project / ".ai/rules/coding.md").read_text("utf-8")
    check = run("update", "--path", str(project), "--check")
    assert check.code == 1 and "Updates are available" in check.out
    dry = run("update", "--path", str(project), "--dry-run")
    assert dry.code == 0 and "Dry run" in dry.out
    assert (project / ".ai/rules/coding.md").read_text("utf-8") == before
    assert lock(project)["kit_version"] == "1.0.0"


def test_project_newer_than_cli_is_refused(project: Path, set_version) -> None:
    set_version("0.9.0")
    result = run("update", "--path", str(project))
    assert result.code == 1
    assert "Upgrade the CLI first" in result.err


def test_not_initialised(tmp_path: Path) -> None:
    result = run("update", "--path", str(tmp_path))
    assert result.code == 1
    assert "ai-project init ." in result.err


def test_tampered_lock_cannot_escape_project(project: Path) -> None:
    data = lock(project)
    data["managed_files"]["../../outside.md"] = "0" * 64
    (project / ".ai/kit.lock.json").write_text(json.dumps(data), encoding="utf-8")
    result = run("update", "--path", str(project))
    assert result.code == 1
    assert "traversal" in result.err.lower() or "corrupt" in result.err.lower()


def test_corrupt_lock(project: Path) -> None:
    (project / ".ai/kit.lock.json").write_text("{not json", encoding="utf-8")
    result = run("update", "--path", str(project))
    assert result.code == 1 and "corrupt" in result.err


def test_crlf_checkout_is_not_a_modification(project: Path) -> None:
    path = project / ".ai/rules/coding.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))  # git autocrlf on Windows
    assert "Already up to date" in run("update", "--path", str(project)).out


def test_lock_that_is_not_an_object(project: Path) -> None:
    (project / ".ai/kit.lock.json").write_text("[]", encoding="utf-8")
    result = run("update", "--path", str(project))
    assert result.code == 1 and "corrupt" in result.err


def test_force_backup_keeps_non_utf8_bytes(project, kit_copy, set_version) -> None:
    target = project / ".ai/rules/security.md"
    target.write_bytes(b"caf\xe9 latin-1 edit\n")
    (kit_copy / "rules" / "security.md").write_text("new kit content\n", encoding="utf-8")
    set_version("1.1.0")
    assert run("update", "--path", str(project), "--force").code == 0
    assert (project / ".ai/rules/security.md.kit-backup").read_bytes() == b"caf\xe9 latin-1 edit\n"


def test_directory_in_place_of_core_file(project: Path) -> None:
    target = project / ".ai/rules/coding.md"
    target.unlink()
    target.mkdir()
    result = run("update", "--path", str(project))
    assert result.code == 1 and "a directory exists" in result.err
    assert json.loads((project / ".ai/kit.lock.json").read_text("utf-8"))["kit_version"] == "1.0.0"
