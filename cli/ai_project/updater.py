"""``ai-project update``: bring CORE kit files to the installed kit version.

Three-way decision per core file, using the hash recorded in the lock file as the base:

=================  ==================  ==========================================
local vs base      kit changed?        action
=================  ==================  ==========================================
missing            -                   write (restore / add)
equal (pristine)   yes                 overwrite
equal to new kit   -                   nothing
modified           no                  keep (project customisation)
modified           yes                 CONFLICT: write ``<file>.kit-new``
=================  ==================  ==========================================

``--force`` resolves conflicts in favour of the kit, saving ``<file>.kit-backup``.
SEED files (context, docs, .gitignore...) are project-owned and never modified.
The kit never downloads anything: upgrading the CLI itself is an explicit pip step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_project import __version__
from ai_project.catalog import Catalog, Selection
from ai_project.console import FAIL, INFO, PASS, WARN, Console
from ai_project.errors import EXIT_FAILURE, EXIT_OK, KitError
from ai_project.generator import backup, build_plan, write_text
from ai_project.lockfile import (
    Lock,
    content_hash,
    file_hash,
    now_iso,
    parse_version,
    read_lock,
    write_lock,
)
from ai_project.paths import safe_join

UPGRADE_HINT = "pip install --upgrade ai-software-engineering-kit (see README, 'Updating')"


@dataclass
class UpdatePlan:
    write: dict[str, str] = field(default_factory=dict)  # path -> content
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    conflicts: dict[str, str] = field(default_factory=dict)  # path -> new kit content
    removed: list[str] = field(default_factory=list)
    obsolete_modified: list[str] = field(default_factory=list)
    seeds_added: dict[str, str] = field(default_factory=dict)
    new_managed: dict[str, str] = field(default_factory=dict)
    # Derived artefacts (graph.json, index.json): regenerated, never conflicts
    derived: dict[str, str] = field(default_factory=dict)  # path -> content to write
    derived_paths: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.write or self.conflicts or self.removed or self.seeds_added or self.derived
        )


def compute_update(root: Path, catalog: Catalog, lock: Lock) -> UpdatePlan:
    selection = Selection.from_dict(lock.selection)
    try:
        resolved = catalog.resolve(selection)
    except KitError as exc:
        raise KitError(
            f"The installed kit no longer supports this project's selection: {exc}"
        ) from None
    plan_files = build_plan(catalog, resolved, selection, lock.answers)
    result = UpdatePlan()

    for item in (p for p in plan_files if p.managed):
        new_hash = content_hash(item.content)
        base = lock.managed.get(item.path)
        target = safe_join(root, item.path)
        if target.is_dir():
            raise KitError(f"Cannot update {item.path}: a directory exists at that path.")
        local = file_hash(target)
        result.new_managed[item.path] = new_hash
        if local is None:
            result.write[item.path] = item.content
            (result.restored if base else result.added).append(item.path)
        elif local == new_hash:
            continue
        elif base is not None and local == base:
            result.write[item.path] = item.content
            result.updated.append(item.path)
        elif base == new_hash:
            result.kept.append(item.path)
        else:
            result.conflicts[item.path] = item.content

    for item in (p for p in plan_files if p.derived):
        result.derived_paths.append(item.path)
        target = safe_join(root, item.path)
        if target.is_dir():
            raise KitError(f"Cannot update {item.path}: a directory exists at that path.")
        if file_hash(target) != content_hash(item.content):  # missing, edited or stale
            result.derived[item.path] = item.content

    for rel, base in lock.managed.items():
        if rel in result.new_managed or rel in result.derived_paths:
            continue  # derived in v1.2 (index.json was CORE in v1.1): not obsolete
        local = file_hash(safe_join(root, rel))
        if local == base:
            result.removed.append(rel)
        elif local is not None:
            result.obsolete_modified.append(rel)

    known_seeds = set(lock.seeds)
    for item in (p for p in plan_files if not p.managed and not p.derived):
        if item.path not in known_seeds and not safe_join(root, item.path).exists():
            result.seeds_added[item.path] = item.content
    return result


def run_update(
    root: Path,
    catalog: Catalog,
    console: Console,
    dry_run: bool = False,
    check: bool = False,
    force: bool = False,
) -> int:
    lock = read_lock(root)
    if lock is None:
        raise KitError(f"{root} was not initialised by the kit. Run 'ai-project init .' first.")
    console.title("AI SOFTWARE ENGINEERING KIT - UPDATE")
    console.print(f"Current Kit: {lock.kit_version}  (project)")
    console.print(f"Latest Kit:  {__version__}  (installed CLI)")
    if parse_version(lock.kit_version) > parse_version(__version__):
        raise KitError(
            f"This project uses kit {lock.kit_version}, newer than the installed CLI "
            f"{__version__}. Upgrade the CLI first: {UPGRADE_HINT}"
        )
    plan = compute_update(root, catalog, lock)
    _print_plan(console, plan, force)

    if not plan.has_changes:
        console.print()
        console.status(PASS, "Already up to date.")
        stale = (
            lock.kit_version != __version__
            or plan.new_managed != lock.managed
            or sorted(plan.derived_paths) != sorted(lock.derived)
        )
        if not check and not dry_run and stale:  # e.g. a file already equal to the new kit
            _save_lock(root, lock, plan)
        return EXIT_OK
    if check:
        console.print()
        console.status(WARN, "Updates are available (run 'ai-project update').")
        return EXIT_FAILURE
    if dry_run:
        console.print()
        console.status(INFO, "Dry run: nothing was written.")
        return EXIT_OK

    for rel, content in {**plan.write, **plan.seeds_added, **plan.derived}.items():
        write_text(safe_join(root, rel), content)
    for rel, content in plan.conflicts.items():
        target = safe_join(root, rel)
        if force:
            backup(root, rel)
            write_text(target, content)
        else:
            write_text(safe_join(root, rel + ".kit-new"), content)
    for rel in plan.removed:
        safe_join(root, rel).unlink()
    _save_lock(root, lock, plan)

    console.print()
    if plan.conflicts and not force:
        console.status(WARN, f"Updated with {len(plan.conflicts)} conflict(s) to merge by hand.")
        console.print("    -> Compare each file with its .kit-new version, merge, delete .kit-new.")
        console.print("    -> Move project-specific instructions to .ai/custom/ to avoid this.")
    else:
        console.status(PASS, f"Project updated to kit {__version__}.")
    return EXIT_OK


def _save_lock(root: Path, lock: Lock, plan: UpdatePlan) -> None:
    lock.kit_version = __version__
    lock.managed = plan.new_managed
    lock.seeds = sorted(set(lock.seeds) | set(plan.seeds_added))
    lock.derived = sorted(plan.derived_paths)
    lock.updated_at = now_iso()
    write_lock(root, lock)


def _print_plan(console: Console, plan: UpdatePlan, force: bool) -> None:
    groups = [
        (PASS, "updated", plan.updated),
        (PASS, "added", plan.added),
        (PASS, "restored (was missing)", plan.restored),
        (PASS, "removed (no longer in the kit)", plan.removed),
        (PASS, "regenerated (derived artefact, not a source of truth)", list(plan.derived)),
        (PASS, "new project file", list(plan.seeds_added)),
        (INFO, "kept (customised, kit unchanged)", plan.kept),
        (
            WARN,
            "obsolete but customised - kept, delete it manually if unused",
            plan.obsolete_modified,
        ),
        (
            FAIL if not force else WARN,
            "CONFLICT: customised locally AND changed in the kit"
            + (" - overwritten, backup saved" if force else " - kit version in .kit-new"),
            list(plan.conflicts),
        ),
    ]
    if any(paths for _, _, paths in groups):
        console.section("Changes")
    for level, label, paths in groups:
        for path in paths:
            console.status(level, path, label)
