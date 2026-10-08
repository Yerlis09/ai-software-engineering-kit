"""The project lock file: ``.ai/kit.lock.json``.

It records which kit version generated the project, what the developer selected and the
hash of every CORE (kit-managed) file *as the kit wrote it*. That hash is the common
ancestor used by ``update`` to tell "unchanged kit file" from "project customisation".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_project.errors import KitError
from ai_project.paths import safe_join

LOCK_PATH = ".ai/kit.lock.json"
SCHEMA_VERSION = 1


def content_hash(text: str) -> str:
    """Hash text with normalised line endings so Git's CRLF conversion is not a 'change'."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str | None:
    try:
        return content_hash(path.read_bytes().decode("utf-8", errors="replace"))
    except OSError:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Lock:
    kit_version: str
    selection: dict[str, Any]
    answers: dict[str, str]
    managed: dict[str, str] = field(default_factory=dict)
    seeds: list[str] = field(default_factory=list)
    derived: list[str] = field(default_factory=list)  # regenerated, never conflicts
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_json(self) -> str:
        data = {
            "schema_version": SCHEMA_VERSION,
            "kit_version": self.kit_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "selection": self.selection,
            "answers": self.answers,
            "managed_files": dict(sorted(self.managed.items())),
            "seed_files": sorted(self.seeds),
            "derived_files": sorted(self.derived),
        }
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def read_lock(root: Path) -> Lock | None:
    path = safe_join(root, LOCK_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("top level must be an object")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise KitError(
                f"{LOCK_PATH} uses schema {data.get('schema_version')}; "
                "this CLI understands schema 1. Upgrade the CLI."
            )
        managed = data["managed_files"]
        if not isinstance(managed, dict):
            raise TypeError("managed_files must be an object")
        for rel in [*managed, *data.get("derived_files", [])]:
            safe_join(root, rel)  # a tampered lock file must not lead us outside the project
        return Lock(
            kit_version=str(data["kit_version"]),
            selection=dict(data["selection"]),
            answers={str(k): str(v) for k, v in data.get("answers", {}).items()},
            managed={str(k): str(v) for k, v in managed.items()},
            seeds=[str(s) for s in data.get("seed_files", [])],
            derived=[str(s) for s in data.get("derived_files", [])],
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:  # incl. JSON/Unicode errors
        raise KitError(f"{LOCK_PATH} is corrupt ({exc}). Restore it from Git.") from None


def write_lock(root: Path, lock: Lock) -> None:
    path = safe_join(root, LOCK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(lock.to_json())


def parse_version(version: str) -> tuple[int, int, int]:
    try:
        major, minor, patch = (int(p) for p in version.split("-")[0].split("."))
    except ValueError:
        raise KitError(f"Invalid semantic version: {version!r}") from None
    return major, minor, patch
