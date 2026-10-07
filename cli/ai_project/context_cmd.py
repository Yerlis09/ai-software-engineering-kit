"""``ai-project context``: show the minimum context for a task, with reasons and estimates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_project import __version__
from ai_project.catalog import Catalog, Selection
from ai_project.console import INFO, PASS, SKIP, WARN, Console
from ai_project.context_budget import parse_tiers
from ai_project.context_graph import (
    GRAPH_PATH,
    GRAPH_STALE_MESSAGE,
    Graph,
    GraphError,
    build_graph,
    check_project_graph,
    graph_sources,
    rebuild_graph,
)
from ai_project.context_index import BUDGET_PATH, CORE_FILES, ESTIMATION_NOTE, knowledge_path
from ai_project.context_router import (
    LOADED,
    ContextPackage,
    PlanSource,
    ProjectSource,
    Router,
    parse_budget,
)
from ai_project.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, KitError
from ai_project.generator import build_plan
from ai_project.init_cmd import DEFAULT_DEPLOYMENT, default_database
from ai_project.lockfile import Lock, content_hash, read_lock
from ai_project.paths import clean_text, safe_join

SIMULATED_NAME = "simulated-project"


@dataclass
class ContextOptions:
    task: str | None = None
    path: str = "."
    profile: str | None = None
    technology: str | None = None
    database: str | None = None
    as_json: bool = False
    strict: bool = False
    rebuild_graph: bool = False


@dataclass
class _Resolved:
    source: Any
    budget_text: str | None
    warnings: list[str]
    graph: Graph | None = None
    graph_info: dict[str, Any] = field(default_factory=dict)
    selection: dict[str, Any] = field(default_factory=dict)
    rebuilt: dict[str, Any] | None = None


def build_package(opts: ContextOptions, catalog: Catalog) -> ContextPackage:
    package, _ = _analyse(opts, catalog)
    return package


def _analyse(opts: ContextOptions, catalog: Catalog) -> tuple[ContextPackage, _Resolved]:
    task = clean_text(opts.task or "")
    if opts.profile:
        resolved = _simulated_source(opts, catalog)
    else:
        resolved = _project_source(Path(opts.path), catalog, opts.rebuild_graph)
    budget = parse_budget(resolved.budget_text)
    tiers = parse_tiers(resolved.budget_text)
    router = Router(
        catalog.routing,
        resolved.source,
        budget,
        graph=resolved.graph,
        tiers=tiers,
        selection=resolved.selection,
    )
    package = router.route(task)
    package.graph_info = resolved.graph_info
    package.warnings.extend(resolved.warnings)
    return package, resolved


def _simulated_source(opts: ContextOptions, catalog: Catalog) -> _Resolved:
    profile = catalog.profiles.get(opts.profile or "")
    if profile is None:
        raise KitError(
            f"Unknown profile '{opts.profile}'. Choose one of: {', '.join(catalog.profiles)}",
            EXIT_USAGE,
        )
    selection = Selection(
        profile.name,
        opts.technology or profile.technologies[0],
        opts.database or default_database(profile.name),
        DEFAULT_DEPLOYMENT,
        tuple(catalog.assistants),
    )
    plan = build_plan(
        catalog, catalog.resolve(selection), selection, {"project_name": SIMULATED_NAME}
    )
    files = {p.path: p.content for p in plan}
    hashes = {p.path: content_hash(p.content) for p in plan if p.managed}
    note = (
        f"Simulated {profile.name} project ({selection.technology}, {selection.database}); "
        "nothing was written"
    )
    resolved = _Resolved(
        PlanSource(files, f"{SIMULATED_NAME} ({profile.name})", profile.name),
        files.get(BUDGET_PATH),
        [note],
        selection=selection.to_dict(),
    )
    try:
        resolved.graph = build_graph(
            graph_sources(catalog, selection.to_dict(), SIMULATED_NAME, files, hashes, __version__)
        )
        resolved.graph_info = _info(resolved.graph, "simulated (built in memory)")
    except KitError as exc:  # fallback: direct (v1.1) routing
        resolved.warnings.append(f"Knowledge graph unavailable ({exc}); direct routing used")
        resolved.graph_info = {"status": "unavailable", "issue": str(exc)}
    return resolved


def _project_source(path: Path, catalog: Catalog, rebuild: bool) -> _Resolved:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise KitError(f"{root} is not a directory.", EXIT_USAGE)
    if not safe_join(root, ".ai").is_dir():
        raise KitError(
            f"{root} has no .ai/ folder. Run it inside a project created with 'ai-project init', "
            "or simulate one with --profile <name>.",
            EXIT_USAGE,
        )
    warnings: list[str] = []
    project = profile = None
    lock: Lock | None
    try:
        lock = read_lock(root)
    except KitError as exc:
        lock = None
        warnings.append(str(exc))
    if lock:
        project = lock.answers.get("project_name")
        profile = str(lock.selection.get("profile", "")) or None
    source = ProjectSource(root, project or root.name, profile)
    if source.index is None:
        warnings.append(
            ".ai/context/index.json missing or invalid: estimates read from files "
            "(run 'ai-project update' to add the index)"
        )
    budget_file = safe_join(root, BUDGET_PATH)
    try:
        budget_text = budget_file.read_text(encoding="utf-8") if budget_file.is_file() else None
    except OSError:
        budget_text = None
    if budget_text is None:
        warnings.append(f"{BUDGET_PATH} not found: default budget used")
    resolved = _Resolved(
        source, budget_text, warnings, selection=dict(lock.selection) if lock else {}
    )
    _attach_graph(resolved, root, catalog, lock, project or root.name, rebuild)
    return resolved


def _attach_graph(
    resolved: _Resolved,
    root: Path,
    catalog: Catalog,
    lock: Lock | None,
    project: str,
    rebuild: bool,
) -> None:
    """Load the saved graph; if missing/invalid/stale, rebuild it in memory (or on disk with
    --rebuild-graph); if that fails too, fall back to direct (v1.1) routing."""
    if lock is None:
        resolved.warnings.append("No lock file: knowledge graph not available; direct routing used")
        resolved.graph_info = {"status": "unavailable", "issue": "no lock file"}
        if rebuild:
            raise KitError("--rebuild-graph needs .ai/kit.lock.json (project created by the kit).")
        return
    check = check_project_graph(root, catalog.routing, __version__, lock)
    if check.state == "ok" and not rebuild:
        resolved.graph = check.graph
        resolved.graph_info = _info(check.graph, "loaded")
        return
    if check.state != "ok" and not rebuild:
        resolved.warnings.append(f"{GRAPH_STALE_MESSAGE} ({check.state}: {check.issues[0]})")
    try:
        src = graph_sources(
            catalog,
            lock.selection,
            project,
            _project_files(resolved.source),
            lock.managed,
            __version__,
        )
        if rebuild:
            graph = rebuild_graph(src, root)
            resolved.rebuilt = {**graph.stats(), "path": GRAPH_PATH, "previous_state": check.state}
            resolved.graph_info = _info(graph, "rebuilt and saved")
        else:
            graph = build_graph(src)
            resolved.graph_info = _info(graph, "rebuilt in memory", check.state)
        resolved.graph = graph
    except (KitError, OSError) as exc:
        if rebuild:
            raise
        resolved.warnings.append(f"Knowledge graph unavailable ({exc}); direct routing used")
        resolved.graph_info = {"status": "unavailable", "issue": str(exc)}


def _project_files(source: ProjectSource) -> dict[str, str]:
    files = {}
    paths = list(CORE_FILES) + [
        knowledge_path(kind, item)
        for kind in ("agents", "rules", "workflows", "stacks")
        for item in source.installed(kind)
    ]
    for path in paths:
        text = source.read(path)
        if text is not None:
            files[path] = text
    return files


def _info(graph: Graph | None, status: str, previous: str | None = None) -> dict[str, Any]:
    if graph is None:
        return {"status": status}
    stats = graph.stats()
    info: dict[str, Any] = {
        "status": status,
        "nodes": stats["nodes"],
        "edges": stats["edges"],
        "source_fingerprint": graph.fingerprint[:12],
        "path": GRAPH_PATH,
    }
    if previous:
        info["previous_state"] = previous
    return info


def run_context(opts: ContextOptions, catalog: Catalog, console: Console) -> int:
    try:
        package, resolved = _analyse(opts, catalog)
    except GraphError as exc:
        raise KitError(f"Knowledge graph rebuild failed: {exc}") from None
    only_rebuild = opts.rebuild_graph and not (opts.task or "").strip()
    if opts.as_json:
        data = {"graph_rebuild": resolved.rebuilt} if only_rebuild else package.to_dict()
        if resolved.rebuilt and not only_rebuild:
            data["graph_rebuild"] = resolved.rebuilt
        console.print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if resolved.rebuilt:
            print_rebuild(resolved.rebuilt, console)
        if not only_rebuild:
            print_package(package, console)
    return EXIT_FAILURE if opts.strict and package.status != "OK" else EXIT_OK


def print_rebuild(stats: dict[str, Any], console: Console) -> None:
    console.title("AI KNOWLEDGE GRAPH")
    console.print(f"Nodes: {stats['nodes']}  ({_counts(stats['node_types'])})")
    console.print(f"Edges: {stats['edges']}  ({_counts(stats['edge_types'])})")
    console.print()
    for check in ("Structure", "Node and edge types", "References", "Paths", "Cycles"):
        console.status(PASS, check)
    console.print()
    console.print(
        f"Graph rebuilt successfully: {stats['path']} (previous state: {stats['previous_state']})"
    )
    console.print()


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{k} {v}" for k, v in counts.items())


def _fmt(tokens: int) -> str:
    return f"{tokens:,} tokens"


def print_package(package: ContextPackage, console: Console) -> None:
    console.title("AI CONTEXT ANALYSIS")
    profile = f"  (profile {package.profile})" if package.profile else ""
    console.print(f"Project: {package.project or '-'}{profile}")
    graph = package.graph_info
    mode = "knowledge graph" if package.mode == "graph" else "direct (v1.1 fallback)"
    detail = f": {graph.get('status')}" if graph.get("status") else ""
    if graph.get("nodes"):
        detail += f", {graph['nodes']} nodes, {graph['edges']} edges"
    console.print(f"Routing: {mode}{detail}")
    console.print()
    console.print("Task:")
    console.print(
        f"  {package.task}"
        if package.task
        else '  (none) - pass --task "..." to select specialists; showing L0 core only'
    )
    if package.classification and package.classification.labels:
        console.print()
        console.print(f"Classification: {', '.join(package.classification.labels)}")
    if package.tier:
        console.print(
            f"Budget: {package.tier} - {package.tier_limit:,} tokens ({package.tier_reason})"
        )

    workflows = package.by_kind("workflow")
    if workflows:
        console.print()
        console.print(f"Workflow: {workflows[0].path}  ({workflows[0].reason})")

    console.section("Selected agents:")
    for item in package.by_kind("agent"):
        console.status(PASS, item.id, _with_rank(item.reason, item))
    targeted = (
        {
            a: r
            for a, r in package.skipped["agents"].items()
            if package.decisions[a].status == "targeted"
        }
        if package.task
        else {}
    )
    if targeted:
        console.section("Targeted reviews (rule sections instead of the full agent):")
        for agent_id, reason in targeted.items():
            console.status(INFO, agent_id, reason)
    console.section("Skipped:")
    for agent_id, reason in package.skipped["agents"].items():
        if agent_id not in targeted:
            console.status(SKIP, agent_id, reason)

    rules = package.by_kind("rule")
    if rules:
        console.section("Rules:")
        for item in rules:
            sections = (
                "whole file"
                if item.sections is None
                else ", ".join(s["heading"] for s in item.sections if s["heading"] != "(preamble)")
            )
            console.status(PASS, item.path, f"{sections} - for {', '.join(item.requested_by)}")
    stacks = package.by_kind("stack")
    if stacks or package.skipped["stacks"]:
        console.section("Stack guides:")
        for item in stacks:
            console.status(PASS, item.id, _with_rank(item.reason, item))
        for stack_id, reason in package.skipped["stacks"].items():
            console.status(SKIP, stack_id, reason)
    if package.deduplicated:
        console.section("Deduplicated:")
        for line in package.deduplicated:
            console.status(INFO, line)

    totals = package.totals
    console.section("Estimated context:")
    for label, key in (
        ("Core (L0)", "core"),
        ("Agents", "agent"),
        ("Rules", "rule"),
        ("Workflow", "workflow"),
        ("Stacks", "stack"),
        ("Task", "task"),
    ):
        console.print(f"  {label:<15} {totals[key]:>8,} tokens")
    console.print("  " + "-" * 32)
    console.print(f"  {'Estimated':<15} {totals['total']:>8,} tokens")
    console.print(f"  {'Budget':<15} {package.limit:>8,} tokens")
    for phase, data in package.phases.items():
        console.print(
            f"  {phase.capitalize():<15} {data['estimated_tokens']:>8,} / {data['budget']:,}"
        )
    status_level = PASS if package.status == "OK" else WARN
    console.print()
    console.status(status_level, f"Status: {package.status}")
    for violation in package.violations:
        console.print(console.style(f"    -> {violation}", "dim"))
    if package.status != "OK":
        console.print(
            "    -> Narrow the task or rely on rule slices; never drop security or tests."
        )
    console.print()
    console.print(f"Full context (everything installed): {_fmt(package.full_context_tokens)}")
    console.print(f"Estimated reduction: {package.reduction_percentage}%")
    specialists = [d for d in package.decisions.values() if d.installed and d.layer in ("L1", "L3")]
    loaded = sum(1 for d in specialists if d.status == LOADED)
    console.print(f"Specialists loaded: {loaded} of {len(specialists)} installed")
    metrics = package.metrics()
    console.print(
        f"Metrics: {metrics['selected_nodes']} selected nodes, "
        f"{metrics['skipped_nodes']} skipped, routing time "
        f"{metrics['routing_time_ms']} ms"
    )
    for warning in package.warnings:
        console.status(INFO, warning)
    console.print(console.style(ESTIMATION_NOTE, "dim"))


def _with_rank(reason: str, item: Any) -> str:
    """Graph mode: show relevance, score and the ranking reasons (why it has that score)."""
    if item.rank is None or item.kind == "core":
        return reason
    why = "; ".join(item.rank.reasons) if item.rank.reasons else reason
    return f"[{item.relevance}, score {item.rank.value:.2f}] {why}"
