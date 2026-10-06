from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_project.errors import KitError
from ai_project.paths import clean_text, package_name, safe_join, validate_project_name
from ai_project.render import render


class TestSafeJoin:
    def test_accepts_nested_relative_path(self, tmp_path: Path) -> None:
        assert safe_join(tmp_path, "a/b/c.md") == (tmp_path / "a" / "b" / "c.md").resolve()

    @pytest.mark.parametrize(
        "evil",
        [
            "../escape.md",
            "a/../../escape.md",
            "/etc/passwd",
            "C:/Windows/x",
            "C:x",
            "a\\..\\b",
            "\\\\server\\share",
            "",
            "a/./b",
            "a\x00b",
        ],
    )
    def test_rejects_traversal_and_absolute(self, tmp_path: Path, evil: str) -> None:
        with pytest.raises(KitError):
            safe_join(tmp_path, evil)

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "root"
        root.mkdir()
        try:
            os.symlink(outside, root / "link", target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not permitted on this platform/user")
        with pytest.raises(KitError):
            safe_join(root, "link/file.md")


class TestProjectName:
    @pytest.mark.parametrize("name", ["automation-hub", "Api_v2", "a", "svc.billing"])
    def test_valid(self, name: str) -> None:
        assert validate_project_name(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "1app",
            "-app",
            "my app",
            "../x",
            "a/b",
            "a\\b",
            "con",
            "NUL.txt",
            "lpt1",
            "name.",
            "x" * 65,
            "café",
        ],
    )
    def test_invalid(self, name: str) -> None:
        with pytest.raises(KitError):
            validate_project_name(name)

    def test_package_name(self) -> None:
        assert package_name("Automation-Hub.v2") == "automation_hub_v2"


def test_clean_text_strips_control_chars_and_caps_length() -> None:
    assert clean_text("  hello\x1b[31m\x07 world \n") == "hello[31m world"
    assert len(clean_text("x" * 5000)) == 2000
    assert clean_text(None) == ""


class TestRender:
    def test_substitutes(self) -> None:
        assert render("Hi {{ name }}/{{name}}", {"name": "Ana"}) == "Hi Ana/Ana"

    def test_unknown_variable_is_an_error(self) -> None:
        with pytest.raises(KitError, match="unknown"):
            render("{{ missing }}", {})

    def test_values_are_not_re_expanded(self) -> None:
        # A user typing template syntax must not trigger a second expansion.
        assert render("{{ a }}", {"a": "{{ b }}", "b": "boom"}) == "{{ b }}"

    def test_no_code_execution(self) -> None:
        assert render("{{ __import__('os') }}", {}) == "{{ __import__('os') }}"
