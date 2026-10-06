"""Turn a selection into a file plan, then write it safely.

Two kinds of files are produced:

* CORE (``managed=True``): agents, rules, workflows, stack guides, ``AGENTS.md`` and
  assistant integrations. Owned by the kit, tracked by hash, refreshed by ``update``.
* SEED (``managed=False``): project context, docs skeleton, ``.gitignore``...
  Created once if absent, then owned by the project. The kit never touches them again.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ai_project import __version__
from ai_project.catalog import Catalog, Resolved, Selection
from ai_project.errors import KitError
from ai_project.lockfile import content_hash, file_hash
from ai_project.paths import package_name, safe_join
from ai_project.render import render

AI_DIR = ".ai"

# Answers collected by `init` (and stored in the lock file), with their placeholder text.
ANSWER_DEFAULTS = {
    "description": "TODO: one or two sentences describing the business objective.",
    "problem": "TODO: which problem does this project solve, for whom, and why now?",
    "users": "TODO: who uses it (roles, internal/external, expected number)?",
    "owner": "TODO: team or person accountable for the project.",
    "functional_requirements": "TODO: list the main capabilities (user stories or use cases).",
    "non_functional_requirements": "TODO: availability, scalability, maintainability targets.",
    "external_services": "TODO: APIs, identity provider, message brokers, third parties.",
    "security_requirements": "TODO: data classification, authentication, compliance (GDPR...).",
    "performance_requirements": "TODO: latency / throughput / data volume targets.",
    "constraints": "TODO: deadlines, budget, mandated technologies, hosting constraints.",
    "risks": "TODO: main technical and business risks and their mitigation.",
}


@dataclass(frozen=True)
class PlannedFile:
    path: str  # POSIX path relative to the project root
    content: str
    managed: bool


@dataclass
class WriteReport:
    created: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # seed already present: project-owned
    conflicts: list[str] = field(default_factory=list)  # core file differs locally
    overwritten: list[str] = field(default_factory=list)


def build_values(catalog: Catalog, resolved: Resolved, selection: Selection, answers: dict) -> dict:
    name = answers["project_name"]
    profile = resolved.profile
    values = {key: answers.get(key) or default for key, default in ANSWER_DEFAULTS.items()}
    values.update(
        project_name=name,
        package_name=package_name(name),
        created_date=answers.get("created_date") or date.today().isoformat(),
        kit_version=__version__,
        profile=profile.name,
        profile_title=profile.title,
        profile_description=profile.description,
        technology=selection.technology,
        technology_title=catalog.technologies[selection.technology].title,
        database=selection.database,
        database_title=catalog.databases[selection.database].title,
        deployment=selection.deployment,
        deployment_title=catalog.deployments[selection.deployment].title,
        architecture=profile_architecture(profile.name),
        agents_table="\n".join(
            f"| `{AI_DIR}/agents/{a}.md` | {catalog.agent_title(a)} |" for a in resolved.agents
        ),
        rules_list="\n".join(f"- `{AI_DIR}/rules/{r}.md`" for r in resolved.rules),
        workflows_list="\n".join(f"- `{AI_DIR}/workflows/{w}.md`" for w in resolved.workflows),
        stacks_list="\n".join(f"- `{AI_DIR}/stacks/{s}/README.md`" for s in resolved.stacks)
        or "- (none selected)",
        structure_list="\n".join(
            f"- `{render(d, {'package_name': package_name(name)})}/`" for d in profile.structure
        )
        or "- (free structure)",
    )
    values.update({f"org_{k}": v for k, v in catalog.organization.items()})
    return values


def profile_architecture(profile: str) -> str:
    return {
        "backend-api": "Modular monolith with layered / clean architecture "
        "(API -> Application -> Domain <- Infrastructure).",
        "frontend": "Feature-based SPA: pages -> feature components -> shared UI -> services.",
        "fullstack": "Separate frontend SPA and backend modular monolith, deployed together.",
        "python-automation": "Jobs orchestrate services; adapters isolate external systems.",
        "data-engineering": "Extract -> Transform -> Load stages with data-quality gates, "
        "idempotent and incremental.",
        "microservice": "Hexagonal service: domain core, ports, adapters (HTTP, DB, messaging).",
    }.get(profile, "To be decided with agents/04-architecture.md and recorded as an ADR.")


def build_plan(
    catalog: Catalog, resolved: Resolved, selection: Selection, answers: dict
) -> list[PlannedFile]:
    values = build_values(catalog, resolved, selection, answers)
    root = catalog.root
    plan: dict[str, PlannedFile] = {}

    def add(path: str, content: str, managed: bool) -> None:
        plan[path] = PlannedFile(path, content.replace("\r\n", "\n"), managed)

    # 1. Knowledge base, copied verbatim (never rendered).
    for agent in resolved.agents:
        add(f"{AI_DIR}/agents/{agent}.md", _read(root / "agents" / f"{agent}.md"), True)
    for rule in resolved.rules:
        add(f"{AI_DIR}/rules/{rule}.md", _read(root / "rules" / f"{rule}.md"), True)
    for workflow in resolved.workflows:
        add(f"{AI_DIR}/workflows/{workflow}.md", _read(root / "workflows" / f"{workflow}.md"), True)
    for stack in resolved.stacks:
        stack_dir = root / "stacks" / stack
        for source in sorted(stack_dir.rglob("*.md")):
            rel = source.relative_to(stack_dir).as_posix()
            add(f"{AI_DIR}/stacks/{stack}/{rel}", _read(source), True)

    # 2. Templates: base first, then the profile overlay (same path = override).
    managed_templates = set(_load_manifest(root)["managed"])
    for layer in _unique(["base", resolved.profile.template]):
        layer_dir = root / "templates" / layer
        for source in sorted(p for p in layer_dir.rglob("*") if p.is_file()):
            rel = _destination(source.relative_to(layer_dir).as_posix())
            add(rel, render(_read(source), values, source=str(source)), rel in managed_templates)

    # 3. Thin assistant-specific pointers to AGENTS.md (no duplicated knowledge).
    for assistant in resolved.assistants:
        files_dir = root / "integrations" / assistant / "files"
        if not files_dir.is_dir():
            continue
        for source in sorted(p for p in files_dir.rglob("*") if p.is_file()):
            rel = source.relative_to(files_dir).as_posix()
            add(rel, render(_read(source), values, source=str(source)), True)

    # 4. Recommended directory structure (empty folders kept with .gitkeep).
    for directory in resolved.profile.structure:
        rel = render(directory, values, source=f"profile {resolved.profile.name}")
        if not any(existing.startswith(rel + "/") for existing in plan):
            add(f"{rel}/.gitkeep", "", False)

    return list(plan.values())


def _destination(rel: str) -> str:
    """``dot-gitignore`` -> ``.gitignore`` and ``x.md.tmpl`` -> ``x.md``.

    Dotfiles are stored with a ``dot-`` prefix so they do not affect the kit repository
    itself (a real ``.gitignore`` inside ``templates/`` would be applied by Git).
    """
    parts = [("." + p[4:]) if p.startswith("dot-") else p for p in rel.split("/")]
    out = "/".join(parts)
    return out[: -len(".tmpl")] if out.endswith(".tmpl") else out


def _load_manifest(root: Path) -> dict:
    try:
        return json.loads((root / "templates" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KitError(f"Invalid templates/manifest.json: {exc}") from None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KitError(f"Cannot read kit file {path}: {exc}") from None


def _unique(items):
    return list(dict.fromkeys(items))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def backup(root: Path, rel: str) -> None:
    """Save ``rel`` as ``rel.kit-backup`` byte for byte (any encoding)."""
    shutil.copyfile(safe_join(root, rel), safe_join(root, rel + ".kit-backup"))


def apply_plan(root: Path, plan: list[PlannedFile], force: bool = False) -> WriteReport:
    """Write a fresh plan (used by ``init``). Existing files are never silently replaced.

    * seed present         -> skipped (project-owned)
    * core present & equal -> unchanged
    * core present & diff  -> kit version written to ``<file>.kit-new`` (conflict),
                              or, with ``force``, old file saved as ``<file>.kit-backup``.
    """
    report = WriteReport()
    for item in plan:
        target = safe_join(root, item.path)
        if target.is_dir():
            raise KitError(f"Cannot write {item.path}: a directory exists at that path.")
        if not target.exists():
            write_text(target, item.content)
            report.created.append(item.path)
        elif not item.managed:
            report.skipped.append(item.path)
        elif file_hash(target) == content_hash(item.content):
            report.unchanged.append(item.path)
        elif force:
            backup(root, item.path)
            write_text(target, item.content)
            report.overwritten.append(item.path)
        else:
            write_text(safe_join(root, item.path + ".kit-new"), item.content)
            report.conflicts.append(item.path)
    return report
