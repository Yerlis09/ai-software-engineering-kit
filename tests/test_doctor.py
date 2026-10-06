from __future__ import annotations

import json
from pathlib import Path

from conftest import run

FAKE_PASSWORD = "Pr0d" + "Passw0rd!x"


def checks_by_name(root: Path) -> dict[str, dict]:
    result = run("doctor", "--path", str(root), "--format", "json")
    return {c["name"]: c for c in json.loads(result.out)["checks"]}


def test_fresh_project_has_no_failure(init_project) -> None:
    root = init_project()
    result = run("doctor", "--path", str(root))
    assert result.code == 0, result.out
    assert "AI SOFTWARE ENGINEERING CHECK" in result.out
    assert "Result: WARN" in result.out  # TODOs, no git, no tooling yet: honest warnings
    assert "0 failure(s)" in result.out


def test_strict_mode_fails_on_warnings(init_project) -> None:
    root = init_project()
    assert run("doctor", "--path", str(root), "--strict").code == 1


def test_empty_directory_fails(tmp_path: Path) -> None:
    result = run("doctor", "--path", str(tmp_path))
    assert result.code == 1
    assert "Result: FAIL" in result.out
    assert "ai-project init ." in result.out


def test_secret_in_source_fails(init_project) -> None:
    root = init_project()
    (root / "src" / "settings.py").write_text(f'DB_PASSWORD = "{FAKE_PASSWORD}"\n', "utf-8")
    result = run("doctor", "--path", str(root))
    assert result.code == 1
    assert "src/settings.py:1" in result.out


def test_env_credentials_warn_loudly_without_blocking(init_project) -> None:
    root = init_project()
    (root / ".env").write_text(f"DB_PASSWORD={FAKE_PASSWORD}\n", "utf-8")
    result = run("doctor", "--path", str(root))
    assert result.code == 0  # team policy: warn, do not block
    assert "SECURITY WARNING - REAL CREDENTIALS FOUND IN .env FILES" in result.out
    assert "vincent.goutagny@netsf.fr" in result.out
    assert checks_by_name(root)["Credentials in .env files"]["status"] == "WARN"


def test_env_not_gitignored_is_reported(init_project) -> None:
    root = init_project()
    (root / ".gitignore").write_text("node_modules/\n", "utf-8")
    assert checks_by_name(root)[".gitignore"]["detail"] == ".env is not ignored"


def test_git_remote_on_team_server(init_project) -> None:
    root = init_project()
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/acme/x.git\n', "utf-8"
    )
    assert "git.netsf.fr" in checks_by_name(root)["Remote"]["detail"]
    (root / ".git" / "config").write_text(
        '[remote "origin"]\n\turl = https://git.netsf.fr/team/x.git\n', "utf-8"
    )
    assert checks_by_name(root)["Remote"]["status"] == "PASS"


def test_tooling_detection(init_project) -> None:
    root = init_project()
    (root / "pyproject.toml").write_text("[tool.ruff]\n[tool.mypy]\n", "utf-8")
    (root / "uv.lock").write_text("", "utf-8")
    (root / "tests" / "unit" / "test_x.py").write_text("def test_x(): pass\n", "utf-8")
    (root / ".gitlab-ci.yml").write_text("stages: [test]\n", "utf-8")
    checks = checks_by_name(root)
    for name in (
        "Formatter",
        "Linter",
        "Type checker",
        "Tests",
        "CI pipeline",
        "Dependency lock (pyproject.toml)",
    ):
        assert checks[name]["status"] == "PASS", name


def test_dockerfile_running_as_root(init_project) -> None:
    root = init_project()
    (root / "Dockerfile").write_text('FROM python:3.12-slim\nCMD ["python"]\n', "utf-8")
    assert checks_by_name(root)["Non-root container (Dockerfile)"]["status"] == "WARN"
    (root / "Dockerfile").write_text("FROM python:3.12-slim\nUSER app\n", "utf-8")
    assert checks_by_name(root)["Non-root container (Dockerfile)"]["status"] == "PASS"


def test_modified_and_missing_core_files(init_project) -> None:
    root = init_project()
    (root / ".ai/rules/coding.md").write_text("changed\n", "utf-8")
    (root / ".ai/workflows/release.md").unlink()
    checks = checks_by_name(root)
    assert checks["Core files customised"]["status"] == "INFO"
    assert checks["Core files present"]["status"] == "WARN"


def test_json_output_is_machine_readable(init_project) -> None:
    root = init_project()
    data = json.loads(run("doctor", "--path", str(root), "--format", "json").out)
    assert data["result"] in ("PASS", "WARN")
    assert {"category", "name", "status", "detail", "hint"} <= set(data["checks"][0])


def test_missing_path_is_usage_error(tmp_path: Path) -> None:
    assert run("doctor", "--path", str(tmp_path / "nope")).code == 2


DEMO = Path(__file__).resolve().parent.parent / "examples" / "fastapi-demo"


def test_demo_project_passes_doctor() -> None:
    result = run("doctor", "--path", str(DEMO))
    assert result.code == 0, result.out
    assert "0 failure(s)" in result.out


def test_demo_project_is_in_sync_with_the_kit() -> None:
    """Fails when kit content changed without refreshing the demo (run 'ai-project update')."""
    result = run("update", "--path", str(DEMO), "--check")
    assert result.code == 0, result.out


def test_vendored_dirs_are_ignored(init_project) -> None:
    root = init_project()
    vendored = root / ".venv" / "Lib" / "site-packages" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "test_pkg.py").write_text("def test_x(): pass\n", "utf-8")
    (vendored / "Dockerfile").write_text("FROM scratch\n", "utf-8")
    checks = checks_by_name(root)
    assert checks["Tests"]["status"] == "WARN"
    assert not any(name.startswith("Non-root container") for name in checks)


def test_malformed_package_json_does_not_crash(init_project) -> None:
    root = init_project()
    (root / "package.json").write_text('{"dependencies": ["eslint"]}', "utf-8")
    assert checks_by_name(root)["Linter"]["status"] == "WARN"
