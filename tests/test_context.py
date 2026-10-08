"""Context & Token Optimization: router, index, budget, CLI and update integration."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from conftest import run

from ai_project.catalog import Catalog
from ai_project.context_cmd import ContextOptions, build_package
from ai_project.context_index import (
    build_index,
    estimate_tokens,
    find_cycle,
    read_index,
    slice_text,
    split_sections,
    validate_routing,
)
from ai_project.context_router import (
    DEFAULT_BUDGET,
    HIGH,
    LOW,
    MEDIUM,
    NONE,
    ContextPackage,
    PlanSource,
    ProjectSource,
    Router,
    match_triggers,
    normalize,
    parse_budget,
)
from ai_project.errors import KitError
from ai_project.paths import kit_root

HEALTH = "Add GET /health endpoint to a FastAPI project."
SQLI = "Fix SQL injection vulnerability in customer search."
REACT = "Improve React dashboard performance."


def package(task: str, profile: str = "backend-api", **kw) -> ContextPackage:
    """Route a task for a simulated project with an explicit database and Kubernetes deployment.

    The kit records database and deployment as undecided when they are not chosen; these routing
    scenarios describe a deployed project with a database, so they state both explicitly.
    """
    no_database = profile in ("frontend", "python-automation")
    kw.setdefault("database", "none" if no_database else "postgresql")
    kw.setdefault("deployment", "kubernetes")
    return build_package(ContextOptions(task=task, profile=profile, **kw), Catalog(kit_root()))


def levels(pkg: ContextPackage) -> dict[str, int]:
    return {a: d.level for a, d in pkg.decisions.items()}


def loaded_agents(pkg: ContextPackage) -> set[str]:
    return {i.id for i in pkg.by_kind("agent")} - {"00-master"}


def ids(pkg: ContextPackage, kind: str) -> set[str]:
    return {i.id for i in pkg.by_kind(kind)}


# 1. Task classification ----------------------------------------------------------------------
def test_classification_health_endpoint() -> None:
    lv = levels(package(HEALTH))
    assert lv["02-backend"] == HIGH and lv["10-testing"] == HIGH
    assert lv["04-architecture"] == MEDIUM and lv["09-security"] == LOW
    for agent in ("03-database", "01-frontend", "12-devops", "08-performance", "13-observability"):
        assert lv[agent] == NONE, agent


def test_classification_sql_injection() -> None:
    lv = levels(package(SQLI))
    assert lv["09-security"] == HIGH and lv["03-database"] == HIGH and lv["10-testing"] == HIGH
    assert lv["02-backend"] >= MEDIUM and lv["04-architecture"] == MEDIUM
    assert lv["01-frontend"] == NONE


def test_classification_react_performance() -> None:
    lv = levels(package(REACT, profile="fullstack"))
    assert lv["01-frontend"] == HIGH and lv["08-performance"] == HIGH
    assert lv["10-testing"] == MEDIUM and lv["04-architecture"] == MEDIUM
    assert lv["02-backend"] == NONE and lv["03-database"] == NONE


def test_trigger_matching_rules() -> None:
    text = normalize("Expose new Endpoints for the SQL Server reports; rapid fix")
    hits = dict(match_triggers({"endpoint*": 2, "sql server": 2, "api": 2, "fix": 1}, text))
    assert hits == {"endpoint*": 2, "sql server": 2, "fix": 1}  # "api" is not in "rapid"


# 2-4. Agent, rule and stack selection ------------------------------------------------------------
def test_agent_selection_matches_the_three_reference_cases() -> None:
    assert loaded_agents(package(HEALTH)) == {"02-backend", "04-architecture", "10-testing"}
    assert loaded_agents(package(SQLI)) == {
        "02-backend",
        "03-database",
        "04-architecture",
        "09-security",
        "10-testing",
    }
    assert loaded_agents(package(REACT, profile="fullstack")) == {
        "01-frontend",
        "04-architecture",
        "08-performance",
        "10-testing",
    }


def direct_package(task: str, profile: str = "backend-api") -> ContextPackage:
    """Direct-mode routing: the mandatory fallback when no graph is available."""
    files = _files_for(profile)
    return Router(
        Catalog(kit_root()).routing, PlanSource(files, "p", profile), dict(DEFAULT_BUDGET)
    ).route(task)


def test_rule_selection_and_targeted_security_review() -> None:
    # Direct mode: metadata-only selection.
    assert ids(direct_package(HEALTH), "rule") == {"coding", "architecture", "testing"}
    # Graph mode: the 'api' task category recommends security, so an API task also gets the
    # targeted security rule sections (sliced), never the whole agent.
    graph_rules = {i.id: i for i in package(HEALTH).by_kind("rule")}
    assert set(graph_rules) == {"coding", "architecture", "testing", "security"}
    assert graph_rules["security"].requested_by == ["task.api"]
    assert graph_rules["security"].sections is not None
    pkg = package("Add customer creation endpoint")
    assert pkg.decisions["09-security"].status == "targeted"
    assert "09-security" not in loaded_agents(pkg)
    security = next(i for i in pkg.by_kind("rule") if i.id == "security")
    headings = {s["heading"] for s in security.sections}
    assert "Input validation and output encoding" in headings
    assert "Authentication and authorization" not in headings
    assert security.phase == "review"


def test_stack_selection() -> None:
    assert ids(package(HEALTH), "stack") == {"python", "fastapi"}
    assert ids(package(SQLI), "stack") == {"python", "fastapi", "postgresql"}
    react = ids(package(REACT, profile="fullstack"), "stack")
    assert react == {"react", "typescript"}
    assert not react & {"fastapi", "python", "postgresql", "kubernetes"}
    assert ids(package("Add unit tests for the parser", profile="python-automation"), "stack") == {
        "python"
    }  # language fallback


def test_devops_task_selects_infrastructure_guides() -> None:
    pkg = package("Fix the Kubernetes deployment probes")
    assert "12-devops" in loaded_agents(pkg)
    assert {"docker", "kubernetes"} <= ids(pkg, "stack")


# 5. Token estimation ---------------------------------------------------------------------------
def test_token_estimation_is_characters_over_four() -> None:
    assert [estimate_tokens(t) for t in ("", "abcd", "abcde", "x" * 400)] == [0, 1, 2, 100]


def test_item_estimates_match_file_contents() -> None:
    pkg = package(HEALTH)
    source_files = PlanSource({}, None, None)  # sanity: estimates are not cached guesses
    assert source_files.cached_tokens("AGENTS.md") is None
    agent = next(i for i in pkg.by_kind("agent") if i.id == "02-backend")
    text = (kit_root() / "agents" / "02-backend.md").read_text("utf-8").replace("\r\n", "\n")
    assert agent.tokens == estimate_tokens(text)


# 6. Budget validation ----------------------------------------------------------------------------
def test_budget_defaults_and_template_agree() -> None:
    template = (kit_root() / "templates/base/.ai/context/budget.json").read_text("utf-8")
    assert parse_budget(template) == DEFAULT_BUDGET
    assert parse_budget(None) == DEFAULT_BUDGET
    assert parse_budget('{"review_budget": 7}')["review_budget"] == 7


@pytest.mark.parametrize(
    "text",
    [
        '{"default_token_budget": -1}',
        '{"planning_budget": "big"}',
        '{"planning_budget": true}',
        '{"unknown": 1}',
        "[]",
        "{not json",
    ],
)
def test_invalid_budget_is_rejected(text: str) -> None:
    with pytest.raises(KitError):
        parse_budget(text)


# 7. Context package ----------------------------------------------------------------------------
def test_package_contains_required_fields() -> None:
    data = package(HEALTH).to_dict()
    for key in (
        "task",
        "selected_agents",
        "selected_rules",
        "selected_workflows",
        "selected_stacks",
        "project_context",
        "estimated_tokens",
        "budget",
        "skipped_context",
        "reasons",
        "deduplicated",
        "full_context_tokens",
        "reduction_percentage",
        "estimation",
    ):
        assert key in data, key
    assert data["selected_workflows"][0]["id"] == "new-feature"
    assert "estimate" in data["estimation"].lower()
    assert data["estimated_tokens"]["total"] == sum(
        v for k, v in data["estimated_tokens"].items() if k != "total"
    )


def test_phases() -> None:
    pkg = package(SQLI)
    phase = {i.id: i.phase for i in pkg.items.values()}
    assert phase["04-architecture"] == "planning" and phase["bug-fix"] == "planning"
    assert phase["09-security"] == "review" and phase["02-backend"] == "implementation"


# 8. Context slicing -------------------------------------------------------------------------------
def test_split_sections_ignores_headings_in_code_blocks() -> None:
    text = "# T\nintro\n## A\na\n```\n## not a heading\n```\n## B\nb\n"
    sections = split_sections(text)
    assert [s.heading for s in sections] == ["", "A", "B"]
    assert slice_text(text, [sections[2]]) == "## B\nb"


def test_rule_slices_point_to_real_sections() -> None:
    pkg = package(SQLI)
    rule = next(i for i in pkg.by_kind("rule") if i.id == "security")
    lines = (kit_root() / "rules/security.md").read_text("utf-8").splitlines()
    for section in rule.sections:
        start, _ = section["lines"]
        if section["heading"] != "(preamble)":
            assert lines[start - 1] == f"## {section['heading']}"
    assert rule.tokens < estimate_tokens("\n".join(lines))


def test_sliced_rule_without_metadata_section_is_kept(tmp_path: Path) -> None:
    files = _files_for("backend-api")
    files[".ai/rules/coding.md"] += "\n## Team convention\nUse cents for money.\n"
    pkg = Router(
        Catalog(kit_root()).routing, PlanSource(files, "p", None), dict(DEFAULT_BUDGET)
    ).route(HEALTH)
    coding = next(i for i in pkg.by_kind("rule") if i.id == "coding")
    assert "Team convention" in {s["heading"] for s in coding.sections}


# 9-10. Dependencies and cycles --------------------------------------------------------------------
def test_dependency_level_is_capped_by_edge_and_parent() -> None:
    lv = levels(package("Add a database migration for orders"))  # database HIGH
    assert lv["03-database"] == HIGH
    assert lv["02-backend"] == MEDIUM  # requires backend at MEDIUM
    assert lv["04-architecture"] == MEDIUM  # backend (MEDIUM) requires architecture MEDIUM


def test_find_cycle() -> None:
    assert find_cycle({"a": ["b"], "b": ["c"], "c": []}) is None
    assert find_cycle({"a": ["b"], "b": ["a"]}) == ["a", "b", "a"]
    assert find_cycle({"a": ["a"]}) == ["a", "a"]


def test_circular_metadata_is_rejected() -> None:
    meta = copy.deepcopy(Catalog(kit_root()).routing)
    meta["agents"]["04-architecture"]["requires"] = {"02-backend": "LOW"}
    with pytest.raises(KitError, match=r"Circular agent dependency: .*->"):
        validate_routing(meta)


# 11. Deduplication ------------------------------------------------------------------------------
def test_each_file_is_loaded_once() -> None:
    for pkg in (package(SQLI), package(REACT, profile="fullstack")):
        paths = [i.path for i in pkg.items.values()]
        assert len(paths) == len(set(paths))
    sqli = package(SQLI)
    python = next(i for i in sqli.by_kind("stack") if i.id == "python")
    assert python.requested_by == ["02-backend", "03-database"]
    assert any("python/README.md" in line for line in sqli.deduplicated)
    coding = next(i for i in sqli.by_kind("rule") if i.id == "coding")
    assert coding.requested_by == ["02-backend", "03-database"]


def test_project_files_are_read_at_most_once(init_project, monkeypatch) -> None:
    root = init_project("dedup-app", "--technology", "python-fastapi")
    reads: list[str] = []
    original = Path.read_text

    def counting(self, *args, **kwargs):
        reads.append(self.as_posix())
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    source = ProjectSource(root, "dedup-app", "backend-api")
    Router(Catalog(kit_root()).routing, source, dict(DEFAULT_BUDGET)).route(SQLI)
    assert len(reads) == len(set(reads))


# 12. Explainability -------------------------------------------------------------------------------
def test_every_decision_is_explained() -> None:
    pkg = package(SQLI)
    for item in pkg.items.values():
        assert item.reason, item.path
    for agent_id, decision in pkg.decisions.items():
        if agent_id not in loaded_agents(pkg) and agent_id != "00-master" and decision.installed:
            assert pkg.skipped["agents"].get(agent_id), agent_id
    assert "sql" in pkg.decisions["03-database"].matched
    assert pkg.skipped["agents"]["01-frontend"].startswith("Not related")
    assert "Required by 02-backend" in " ".join(pkg.decisions["04-architecture"].reasons)


# 13-14. CLI and JSON ------------------------------------------------------------------------------
def test_cli_json_output() -> None:
    result = run("context", "--profile", "backend-api", "--task", HEALTH, "--json")
    assert result.code == 0, result.err
    data = json.loads(result.out)
    assert {a["id"] for a in data["selected_agents"]} == {
        "00-master",
        "02-backend",
        "04-architecture",
        "10-testing",
    }
    assert data["budget"]["status"] == "OK"
    levels_by_id = {a["id"]: a["level"] for a in data["selected_agents"]}
    assert levels_by_id["00-master"] == "CORE" and levels_by_id["02-backend"] == "HIGH"


def test_cli_text_output() -> None:
    result = run("context", "--profile", "backend-api", "--task", "add customer endpoint")
    assert result.code == 0, result.err
    for text in (
        "AI CONTEXT ANALYSIS",
        "Selected agents:",
        "Skipped:",
        "Estimated context:",
        "Budget",
        "Status: OK",
        "Estimated reduction",
        "not the provider's actual",
    ):
        assert text in result.out, text


def test_cli_inside_a_generated_project(init_project) -> None:
    root = init_project("billing-api", "--technology", "python-fastapi")
    result = run("context", "--path", str(root), "--task", "Add customer creation endpoint")
    assert result.code == 0, result.err
    assert "Project: billing-api" in result.out and "index.json missing" not in result.out


def test_cli_outside_a_project_is_a_usage_error(tmp_path: Path) -> None:
    result = run("context", "--path", str(tmp_path), "--task", "x")
    assert result.code == 2 and "--profile" in result.err


# 15. Empty task -----------------------------------------------------------------------------------
@pytest.mark.parametrize("task", ["", "   \n\t"])
def test_empty_task_loads_core_only(task: str) -> None:
    pkg = package(task)
    assert loaded_agents(pkg) == set() and not pkg.by_kind("stack") and not pkg.by_kind("rule")
    assert {i.kind for i in pkg.items.values()} == {"core", "agent"}  # AGENTS, project, master
    assert pkg.skipped["agents"]["02-backend"] == "No task given"


# 16-17. Unknown technology and unknown agent -----------------------------------------------------
def test_technology_not_installed_is_reported() -> None:
    pkg = package("Add an Angular page for invoices")  # backend-api project: no angular guide
    assert "angular" in pkg.skipped["stacks"]
    assert "not installed" in pkg.skipped["stacks"]["angular"]
    assert pkg.decisions["01-frontend"].status == "not_installed"


def test_unknown_words_do_not_crash() -> None:
    pkg = package("Port the zorblax quantum flux capacitor to Elixir")
    assert pkg.status in ("OK", "OVER_BUDGET")


def test_unknown_technology_option_is_rejected() -> None:
    result = run("context", "--profile", "backend-api", "--technology", "cobol", "--task", "x")
    assert result.code == 2


def test_unknown_agent_reference_in_metadata() -> None:
    meta = copy.deepcopy(Catalog(kit_root()).routing)
    meta["agents"]["02-backend"]["requires"]["99-ghost"] = "HIGH"
    with pytest.raises(KitError, match="99-ghost"):
        validate_routing(meta)


def test_custom_agent_without_metadata_is_skipped_with_reason(init_project) -> None:
    root = init_project("custom-agents")
    (root / ".ai/agents/99-billing-domain.md").write_text("# Billing\n", encoding="utf-8")
    result = run("context", "--path", str(root), "--task", "add invoice endpoint", "--json")
    data = json.loads(result.out)
    assert data["skipped_context"]["agents"]["99-billing-domain"].startswith("No routing metadata")


@pytest.mark.parametrize("trigger", ["os.system(", "../x", "A B", ""])
def test_metadata_triggers_are_validated(trigger: str) -> None:
    meta = copy.deepcopy(Catalog(kit_root()).routing)
    meta["agents"]["02-backend"]["triggers"][trigger] = 1
    with pytest.raises(KitError):
        validate_routing(meta)


# 18. Budget exceeded -----------------------------------------------------------------------------
def test_budget_exceeded(init_project) -> None:
    root = init_project("tight-budget")
    (root / ".ai/context/budget.json").write_text('{"default_token_budget": 1000}', "utf-8")
    result = run("context", "--path", str(root), "--task", SQLI)
    assert result.code == 0 and "OVER_BUDGET" in result.out  # reported, never auto-trimmed
    assert "never drop security or tests" in result.out
    strict = run("context", "--path", str(root), "--task", SQLI, "--strict", "--json")
    assert strict.code == 1
    data = json.loads(strict.out)
    assert any(v.startswith("total") for v in data["budget"]["violations"])
    assert "09-security" in {a["id"] for a in data["selected_agents"]}  # security kept


def test_invalid_budget_file_in_project(init_project) -> None:
    root = init_project("bad-budget")
    (root / ".ai/context/budget.json").write_text('{"planning_budget": 0}', "utf-8")
    assert run("context", "--path", str(root), "--task", "x").code == 1
    checks = json.loads(run("doctor", "--path", str(root), "--format", "json").out)["checks"]
    assert {c["name"]: c["status"] for c in checks}["Context budget"] == "WARN"


# 19-20. Existing projects and backward compatibility ---------------------------------------------
def _simulate_v100_project(root: Path) -> None:
    """Turn a fresh project into what kit 1.0.0 generated (no index, router, budget).

    Adjusted in v1.2 (decision C): index.json and graph.json are derived artefacts listed in
    `derived_files`, so the simulation removes them from there (and removes graph.json too).
    """
    lock_path = root / ".ai/kit.lock.json"
    lock = json.loads(lock_path.read_text("utf-8"))
    for rel in (
        ".ai/context/index.json",
        ".ai/context/graph.json",
        ".ai/agents/15-context-token-optimizer.md",
        ".ai/context/README.md",
    ):
        (root / rel).unlink()
        lock["managed_files"].pop(rel, None)
    lock.pop("derived_files", None)
    (root / ".ai/context/budget.json").unlink()
    lock["seed_files"].remove(".ai/context/budget.json")
    lock["kit_version"] = "1.0.0"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")


def test_v100_project_works_and_updates(init_project) -> None:
    root = init_project("legacy-app", "--technology", "python-fastapi")
    _simulate_v100_project(root)
    custom_context = "# Project context\nOur own summary.\n"
    (root / ".ai/context/project.md").write_text(custom_context, encoding="utf-8")

    before = run("context", "--path", str(root), "--task", HEALTH)
    assert before.code == 0 and "index.json missing" in before.out
    checks = json.loads(run("doctor", "--path", str(root), "--format", "json").out)["checks"]
    assert {c["name"]: c["status"] for c in checks}["Context index"] == "WARN"

    assert run("update", "--path", str(root), "--check").code == 1
    updated = run("update", "--path", str(root))
    assert updated.code == 0, updated.err
    assert (root / ".ai/context/index.json").is_file()
    assert (root / ".ai/agents/15-context-token-optimizer.md").is_file()
    assert (root / ".ai/context/budget.json").is_file()
    assert (root / ".ai/context/project.md").read_text("utf-8") == custom_context  # untouched
    lock = json.loads((root / ".ai/kit.lock.json").read_text("utf-8"))
    # The index is a derived artefact, not a CORE file
    assert ".ai/context/index.json" in lock["derived_files"]
    assert ".ai/context/index.json" not in lock["managed_files"]
    assert run("update", "--path", str(root), "--check").code == 0


def test_customised_index_is_regenerated_as_a_derived_artefact(init_project, kit_copy, set_version):
    # index.json is derived (not a source of truth): update regenerates it, local edits are
    # replaced, no .kit-new conflict.
    root = init_project("idx-app")
    index = root / ".ai/context/index.json"
    index.write_text(index.read_text("utf-8").replace('"usage"', '"usage_local"'), "utf-8")
    rules = kit_copy / "rules" / "coding.md"
    rules.write_text(rules.read_text("utf-8") + "\n## Extra\nNew rule.\n", "utf-8")
    set_version("9.0.0")
    result = run("update", "--path", str(root))
    assert result.code == 0 and "CONFLICT" not in result.out
    assert not (root / ".ai/context/index.json.kit-new").exists()
    assert '"usage_local"' not in index.read_text("utf-8")
    assert "Extra" in index.read_text("utf-8")  # regenerated from the new sources


def test_generated_index_is_valid_and_safe(init_project) -> None:
    root = init_project("idx-check", "--technology", "python-fastapi")
    index = read_index((root / ".ai/context/index.json").read_text("utf-8"))
    assert index is not None
    for kind in ("agents", "rules", "workflows", "stacks"):
        for entry in index[kind].values():
            assert entry["path"].startswith(".ai/") and ".." not in entry["path"]
            assert (root / entry["path"]).is_file()
    assert "01-frontend" in index["not_installed_agents"]
    assert index["agents"]["15-context-token-optimizer"]["layer"] == "router"


def test_index_is_deterministic(catalog: Catalog) -> None:
    files = _files_for("backend-api")
    assert build_index(files, catalog.routing) == build_index(dict(files), catalog.routing)


def test_project_source_refuses_paths_outside_context(init_project) -> None:
    root = init_project("safe-app")
    source = ProjectSource(root, "safe-app", None)
    for path in ("../outside.md", ".git/config", "src/app.py", ".ai/kit.lock.json"):
        with pytest.raises(KitError):
            source.read(path)


def test_router_agent_is_loaded_only_for_context_optimisation_tasks() -> None:
    # Normal tasks never load the context optimiser; context-optimisation tasks do.
    for task in (HEALTH, SQLI, "Add customer creation endpoint", "Refactor the token parser"):
        assert "15-context-token-optimizer" not in {i.id for i in package(task).by_kind("agent")}
        assert "15-context-token-optimizer" not in {
            i.id for i in direct_package(task).by_kind("agent")
        }
    for task in ("optimise the context token budget", "Improve context routing to reduce tokens"):
        assert "15-context-token-optimizer" in {i.id for i in package(task).by_kind("agent")}


# 27. Reduction: full vs optimized (computed, estimated tokens) -----------------------------------
@pytest.mark.parametrize(
    ("task", "profile"), [(HEALTH, "backend-api"), (SQLI, "backend-api"), (REACT, "fullstack")]
)
def test_reduction_versus_full_context(task: str, profile: str) -> None:
    pkg = package(task, profile=profile)
    full, optimized = pkg.full_context_tokens, pkg.totals["total"]
    assert 0 < optimized < full
    expected = round((full - optimized) / full * 100, 1)
    assert pkg.reduction_percentage == expected
    assert pkg.reduction_percentage > 50  # measured: ~62-72% on the reference cases


def test_reduction_guards_division_by_zero() -> None:
    pkg = package("")
    pkg.full_context_tokens = 0
    assert pkg.reduction_percentage == 0.0


def test_profile_matrix_routes_without_errors(catalog: Catalog) -> None:
    for name, profile in catalog.profiles.items():
        for technology in profile.technologies:
            pkg = package(HEALTH, profile=name, technology=technology)
            assert pkg.items, (name, technology)


def _files_for(profile: str) -> dict[str, str]:
    from ai_project.catalog import Selection
    from ai_project.generator import build_plan

    catalog = Catalog(kit_root())
    prof = catalog.profiles[profile]
    selection = Selection(profile, prof.technologies[0], "postgresql", "kubernetes", ())
    plan = build_plan(catalog, catalog.resolve(selection), selection, {"project_name": "x"})
    return {p.path: p.content for p in plan}
