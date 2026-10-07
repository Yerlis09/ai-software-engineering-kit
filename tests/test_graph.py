"""Knowledge Graph: build, save/load, validation, traversal, dependency expansion, security."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_project import __version__
from ai_project.catalog import Catalog, Selection
from ai_project.context_graph import (
    EDGE_TYPES,
    GRAPH_PATH,
    NODE_TYPES,
    Edge,
    Graph,
    GraphError,
    Node,
    build_graph,
    expand_dependencies,
    graph_sources,
    load_graph,
    rebuild_graph,
    save_graph,
    source_fingerprint,
    traverse_graph,
    validate_graph_data,
    validate_graph_paths,
)
from ai_project.generator import build_plan
from ai_project.lockfile import content_hash
from ai_project.paths import kit_root


def _plan_files(
    profile: str = "backend-api", technology: str = "python-fastapi", database: str = "postgresql"
) -> tuple[Catalog, Selection, dict[str, str]]:
    catalog = Catalog(kit_root())
    selection = Selection(profile, technology, database, "kubernetes", ("claude-code",))
    plan = build_plan(catalog, catalog.resolve(selection), selection, {"project_name": "graph-app"})
    return catalog, selection, {p.path: p.content for p in plan}


def _graph(**kw) -> Graph:
    catalog, selection, files = _plan_files(**kw)
    hashes = {p: content_hash(c) for p, c in files.items()}
    return build_graph(
        graph_sources(catalog, selection.to_dict(), "graph-app", files, hashes, __version__)
    )


@pytest.fixture(scope="module")
def graph() -> Graph:
    return _graph()


def _data(graph: Graph) -> dict:
    return json.loads(graph.to_json())


# Build -----------------------------------------------------------------------------------------
def test_graph_has_all_node_types(graph: Graph) -> None:
    assert set(graph.stats()["node_types"]) == set(NODE_TYPES)
    assert set(graph.stats()["edge_types"]) <= set(EDGE_TYPES)


def test_graph_is_derived_from_sources(graph: Graph) -> None:
    backend = graph.nodes["agent.02-backend"]
    assert backend.path == ".ai/agents/02-backend.md" and backend.tokens and backend.installed
    assert graph.nodes["agent.01-frontend"].installed is False  # not in backend-api profile
    targets = {(e.target, e.type) for e in graph.outgoing("agent.02-backend")}
    assert ("agent.04-architecture", "requires") in targets
    assert ("agent.09-security", "recommends") in targets
    profile_edges = {e.target for e in graph.outgoing("profile.backend-api", ["requires"])}
    assert "agent.02-backend" in profile_edges
    assert ("stack.python", "specializes") in {
        (e.target, e.type) for e in graph.outgoing("stack.fastapi")
    }
    assert ("stack.docker", "depends_on") in {
        (e.target, e.type) for e in graph.outgoing("stack.kubernetes")
    }


def test_rule_sections_become_concepts_with_line_ranges(graph: Graph) -> None:
    concepts = [graph.nodes[e.target] for e in graph.outgoing("rule.security", ["related_to"])]
    names = {c.name for c in concepts}
    assert {"Authentication and authorization", "Secrets management"} <= names
    lines = (kit_root() / "rules/security.md").read_text("utf-8").splitlines()
    for concept in concepts:
        assert concept.type == "CONCEPT" and concept.lines
        assert lines[concept.lines[0] - 1] == f"## {concept.name}"


def test_graph_json_is_deterministic_and_has_no_timestamp(graph: Graph) -> None:
    assert graph.to_json() == _graph().to_json()
    text = graph.to_json()
    assert "created" not in text and "timestamp" not in text
    assert json.loads(text)["source_fingerprint"] == graph.fingerprint


def test_save_and_load_round_trip(tmp_path: Path, graph: Graph) -> None:
    path = save_graph(tmp_path, graph)
    assert path == (tmp_path / GRAPH_PATH).resolve()
    loaded = load_graph(path.read_text("utf-8"))
    assert loaded.to_json() == graph.to_json()


def test_rebuild_validates_paths_and_saves(tmp_path: Path) -> None:
    catalog, selection, files = _plan_files()
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    hashes = {p: content_hash(c) for p, c in files.items()}
    src = graph_sources(catalog, selection.to_dict(), "graph-app", files, hashes, __version__)
    graph = rebuild_graph(src, tmp_path)
    assert (tmp_path / GRAPH_PATH).is_file() and graph.stats()["nodes"] > 100
    (tmp_path / ".ai/agents/02-backend.md").unlink()
    with pytest.raises(GraphError, match="broken path"):
        rebuild_graph(src, tmp_path)


# Fingerprint / staleness ------------------------------------------------------------------------
def test_fingerprint_changes_with_any_source() -> None:
    meta, sel, files = {"agents": {}}, {"profile": "x"}, {".ai/rules/a.md": "h1"}
    base = source_fingerprint(meta, "1.2.0", sel, files)
    assert base == source_fingerprint(meta, "1.2.0", sel, dict(files))
    assert base != source_fingerprint({"agents": {"a": {}}}, "1.2.0", sel, files)
    assert base != source_fingerprint(meta, "1.3.0", sel, files)
    assert base != source_fingerprint(meta, "1.2.0", {"profile": "y"}, files)
    assert base != source_fingerprint(meta, "1.2.0", sel, {".ai/rules/a.md": "h2"})


# Validation -------------------------------------------------------------------------------------
def _mutate(graph: Graph, fn) -> list[str]:
    data = _data(graph)
    fn(data)
    return validate_graph_data(data)


def test_valid_graph_has_no_issues(graph: Graph) -> None:
    assert validate_graph_data(_data(graph)) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda d: d["nodes"].append(dict(d["nodes"][0])), "duplicate node id"),
        (lambda d: d["nodes"][0].update(type="SPACESHIP"), "invalid node type"),
        (lambda d: d["edges"][0].update(type="eats"), "invalid edge type"),
        (
            lambda d: d["edges"].append(
                {"from": "agent.00-master", "to": "agent.ghost", "type": "requires", "weight": 1}
            ),
            "missing node",
        ),
        (lambda d: d["edges"][0].update(weight=7), "invalid weight"),
        (lambda d: d["nodes"][0].update(path="../../secret.txt"), "invalid path"),
        (lambda d: d["nodes"][0].update(path="/etc/passwd"), "invalid path"),
        (lambda d: d["nodes"][0].update(path="C:/Windows/x.md"), "invalid path"),
        (lambda d: d["nodes"][0].update(path="src/app.py"), "invalid path"),
        (lambda d: d["nodes"][0].update(id="Bad ID"), "invalid node id"),
        (lambda d: d.update(schema_version=99), "schema_version"),
        (lambda d: d.update(nodes="x"), "must be lists"),
    ],
)
def test_validation_detects_errors(graph: Graph, mutation, expected: str) -> None:
    issues = _mutate(graph, mutation)
    assert any(expected in issue for issue in issues), issues


def test_cycle_is_detected_with_clear_message(graph: Graph) -> None:
    def add_cycle(d: dict) -> None:
        d["edges"] += [
            {"from": "stack.python", "to": "stack.docker", "type": "depends_on", "weight": 1},
            {"from": "stack.docker", "to": "stack.linux", "type": "requires", "weight": 1},
            {"from": "stack.linux", "to": "stack.python", "type": "specializes", "weight": 1},
        ]

    issues = _mutate(graph, add_cycle)
    assert any(i.startswith("dependency cycle:") and "->" in i for i in issues), issues


@pytest.mark.parametrize("text", ["{not json", "[]", "null", '{"schema_version": 1}', ""])
def test_corrupted_graph_raises_recoverable_error(text: str) -> None:
    with pytest.raises(GraphError):
        load_graph(text)


def test_graph_paths_cannot_escape_through_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret", encoding="utf-8")
    root = tmp_path / "project"
    (root / ".ai").mkdir(parents=True)
    try:
        os.symlink(outside, root / ".ai" / "agents", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this platform/user")
    graph = Graph(
        {"agent.x": Node("agent.x", "AGENT", "x", path=".ai/agents/secret.md")},
        [],
        "f",
        __version__,
    )
    issues = validate_graph_paths(graph, root)
    assert issues and "escapes" in issues[0]


def test_broken_path_is_reported(tmp_path: Path) -> None:
    graph = Graph(
        {"agent.x": Node("agent.x", "AGENT", "x", path=".ai/agents/x.md")}, [], "f", __version__
    )
    assert "broken path" in validate_graph_paths(graph, tmp_path)[0]


def test_graph_data_is_never_executed(graph: Graph) -> None:
    data = _data(graph)
    data["nodes"][0]["name"] = "__import__('os').system('echo pwned')"
    loaded = load_graph(json.dumps(data))  # names are plain strings, never evaluated
    assert loaded.nodes[data["nodes"][0]["id"]].name.startswith("__import__")


# Traversal and dependency expansion -------------------------------------------------------------
def _toy() -> Graph:
    nodes = {i: Node(i, "AGENT", i) for i in ("agent.a", "agent.b", "agent.c", "agent.d")}
    edges = [
        Edge("agent.a", "agent.b", "requires", 0.5),
        Edge("agent.b", "agent.c", "related_to", 0.5),
        Edge("agent.c", "agent.a", "related_to", 1.0),  # non-dependency cycle: allowed
        Edge("agent.c", "agent.d", "related_to", 1.0),
        Edge("agent.a", "agent.d", "conflicts_with", 1.0),
    ]
    return Graph(nodes, edges, "f", __version__)


def test_traversal_weights_depth_and_termination() -> None:
    reached = traverse_graph(_toy(), {"agent.a": 1.0}, max_depth=3)
    assert reached["agent.b"] == (0.5, "agent.a")
    assert reached["agent.c"] == (0.25, "agent.b")
    assert reached["agent.d"] == (0.25, "agent.c")  # conflicts_with is not followed
    assert reached["agent.a"][0] == 1.0  # the cycle back to the seed does not loop
    assert "agent.c" not in traverse_graph(_toy(), {"agent.a": 1.0}, max_depth=1)


def test_dependency_expansion(graph: Graph) -> None:
    assert expand_dependencies(graph, ["stack.fastapi"]) == ["stack.fastapi", "stack.python"]
    assert "stack.docker" in expand_dependencies(graph, ["stack.kubernetes"])
    assert "stack.typescript" in expand_dependencies(graph, ["stack.react"])
    closure = expand_dependencies(graph, ["agent.02-backend"])
    assert {"agent.04-architecture", "agent.10-testing"} <= set(closure)


def test_dependency_expansion_terminates_on_cycles() -> None:
    nodes = {i: Node(i, "STACK", i) for i in ("stack.a", "stack.b", "stack.c")}
    edges = [
        Edge("stack.a", "stack.b", "depends_on", 1),
        Edge("stack.b", "stack.c", "requires", 1),
        Edge("stack.c", "stack.a", "specializes", 1),
    ]
    assert expand_dependencies(Graph(nodes, edges, "f", __version__), ["stack.a"]) == [
        "stack.a",
        "stack.b",
        "stack.c",
    ]


# CLI, doctor, fallback, regeneration, derived files (integration) -----------------------------
from conftest import run  # noqa: E402

from ai_project.context_graph import GRAPH_STALE_MESSAGE  # noqa: E402


def _doctor_checks(root: Path) -> dict[str, dict]:
    data = json.loads(run("doctor", "--path", str(root), "--format", "json").out)
    return {c["name"]: c for c in data["checks"] if c["category"] == "Knowledge Graph"}


def _context_json(root: Path, *extra: str) -> dict:
    result = run("context", "--path", str(root), "--json", *extra)
    assert result.code == 0, result.err
    return json.loads(result.out)


def test_init_generates_graph_and_index_as_derived(init_project) -> None:
    root = init_project("derived-app", "--technology", "python-fastapi")
    lock = json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))
    assert sorted(lock["derived_files"]) == [".ai/context/graph.json", ".ai/context/index.json"]
    assert ".ai/context/index.json" not in lock["managed_files"]
    assert ".ai/context/graph.json" not in lock["seed_files"]
    assert (root / ".ai/context/README.md").is_file()
    checks = _doctor_checks(root)
    assert all(c["status"] == "PASS" for c in checks.values()), checks
    assert run("update", "--path", str(root), "--check").code == 0
    assert _context_json(root, "--task", "x")["graph"]["status"] == "loaded"


def test_rebuild_graph_command(init_project) -> None:
    root = init_project("rebuild-app")
    (root / GRAPH_PATH).unlink()
    result = run("context", "--path", str(root), "--rebuild-graph")
    assert result.code == 0, result.err
    assert "AI KNOWLEDGE GRAPH" in result.out and "Graph rebuilt successfully" in result.out
    assert (root / GRAPH_PATH).is_file()
    data = json.loads(run("context", "--path", str(root), "--rebuild-graph", "--json").out)
    assert data["graph_rebuild"]["nodes"] > 100 and data["graph_rebuild"]["previous_state"] == "ok"
    combined = _context_json(root, "--rebuild-graph", "--task", "Fix ClickHouse query")
    assert combined["graph_rebuild"]["edges"] > 0 and combined["mode"] == "graph"


@pytest.mark.parametrize(
    ("damage", "state"),
    [
        (lambda p: p.unlink(), "missing"),
        (lambda p: p.write_text("{not json", encoding="utf-8"), "invalid"),
        (
            lambda p: p.write_text(
                p.read_text("utf-8").replace(
                    '"path":".ai/agents/00-master.md"', '"path":"../../secret.txt"'
                ),
                encoding="utf-8",
            ),
            "invalid",
        ),
        (
            lambda p: p.write_text(
                p.read_text("utf-8").replace('"source_fingerprint": "', '"source_fingerprint": "0'),
                encoding="utf-8",
            ),
            "stale",
        ),
    ],
)
def test_bad_graph_is_rebuilt_in_memory_and_reported(init_project, damage, state: str) -> None:
    root = init_project("bad-graph")
    damage(root / GRAPH_PATH)
    data = _context_json(root, "--task", "Create a FastAPI endpoint for equipment")
    assert data["mode"] == "graph"
    assert data["graph"]["status"] == "rebuilt in memory"
    assert data["graph"]["previous_state"] == state
    assert any(GRAPH_STALE_MESSAGE in w for w in data["warnings"])
    doctor = run("doctor", "--path", str(root))
    assert doctor.code == 0  # graph problems never FAIL
    checks = _doctor_checks(root)
    statuses = {c["status"] for c in checks.values()}
    assert "WARN" in statuses and "FAIL" not in statuses
    assert any("rebuild-graph" in c["hint"] for c in checks.values() if c["status"] == "WARN")


def test_fallback_to_direct_mode_when_graph_cannot_be_built(init_project, monkeypatch) -> None:
    import ai_project.context_cmd as context_cmd

    root = init_project("fallback-app")
    (root / GRAPH_PATH).unlink()

    def broken(*_args, **_kwargs):
        raise GraphError("simulated failure")

    monkeypatch.setattr(context_cmd, "build_graph", broken)
    data = _context_json(root, "--task", "Create a FastAPI endpoint for equipment")
    assert data["mode"] == "direct" and data["graph"]["status"] == "unavailable"
    assert any("direct routing used" in w for w in data["warnings"])
    assert {a["id"] for a in data["selected_agents"]} >= {"02-backend", "10-testing"}


def test_project_without_lock_uses_direct_mode(init_project) -> None:
    root = init_project("nolock-app")
    (root / ".ai/kit.lock.json").unlink()
    data = _context_json(root, "--task", "Fix ClickHouse query")
    assert data["mode"] == "direct"
    assert run("context", "--path", str(root), "--rebuild-graph").code == 1


def test_rebuild_after_a_knowledge_file_is_removed(init_project) -> None:
    root = init_project("escape-app")
    (root / ".ai/agents/02-backend.md").unlink()  # a referenced, installed file disappears
    result = run("context", "--path", str(root), "--rebuild-graph")
    assert result.code == 0  # the file is simply not installed any more: not referenced
    assert "agent.02-backend" not in {
        n["id"]
        for n in json.loads((root / GRAPH_PATH).read_text("utf-8"))["nodes"]
        if n.get("installed", True) and n.get("path")
    }


def test_update_regenerates_derived_files_without_conflicts(init_project) -> None:
    root = init_project("regen-app")
    graph_path, index_path = root / GRAPH_PATH, root / ".ai/context/index.json"
    original = graph_path.read_text("utf-8")
    graph_path.write_text(original.replace('"note"', '"note_local"'), encoding="utf-8")
    index_path.write_text("{}", encoding="utf-8")
    result = run("update", "--path", str(root))
    assert result.code == 0 and "regenerated (derived artefact" in result.out
    assert "CONFLICT" not in result.out
    assert graph_path.read_text("utf-8") == original
    assert not (root / ".ai/context/index.json.kit-new").exists()
    assert not (root / ".ai/context/graph.json.kit-new").exists()


def test_v11_project_migrates_to_derived_files(init_project) -> None:
    """A 1.1 project: index.json was CORE (in managed_files), no graph, no derived list."""
    root = init_project("v11-app")
    lock_path = root / ".ai/kit.lock.json"
    lock = json.loads(lock_path.read_text("utf-8"))
    index_text = (root / ".ai/context/index.json").read_text("utf-8")
    lock["managed_files"][".ai/context/index.json"] = content_hash(index_text)
    lock.pop("derived_files")
    lock["kit_version"] = "1.1.0"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    (root / GRAPH_PATH).unlink()
    assert run("update", "--path", str(root), "--check").code == 1
    result = run("update", "--path", str(root))
    assert result.code == 0 and "CONFLICT" not in result.out, result.out
    migrated = json.loads(lock_path.read_text("utf-8"))
    assert ".ai/context/index.json" not in migrated["managed_files"]
    assert sorted(migrated["derived_files"]) == [".ai/context/graph.json", ".ai/context/index.json"]
    assert (root / GRAPH_PATH).is_file() and (root / ".ai/context/index.json").is_file()
    assert run("update", "--path", str(root), "--check").code == 0


def test_lock_with_escaping_derived_path_is_rejected(init_project) -> None:
    root = init_project("lock-escape")
    lock_path = root / ".ai/kit.lock.json"
    lock = json.loads(lock_path.read_text("utf-8"))
    lock["derived_files"].append("../../outside.json")
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    result = run("update", "--path", str(root))
    assert result.code == 1
