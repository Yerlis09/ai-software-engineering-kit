"""Knowledge Graph: a derived, regenerable map of the kit's knowledge.

The graph is NOT a source of truth. It is built from ``catalog/*.json``, ``profiles/*.json``
and the installed knowledge files, saved as ``.ai/context/graph.json`` and can be deleted
and rebuilt at any time (``ai-project context --rebuild-graph``). It is data only: it is
parsed and validated, never executed.

Traversal is iterative (no recursion), bounded by ``max_depth`` and a best-weight map, so a
malformed graph can never loop forever.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ai_project.context_index import estimate_tokens, find_cycle, knowledge_path, split_sections
from ai_project.errors import KitError
from ai_project.paths import safe_join

GRAPH_PATH = ".ai/context/graph.json"
GRAPH_SCHEMA = 1
NODE_TYPES = (
    "TASK",
    "AGENT",
    "RULE",
    "WORKFLOW",
    "STACK",
    "TECHNOLOGY",
    "DATABASE",
    "TOOL",
    "PROFILE",
    "PROJECT",
    "FILE",
    "CONCEPT",
    "INTEGRATION",
)
EDGE_TYPES = (
    "requires",
    "recommends",
    "optional",
    "depends_on",
    "conflicts_with",
    "related_to",
    "implemented_by",
    "validated_by",
    "uses",
    "extends",
    "specializes",
    "belongs_to",
)
# Edges that express "cannot work without": cycles among them are errors.
DEPENDENCY_EDGES = frozenset({"requires", "depends_on", "specializes"})
LEVEL_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}
ROOT_FILES = ("AGENTS.md", ".ai/context/project.md")

_NODE_ID = re.compile(r"^[a-z]+\.[a-z0-9][a-z0-9_.-]{0,100}$")


class GraphError(KitError):
    """The graph file is missing, unreadable or invalid (recoverable: rebuild it)."""


@dataclass(frozen=True)
class Node:
    id: str
    type: str
    name: str
    path: str | None = None
    layer: str | None = None
    tokens: int | None = None
    lines: tuple[int, int] | None = None
    installed: bool = True

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "type": self.type, "name": self.name}
        for key in ("path", "layer", "tokens"):
            if getattr(self, key) is not None:
                data[key] = getattr(self, key)
        if self.lines is not None:
            data["lines"] = list(self.lines)
        if not self.installed:
            data["installed"] = False
        return data


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    weight: float

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.source, "to": self.target, "type": self.type, "weight": self.weight}


@dataclass
class Graph:
    nodes: dict[str, Node]
    edges: list[Edge]
    fingerprint: str
    kit_version: str
    _out: dict[str, list[Edge]] = field(default_factory=dict, repr=False)
    _in: dict[str, list[Edge]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.edges = sorted(set(self.edges), key=lambda e: (e.source, e.target, e.type))
        for edge in self.edges:
            self._out.setdefault(edge.source, []).append(edge)
            self._in.setdefault(edge.target, []).append(edge)

    def outgoing(self, node_id: str, types: Iterable[str] | None = None) -> list[Edge]:
        wanted = set(types) if types else None
        return [e for e in self._out.get(node_id, []) if wanted is None or e.type in wanted]

    def incoming(self, node_id: str, types: Iterable[str] | None = None) -> list[Edge]:
        wanted = set(types) if types else None
        return [e for e in self._in.get(node_id, []) if wanted is None or e.type in wanted]

    def stats(self) -> dict[str, Any]:
        node_types: dict[str, int] = {}
        edge_types: dict[str, int] = {}
        for node in self.nodes.values():
            node_types[node.type] = node_types.get(node.type, 0) + 1
        for edge in self.edges:
            edge_types[edge.type] = edge_types.get(edge.type, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_types": dict(sorted(node_types.items())),
            "edge_types": dict(sorted(edge_types.items())),
        }

    def to_json(self) -> str:
        """Deterministic, compact, one node/edge per line, no timestamps (stable Git diffs)."""

        def dumps(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        nodes = [dumps(n.to_dict()) for n in sorted(self.nodes.values(), key=lambda n: n.id)]
        edges = [dumps(e.to_dict()) for e in self.edges]
        head = {
            "schema_version": GRAPH_SCHEMA,
            "kit_version": self.kit_version,
            "source_fingerprint": self.fingerprint,
            "note": "Derived from agents/, rules/, workflows/, stacks/, profiles/, catalog/. "
            "Do not edit: regenerate with 'ai-project context --rebuild-graph'.",
        }
        lines = ["{"]
        lines += [
            f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()
        ]
        lines.append('  "nodes": [')
        lines += [f"    {n}," for n in nodes[:-1]] + [f"    {nodes[-1]}"] if nodes else []
        lines.append("  ],")
        lines.append('  "edges": [')
        lines += [f"    {e}," for e in edges[:-1]] + [f"    {edges[-1]}"] if edges else []
        lines.append("  ]")
        lines.append("}")
        return "\n".join(lines) + "\n"


# --- Fingerprint ---------------------------------------------------------------------------
def source_fingerprint(
    meta: Mapping[str, Any],
    kit_version: str,
    selection: Mapping[str, Any],
    knowledge_hashes: Mapping[str, str],
) -> str:
    """Hash of everything the graph is derived from. A different value means 'stale'."""
    payload = {
        "meta": meta,
        "kit_version": kit_version,
        "selection": selection,
        "files": {p: h for p, h in sorted(knowledge_hashes.items()) if p.startswith(".ai/")},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def knowledge_hash_paths(hashes: Mapping[str, str]) -> dict[str, str]:
    """Keep only knowledge files (agents, rules, workflows, stacks): the graph's inputs."""
    prefixes = (".ai/agents/", ".ai/rules/", ".ai/workflows/", ".ai/stacks/")
    return {p: h for p, h in hashes.items() if p.startswith(prefixes)}


