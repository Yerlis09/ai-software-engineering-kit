"""Kit location, safe path handling and input validation.

Every path written by the kit goes through :func:`safe_join`, which refuses absolute
paths, ``..`` segments and anything that resolves (including through symlinks)
outside the target directory.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath

from ai_project.errors import EXIT_USAGE, KitError

KIT_HOME_ENV = "AI_KIT_HOME"
_KIT_MARKER = Path("agents") / "00-master.md"

_PROJECT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
_WINDOWS_RESERVED = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)
MAX_TEXT_LENGTH = 2000


def kit_root() -> Path:
    """Return the directory holding the knowledge base (agents, rules, templates...).

    Order: ``$AI_KIT_HOME`` (team forks), the copy bundled in the installed package,
    then the source checkout (editable installs and ``python -m`` from the repo).
    """
    override = os.environ.get(KIT_HOME_ENV)
    if override:
        candidate = Path(override).expanduser()
        if not _is_kit(candidate):
            raise KitError(
                f"{KIT_HOME_ENV}={override} does not contain a kit (missing {_KIT_MARKER})."
            )
        return candidate.resolve()
    package_dir = Path(__file__).resolve().parent
    for candidate in (package_dir / "_kit", package_dir.parent.parent):
        if _is_kit(candidate):
            return candidate
    raise KitError("Kit knowledge base not found. Reinstall the kit (see README, 'Installation').")


def _is_kit(path: Path) -> bool:
    return (path / _KIT_MARKER).is_file() and (path / "profiles").is_dir()


def safe_join(root: Path, relative: str) -> Path:
    """Join a POSIX-style relative path to ``root``, refusing any escape from ``root``."""
    if not relative or "\\" in relative or "\x00" in relative:
        raise KitError(f"Unsafe path rejected: {relative!r}")
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise KitError(f"Absolute path rejected: {relative!r}")
    if any(part in ("..", ".") for part in relative.split("/")):
        raise KitError(f"Path traversal rejected: {relative!r}")
    root_resolved = root.resolve()
    target = (root_resolved / Path(*posix.parts)).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise KitError(f"Path escapes the project directory: {relative!r}")
    return target


def validate_project_name(name: str) -> str:
    """Validate a project name; it becomes a directory name, so it must be portable."""
    name = (name or "").strip()
    if not _PROJECT_NAME.match(name):
        raise KitError(
            "Invalid project name. Use 1-64 characters: letters, digits, '-', '_' or '.', "
            "starting with a letter (example: automation-hub).",
            EXIT_USAGE,
        )
    if name.endswith(".") or name.split(".")[0].lower() in _WINDOWS_RESERVED:
        raise KitError(
            f"'{name}' is not a portable directory name (reserved on Windows).", EXIT_USAGE
        )
    return name


def package_name(project_name: str) -> str:
    """Derive an importable package name: ``Automation-Hub`` -> ``automation_hub``."""
    slug = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")
    return slug or "app"


def clean_text(value: str | None, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Normalise free text typed by the user: strip control characters and cap the length."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return text.strip()[:max_length]