# --- Build -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class GraphSources:
    """Everything the graph is derived from (sources of truth), already loaded."""

    meta: Mapping[str, Any]
    profiles: Mapping[str, Any]  # name -> Profile
    technologies: Mapping[str, Any]  # key -> Option
    databases: Mapping[str, Any]
    deployments: Mapping[str, Any]
    assistants: Mapping[str, Any]
    selection: Mapping[str, Any]  # profile, technology, database, deployment, assistants
    project_name: str
    files: Mapping[str, str]  # installed knowledge + core files: path -> content
    kit_version: str
    knowledge_hashes: Mapping[str, str]


def graph_sources(
    catalog: Any,
    selection: Mapping[str, Any],
    project_name: str,
    files: Mapping[str, str],
    knowledge_hashes: Mapping[str, str],
    kit_version: str,
) -> GraphSources:
    """Assemble the sources of truth from a loaded ``Catalog``."""
    return GraphSources(
        meta=catalog.routing,
        profiles=catalog.profiles,
        technologies=catalog.technologies,
        databases=catalog.databases,
        deployments=catalog.deployments,
        assistants=catalog.assistants,
        selection=dict(selection),
        project_name=project_name,
        files=files,
        kit_version=kit_version,
        knowledge_hashes=knowledge_hash_paths(knowledge_hashes),
    )


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def build_graph(src: GraphSources) -> Graph:
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    meta = src.meta

    def node(node_id: str, node_type: str, name: str, **kw: Any) -> str:
        nodes[node_id] = Node(node_id, node_type, name, **kw)
        return node_id

    def edge(source: str, target: str, edge_type: str, weight: float) -> None:
        if source in nodes and target in nodes:
            edges.append(Edge(source, target, edge_type, round(float(weight), 3)))

    def knowledge(kind: str, item_id: str) -> dict[str, Any]:
        path = knowledge_path(kind, item_id)
        if path in src.files:
            return {"path": path, "tokens": estimate_tokens(src.files[path])}
        return {"installed": False}

    # Knowledge nodes ---------------------------------------------------------------------
    for agent_id, spec in meta.get("agents", {}).items():
        node(
            f"agent.{agent_id}",
            "AGENT",
            spec.get("summary", agent_id),
            layer=spec.get("layer"),
            **knowledge("agents", agent_id),
        )
    for rule_id in meta.get("rules", {}):
        node(
            f"rule.{rule_id}", "RULE", f"{rule_id} rules", layer="L1", **knowledge("rules", rule_id)
        )
    for workflow_id in meta.get("workflows", {}):
        node(
            f"workflow.{workflow_id}",
            "WORKFLOW",
            workflow_id,
            layer="L1",
            **knowledge("workflows", workflow_id),
        )
    for stack_id in meta.get("stacks", {}):
        node(f"stack.{stack_id}", "STACK", stack_id, layer="L2", **knowledge("stacks", stack_id))
    for task_id in meta.get("tasks", {}):
        node(f"task.{task_id}", "TASK", task_id.replace("_", " "))
    for tool_id, spec in meta.get("tools", {}).items():
        node(f"tool.{tool_id}", "TOOL", spec.get("name", tool_id))

    # Concepts: H2 sections of installed rule files (used for slicing) ------------------------
    for rule_id in meta.get("rules", {}):
        path = knowledge_path("rules", rule_id)
        if path not in src.files:
            continue
        always = {
            h for h, s in meta["rules"][rule_id].get("sections", {}).items() if s.get("always")
        }
        for section in split_sections(src.files[path]):
            if not section.heading:
                continue
            concept = node(
                f"concept.{rule_id}.{slug(section.heading)}",
                "CONCEPT",
                section.heading,
                path=path,
                lines=(section.start, section.end),
                tokens=section.tokens,
            )
            edge(
                f"rule.{rule_id}", concept, "related_to", 0.9 if section.heading in always else 0.6
            )

    # Catalog nodes ---------------------------------------------------------------------------
    for name, profile in src.profiles.items():
        node(f"profile.{name}", "PROFILE", profile.title)
    for key, option in src.technologies.items():
        node(f"technology.{key}", "TECHNOLOGY", option.title)
    for key, option in src.deployments.items():
        node(f"technology.deploy-{key}", "TECHNOLOGY", option.title)
    for key, option in src.databases.items():
        node(f"database.{key}", "DATABASE", option.title)
    for key, option in src.assistants.items():
        node(
            f"integration.{key}",
            "INTEGRATION",
            option.title,
            installed=key in src.selection.get("assistants", []),
        )
    for path, name in (("AGENTS.md", "AGENTS.md"), (".ai/context/project.md", "Project context")):
        if path in src.files:
            node(
                f"file.{slug(path)}",
                "FILE",
                name,
                path=path,
                layer="L0",
                tokens=estimate_tokens(src.files[path]),
            )
    project = node(f"project.{slug(src.project_name)}", "PROJECT", src.project_name)

    # Edges -----------------------------------------------------------------------------------
    for agent_id, spec in meta.get("agents", {}).items():
        a = f"agent.{agent_id}"
        for target, level in spec.get("requires", {}).items():
            edge(a, f"agent.{target}", "requires", LEVEL_WEIGHT.get(level, 0.7))
        for target in spec.get("recommended", []):
            edge(a, f"agent.{target}", "recommends", 0.4)
        for target in spec.get("optional", []):
            edge(a, f"agent.{target}", "optional", 0.2)
    for rule_id, spec in meta.get("rules", {}).items():
        for owner in spec.get("agents", []):
            edge(f"rule.{rule_id}", f"agent.{owner}", "belongs_to", 0.8)
    domains = meta.get("domains", {})
    for stack_id, spec in meta.get("stacks", {}).items():
        s = f"stack.{stack_id}"
        for domain in spec.get("domains", []):
            for owner in domains.get(domain, []):
                edge(s, f"agent.{owner}", "implemented_by", 0.6)
        for target in [*spec.get("depends_on", []), *spec.get("companions", [])]:
            edge(s, f"stack.{target}", "depends_on", 0.9)
        for target in spec.get("specializes", []):
            edge(s, f"stack.{target}", "specializes", 1.0)
        for target, weight in spec.get("related", {}).items():
            edge(s, f"stack.{target}", "related_to", weight)
        for target in spec.get("conflicts", []):
            edge(s, f"stack.{target}", "conflicts_with", 0.2)
    for task_id, spec in meta.get("tasks", {}).items():
        t = f"task.{task_id}"
        for target in spec.get("requires", []):
            edge(t, f"agent.{target}", "requires", 1.0)
        for target, weight in spec.get("recommends", {}).items():
            edge(t, f"agent.{target}", "recommends", weight)
        if spec.get("workflow"):
            edge(t, f"workflow.{spec['workflow']}", "related_to", 1.0)
    for tool_id, spec in meta.get("tools", {}).items():
        for stack_id in spec.get("stacks", []):
            edge(f"tool.{tool_id}", f"stack.{stack_id}", "belongs_to", 1.0)
        for agent_id in spec.get("validates", []):
            edge(f"agent.{agent_id}", f"tool.{tool_id}", "validated_by", 0.5)
    for name, profile in src.profiles.items():
        p = f"profile.{name}"
        for agent_id in profile.agents:
            edge(p, f"agent.{agent_id}", "requires", 1.0)
        for agent_id in profile.agents_if_database:
            edge(p, f"agent.{agent_id}", "optional", 0.8)
        for rule_id in profile.rules:
            edge(p, f"rule.{rule_id}", "requires", 0.6)
        for workflow_id in profile.workflows:
            edge(p, f"workflow.{workflow_id}", "requires", 0.6)
        for tech in profile.technologies:
            edge(p, f"technology.{tech}", "uses", 0.5)
    for key, option in src.technologies.items():
        for stack_id in option.stacks:
            edge(f"technology.{key}", f"stack.{stack_id}", "uses", 0.9)
    for key, option in src.deployments.items():
        for stack_id in option.stacks:
            edge(f"technology.deploy-{key}", f"stack.{stack_id}", "uses", 0.7)
    for key, option in src.databases.items():
        for stack_id in option.stacks:
            edge(f"database.{key}", f"stack.{stack_id}", "uses", 0.9)
    for key in src.assistants:
        edge(f"integration.{key}", "file.agents-md", "uses", 1.0)

    sel = src.selection
    edge(project, f"profile.{sel.get('profile')}", "belongs_to", 1.0)
    edge(project, f"technology.{sel.get('technology')}", "uses", 1.0)
    edge(project, f"database.{sel.get('database')}", "uses", 1.0)
    edge(project, f"technology.deploy-{sel.get('deployment')}", "uses", 1.0)
    for assistant in sel.get("assistants", []):
        edge(project, f"integration.{assistant}", "uses", 1.0)
    for file_node in ("file.agents-md", "file.ai-context-project-md"):
        edge(project, file_node, "requires", 1.0)

    fingerprint = source_fingerprint(meta, src.kit_version, dict(sel), src.knowledge_hashes)
    return Graph(nodes, edges, fingerprint, src.kit_version)


# --- Load / save / validate --------------------------------------------------------------------
def load_graph(text: str) -> Graph:
    """Parse and structurally validate graph JSON. Raises GraphError (recoverable)."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise GraphError(f"graph.json is not valid JSON: {exc}") from None
    issues = validate_graph_data(data)
    if issues:
        raise GraphError("Invalid knowledge graph: " + "; ".join(issues[:5]))
    nodes = {}
    for raw in data["nodes"]:
        lines = raw.get("lines")
        nodes[raw["id"]] = Node(
            raw["id"],
            raw["type"],
            str(raw.get("name", "")),
            raw.get("path"),
            raw.get("layer"),
            raw.get("tokens"),
            tuple(lines) if lines else None,
            raw.get("installed", True),
        )
    edges = [Edge(e["from"], e["to"], e["type"], float(e["weight"])) for e in data["edges"]]
    return Graph(nodes, edges, str(data["source_fingerprint"]), str(data["kit_version"]))


def validate_graph_data(data: Any) -> list[str]:
    """Structure, node/edge types, duplicate IDs, references, weights, path syntax, cycles."""
    if not isinstance(data, dict):
        return ["top level must be an object"]
    issues: list[str] = []
    if data.get("schema_version") != GRAPH_SCHEMA:
        issues.append(f"unknown schema_version {data.get('schema_version')!r}")
    for key in ("source_fingerprint", "kit_version"):
        if not isinstance(data.get(key), str):
            issues.append(f"missing {key}")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return [*issues, "'nodes' and 'edges' must be lists"]
    ids: set[str] = set()
    for raw in nodes:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            issues.append("node without a string id")
            continue
        node_id = raw["id"]
        if not _NODE_ID.match(node_id):
            issues.append(f"invalid node id {node_id!r}")
        if node_id in ids:
            issues.append(f"duplicate node id {node_id!r}")
        ids.add(node_id)
        if raw.get("type") not in NODE_TYPES:
            issues.append(f"invalid node type {raw.get('type')!r} for {node_id}")
        path = raw.get("path")
        if path is not None and not _path_syntax_ok(path):
            issues.append(f"invalid path {path!r} for {node_id}")
        lines = raw.get("lines")
        if lines is not None and not (
            isinstance(lines, list)
            and len(lines) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in lines)
            and lines[0] <= lines[1]
        ):
            issues.append(f"invalid line range for {node_id}")
    dependency_graph: dict[str, list[str]] = {}
    for raw in edges:
        if not isinstance(raw, dict):
            issues.append("edge must be an object")
            continue
        source, target, edge_type = raw.get("from"), raw.get("to"), raw.get("type")
        if edge_type not in EDGE_TYPES:
            issues.append(f"invalid edge type {edge_type!r} ({source} -> {target})")
        for end in (source, target):
            if end not in ids:
                issues.append(f"edge references missing node {end!r}")
        weight = raw.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
            issues.append(f"invalid weight {weight!r} ({source} -> {target})")
        if edge_type in DEPENDENCY_EDGES and isinstance(source, str) and isinstance(target, str):
            dependency_graph.setdefault(source, []).append(target)
            dependency_graph.setdefault(target, [])
    cycle = find_cycle(dependency_graph)
    if cycle:
        issues.append("dependency cycle: " + " -> ".join(cycle))
    return issues


def _path_syntax_ok(path: Any) -> bool:
    if not isinstance(path, str) or "\\" in path or "\x00" in path or path.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", path) or any(p in ("", ".", "..") for p in path.split("/")):
        return False
    return path in ROOT_FILES or path.startswith(".ai/")


def validate_graph_paths(graph: Graph, root: Path) -> list[str]:
    """Every installed node path must stay inside the project (symlinks resolved) and exist.

    Measured on Windows: resolving every node path cost ~30 ms per run. Each distinct parent
    directory is resolved once instead (same containment guarantee), and a file that is itself
    a symlink still gets a full ``safe_join`` resolution.
    """
    issues: list[str] = []
    parents: dict[str, Path | None] = {}
    for node in sorted(graph.nodes.values(), key=lambda n: n.id):
        if node.path is None:
            continue
        parent_rel, _, name = node.path.rpartition("/")
        try:
            if parent_rel not in parents:
                parents[parent_rel] = safe_join(root, parent_rel) if parent_rel else root.resolve()
            parent = parents[parent_rel]
            if parent is None or not name or name in (".", ".."):
                raise KitError(f"Unsafe path rejected: {node.path!r}")
            target = parent / name
            if target.is_symlink():
                target = safe_join(root, node.path)  # full resolution for symlinked files
        except KitError as exc:
            parents.setdefault(parent_rel, None)
            issues.append(f"{node.id}: {exc}")
            continue
        if node.installed and not target.is_file():
            issues.append(f"{node.id}: broken path {node.path}")
    return issues


def save_graph(root: Path, graph: Graph) -> Path:
    target = safe_join(root, GRAPH_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(graph.to_json())
    return target


def rebuild_graph(src: GraphSources, root: Path | None = None) -> Graph:
    """Build, validate (structure, cycles, and paths when a project root is given), save."""
    graph = build_graph(src)
    issues = validate_graph_data(json.loads(graph.to_json()))
    if root is not None:
        issues += validate_graph_paths(graph, root)
    if issues:
        raise GraphError("Rebuilt graph is invalid: " + "; ".join(issues[:5]))
    if root is not None:
        save_graph(root, graph)
    return graph


# --- Traversal ---------------------------------------------------------------------------------
def traverse_graph(
    graph: Graph,
    seeds: Mapping[str, float],
    max_depth: int = 3,
    edge_types: Iterable[str] | None = None,
) -> dict[str, tuple[float, str]]:
    """Weighted breadth-first traversal from seed nodes.

    Returns ``node -> (best weight, node it was reached from)``. Weight = product of edge
    weights along the path. Iterative, depth-bounded, and a node is re-expanded only when a
    strictly better weight is found, so it terminates on any graph, cyclic or not.
    """
    types = set(edge_types) if edge_types else None
    best: dict[str, tuple[float, str]] = {s: (w, s) for s, w in seeds.items() if s in graph.nodes}
    queue = deque((s, w, 0) for s, (w, _) in sorted(best.items()))
    while queue:
        node_id, weight, depth = queue.popleft()
        if depth >= max_depth or weight < best.get(node_id, (0.0, ""))[0]:
            continue
        for e in graph.outgoing(node_id, types):
            if e.type == "conflicts_with":
                continue
            reached = round(weight * e.weight, 6)
            if reached > best.get(e.target, (0.0, ""))[0]:
                best[e.target] = (reached, node_id)
                queue.append((e.target, reached, depth + 1))
    return best


def expand_dependencies(graph: Graph, start: Iterable[str], max_depth: int = 10) -> list[str]:
    """Transitive closure over requires/depends_on/specializes, in deterministic BFS order.
    Example: stack.fastapi -> stack.python. Visited set + depth bound: never loops."""
    order: list[str] = []
    seen: set[str] = set()
    queue = deque((s, 0) for s in sorted(start) if s in graph.nodes)
    while queue:
        node_id, depth = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        order.append(node_id)
        if depth >= max_depth:
            continue
        for e in graph.outgoing(node_id, DEPENDENCY_EDGES):
            if e.target not in seen:
                queue.append((e.target, depth + 1))
    return order


# --- Project graph status (shared by `context` and `doctor`) -----------------------------------
GRAPH_STALE_MESSAGE = "Knowledge graph is missing/stale. Rebuild recommended with --rebuild-graph."


@dataclass
class GraphCheck:
    state: str  # ok | missing | invalid | stale
    graph: Graph | None
    issues: list[str]


def expected_fingerprint(meta: Mapping[str, Any], kit_version: str, lock: Any) -> str:
    """Fingerprint a graph built today from this project's lock file would carry."""
    return source_fingerprint(
        meta, kit_version, dict(lock.selection), knowledge_hash_paths(lock.managed)
    )


def check_project_graph(
    root: Path, meta: Mapping[str, Any], kit_version: str, lock: Any
) -> GraphCheck:
    """Load ``.ai/context/graph.json`` and classify it. Never raises for a bad graph."""
    path = safe_join(root, GRAPH_PATH)
    if not path.is_file():
        return GraphCheck("missing", None, [f"{GRAPH_PATH} not found"])
    try:
        graph = load_graph(path.read_text(encoding="utf-8"))
    except (GraphError, OSError, UnicodeDecodeError) as exc:
        return GraphCheck("invalid", None, [str(exc)])
    issues = validate_graph_paths(graph, root)
    if issues:
        return GraphCheck("invalid", graph, issues)
    if lock is not None and graph.fingerprint != expected_fingerprint(meta, kit_version, lock):
        return GraphCheck("stale", graph, ["source fingerprint differs from the current sources"])
    return GraphCheck("ok", graph, [])
