"""Task classification, context ranking and token budget (pure functions)."""

from __future__ import annotations

import pytest

from ai_project.catalog import Catalog
from ai_project.context_budget import (
    DEFAULT_BUDGET,
    DEFAULT_TIERS,
    OPTIONAL,
    RECOMMENDED,
    REQUIRED,
    Candidate,
    choose_tier,
    parse_budget,
    parse_tiers,
    slice_to_budget,
)
from ai_project.context_rank import (
    DEFAULT_WEIGHTS,
    RankingConfig,
    classify_task,
    score_candidate,
    task_match_from_trigger_score,
    token_cost,
)
from ai_project.context_router import match_triggers, normalize
from ai_project.errors import KitError
from ai_project.paths import kit_root

META = Catalog(kit_root()).routing


def labels(task: str) -> list[str]:
    return classify_task(normalize(task), META, match_triggers).labels


# Classification --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("task", "category"),
    [
        ("Bootstrap a new project for invoicing", "new_project"),
        ("Implement the export feature", "new_feature"),
        ("Fix the crash in the parser", "bug_fix"),
        ("Refactor the billing module", "refactoring"),
        ("Audit authentication security", "security"),
        ("Increase test coverage of the parser", "testing"),
        ("Speed up slow report latency", "performance"),
        ("Add an index to the orders table", "database"),
        ("Expose a REST API for invoices", "api"),
        ("Build a React page for orders", "frontend"),
        ("Move business logic into the backend service", "backend"),
        ("Deploy service to Kubernetes", "deployment"),
        ("Update the README and diagrams", "documentation"),
        ("Prepare the release and bump the version", "release"),
    ],
)
def test_all_fourteen_categories(task: str, category: str) -> None:
    assert category in labels(task)


def test_reference_classifications() -> None:
    assert labels("Create a FastAPI endpoint for equipment") == [
        "new_feature",
        "api",
        "backend",
        "fastapi",
    ]
    assert labels("Fix ClickHouse query") == ["database", "bug_fix", "clickhouse"]
    assert labels("Audit authentication security") == ["security"]
    assert labels("Refactor a Python service") == ["refactoring", "backend", "python"]
    assert labels("Deploy service to Kubernetes") == ["deployment", "kubernetes"]


def test_weak_words_alone_do_not_classify() -> None:
    assert "backend" not in labels("Deploy service to Kubernetes")  # 'service' alone is weak


@pytest.mark.parametrize("task", ["", "   ", "Paint the office walls"])
def test_empty_and_unknown_tasks(task: str) -> None:
    result = classify_task(normalize(task), META, match_triggers)
    assert result.categories == () and result.technologies == ()


def test_combined_task_and_technology_detection() -> None:
    result = classify_task(
        normalize("Fix the slow PostgreSQL query behind the React dashboard"), META, match_triggers
    )
    assert {"bug_fix", "performance", "database", "frontend"} <= set(result.categories)
    assert set(result.technologies) == {"postgresql", "react"}
    assert result.to_dict()["matched_triggers"]["database"]


def test_classification_is_deterministic() -> None:
    task = normalize("Fix SQL injection in the customer search API")
    assert classify_task(task, META, match_triggers) == classify_task(task, META, match_triggers)


# Ranking ----------------------------------------------------------------------------------------
def test_ranking_config_comes_from_metadata() -> None:
    config = RankingConfig.from_meta(META)
    assert config.weights == {**DEFAULT_WEIGHTS, **META["ranking"]["weights"]}
    assert config.min_recommended_score == META["ranking"]["min_recommended_score"]
    assert config.protected_agents == ("09-security", "10-testing")


def test_score_formula_and_breakdown() -> None:
    config = RankingConfig(weights=DEFAULT_WEIGHTS)
    score = score_candidate(
        config,
        {
            "task_match": 1.0,
            "graph_weight": 0.5,
            "profile_match": 1.0,
            "technology_match": 0.0,
            "dependency_bonus": 1.0,
            "token_cost": 0.4,
        },
        ["task matched: endpoint"],
    )
    expected = 0.35 * 1 + 0.30 * 0.5 + 0.05 * 1 + 0.15 * 1 - 0.05 * 0.4
    assert score.value == round(expected, 3)
    assert score.components["graph_weight"] == 0.5
    assert score.to_dict()["reasons"] == ["task matched: endpoint"]


@pytest.mark.parametrize(
    ("component", "value"),
    [
        ("task_match", 1.0),
        ("graph_weight", 1.0),
        ("profile_match", 1.0),
        ("technology_match", 1.0),
        ("dependency_bonus", 1.0),
    ],
)
def test_each_positive_component_raises_the_score(component: str, value: float) -> None:
    config = RankingConfig(weights=DEFAULT_WEIGHTS)
    assert score_candidate(config, {component: value}).value > score_candidate(config, {}).value


def test_token_cost_and_redundancy_lower_the_score() -> None:
    config = RankingConfig(weights=DEFAULT_WEIGHTS)
    base = score_candidate(config, {"task_match": 1.0})
    assert score_candidate(config, {"task_match": 1.0, "token_cost": 1.0}).value < base.value
    assert score_candidate(config, {"task_match": 1.0, "redundancy_penalty": 0.2}).value == round(
        base.value - 0.2, 3
    )


def test_score_is_clamped() -> None:
    config = RankingConfig(weights=DEFAULT_WEIGHTS)
    assert score_candidate(config, {k: 5.0 for k in DEFAULT_WEIGHTS}).value <= 1.0
    assert score_candidate(config, {"redundancy_penalty": 1.0}).value == 0.0


def test_component_helpers() -> None:
    assert [task_match_from_trigger_score(s) for s in (0, 1, 3, 9)] == [0.0, 1 / 3, 1.0, 1.0]
    assert token_cost(1250, 2500) == 0.5 and token_cost(9999, 2500) == 1.0
    assert token_cost(10, 0) == 0.0


# Budget -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("categories", "deep", "tier"),
    [
        (["documentation"], False, "simple"),
        ([], False, "simple"),
        (["new_feature", "api"], False, "normal"),
        (["refactoring", "backend"], False, "normal"),
        (["frontend", "backend", "database"], False, "complex"),
        (["new_project"], False, "complex"),
        (["frontend", "performance"], True, "complex"),
        (["security"], False, "security"),
        (["security", "frontend", "backend", "database"], True, "security"),
    ],
)
def test_choose_tier(categories: list[str], deep: bool, tier: str) -> None:
    assert choose_tier(categories, deep)[0] == tier


def test_tiers_defaults_and_overrides() -> None:
    assert parse_tiers(None) == DEFAULT_TIERS
    template = (kit_root() / "templates/base/.ai/context/budget.json").read_text("utf-8")
    assert parse_tiers(template) == DEFAULT_TIERS
    assert parse_tiers('{"budgets": {"simple": 9000}}')["simple"] == 9000
    # Single-budget file (no tiers): its one budget applies to every tier
    assert parse_tiers('{"default_token_budget": 15000}') == dict.fromkeys(DEFAULT_TIERS, 15000)
    assert parse_tiers('{"default_token_budget": 15000, "budgets": {}}') == DEFAULT_TIERS
    assert parse_budget('{"budgets": {"security": 30000}}') == DEFAULT_BUDGET


@pytest.mark.parametrize(
    "text",
    [
        '{"budgets": {"huge": 1}}',
        '{"budgets": {"simple": 0}}',
        '{"budgets": []}',
        '{"budgets": {"normal": "x"}}',
    ],
)
def test_invalid_tiers_are_rejected(text: str) -> None:
    with pytest.raises(KitError):
        parse_budget(text)


def _candidates() -> list[Candidate]:
    return [
        Candidate("agent.backend", 1200, REQUIRED, 0.9),
        Candidate("agent.testing", 1100, REQUIRED, 0.7),
        Candidate("stack.fastapi", 1000, RECOMMENDED, 0.6),
        Candidate("stack.ci-cd", 900, RECOMMENDED, 0.4),
        Candidate("stack.linux", 800, RECOMMENDED, 0.2),
        Candidate("agent.frontend", 1500, OPTIONAL, 0.1),
    ]


def test_slicer_priorities_large_budget() -> None:
    result = slice_to_budget(_candidates(), limit=1_000_000, min_score=0.3)
    assert result.selected == ["agent.backend", "agent.testing", "stack.fastapi", "stack.ci-cd"]
    assert result.dropped["stack.linux"].startswith("low relevance")
    assert result.dropped["agent.frontend"].startswith("optional")
    assert not result.over_budget


def test_slicer_drops_recommended_by_score_when_budget_is_tight() -> None:
    result = slice_to_budget(_candidates(), limit=4000, min_score=0.3, base_tokens=500)
    # 500 base + 2,300 required = 2,800; fastapi (score 0.6) fits: 3,800
    assert result.selected == ["agent.backend", "agent.testing", "stack.fastapi"]
    assert result.dropped["stack.ci-cd"].startswith("budget")  # 3,800 + 900 > 4,000
    assert result.total_tokens == 3800


def test_tiny_budget_keeps_required_and_reports_over_budget() -> None:
    result = slice_to_budget(_candidates(), limit=100, min_score=0.3)
    assert {"agent.backend", "agent.testing"} <= set(result.selected)  # never dropped
    assert result.over_budget and result.required_tokens == 2300


def test_slicer_is_deterministic() -> None:
    a = slice_to_budget(_candidates(), 3500, 0.3)
    b = slice_to_budget(list(reversed(_candidates())), 3500, 0.3)
    assert a.selected == b.selected and a.dropped == b.dropped


# Router integration: graph mode vs direct mode --------------------------------------------------
from ai_project import __version__  # noqa: E402
from ai_project.catalog import Selection  # noqa: E402
from ai_project.context_budget import DEFAULT_BUDGET as BUDGET  # noqa: E402
from ai_project.context_graph import build_graph, graph_sources  # noqa: E402
from ai_project.context_router import PlanSource, Router  # noqa: E402
from ai_project.generator import build_plan  # noqa: E402
from ai_project.lockfile import content_hash  # noqa: E402

CASES = {
    "fastapi_endpoint": ("Create a FastAPI endpoint for equipment", "postgresql"),
    "clickhouse_fix": ("Fix ClickHouse query", "clickhouse"),
    "auth_audit": ("Audit authentication security", "postgresql"),
    "python_refactor": ("Refactor a Python service", "postgresql"),
    "k8s_deploy": ("Deploy service to Kubernetes", "none"),
}


def _route(
    task,
    database="postgresql",
    profile="backend-api",
    technology="python-fastapi",
    graph_mode=True,
    tiers=None,
):
    catalog = Catalog(kit_root())
    selection = Selection(profile, technology, database, "kubernetes", tuple(catalog.assistants))
    plan = build_plan(catalog, catalog.resolve(selection), selection, {"project_name": "x"})
    files = {p.path: p.content for p in plan}
    graph = None
    if graph_mode:
        hashes = {p.path: content_hash(p.content) for p in plan if p.managed}
        graph = build_graph(
            graph_sources(catalog, selection.to_dict(), "x", files, hashes, __version__)
        )
    router = Router(
        catalog.routing,
        PlanSource(files, "x", profile),
        dict(BUDGET),
        graph=graph,
        tiers=tiers,
        selection=selection.to_dict(),
    )
    return router.route(task)


def _ids(pkg, kind):
    return {i.id for i in pkg.by_kind(kind)} - {"00-master"}


def _relevance(pkg, kind, item_id):
    return next(i.relevance for i in pkg.by_kind(kind) if i.id == item_id)


def test_case_1_fastapi_endpoint() -> None:
    pkg = _route(*CASES["fastapi_endpoint"])
    assert {"02-backend", "04-architecture", "10-testing"} <= _ids(pkg, "agent")
    assert {"fastapi", "python"} <= _ids(pkg, "stack")
    assert _relevance(pkg, "stack", "fastapi") == REQUIRED
    assert not _ids(pkg, "agent") & {"01-frontend"}
    assert not _ids(pkg, "stack") & {"react", "angular"}


def test_case_2_clickhouse_fix() -> None:
    pkg = _route(*CASES["clickhouse_fix"])
    assert {"03-database", "02-backend", "10-testing"} <= _ids(pkg, "agent")
    assert "clickhouse" in _ids(pkg, "stack")
    assert _relevance(pkg, "stack", "clickhouse") == REQUIRED
    assert pkg.classification.categories[:2] == ("database", "bug_fix")


def test_case_3_auth_audit_security_first() -> None:
    pkg = _route(*CASES["auth_audit"])
    assert pkg.tier == "security"
    assert {"09-security", "10-testing"} <= _ids(pkg, "agent")
    assert _relevance(pkg, "agent", "09-security") == REQUIRED
    rules = {i.id: i for i in pkg.by_kind("rule")}
    security = {s["heading"] for s in rules["security"].sections}
    assert "Authentication and authorization" in security
    assert "Files, paths and network" not in security  # concept slicing
    assert rules["architecture"].requested_by == ["task.security"]  # relevant architecture
    concepts = next(e for e in pkg.selected_list() if e["id"] == "rule.security")["concepts"]
    assert "concept.security.authentication-and-authorization" in concepts


def test_case_4_python_refactor_fastapi_is_only_recommended() -> None:
    pkg = _route(*CASES["python_refactor"])
    assert {"05-quality", "02-backend", "10-testing"} <= _ids(pkg, "agent")
    assert _relevance(pkg, "stack", "python") == REQUIRED
    assert pkg.stack_ranks["fastapi"][0] == RECOMMENDED  # not REQUIRED: only the project uses it
    assert _route(*CASES["python_refactor"], graph_mode=False).by_kind("stack")  # direct mode works


def test_case_5_kubernetes_deploy_reduces_context() -> None:
    before = _route(*CASES["k8s_deploy"], graph_mode=False)
    after = _route(*CASES["k8s_deploy"])
    assert "kubernetes" in _ids(after, "stack")
    assert _relevance(after, "stack", "kubernetes") == REQUIRED
    assert {"12-devops", "10-testing"} <= _ids(after, "agent")
    assert not _ids(after, "stack") & {"linux", "nginx", "ci-cd"}
    skipped = {e["id"]: e for e in after.skipped_list()}
    for stack in ("stack.linux", "stack.nginx", "stack.ci-cd"):
        assert skipped[stack]["relevance"] in (RECOMMENDED, OPTIONAL)
    assert skipped["agent.02-backend"]["relevance"] == RECOMMENDED  # relevant, ranked low
    assert after.totals["total"] < before.totals["total"]
    assert len({i.path for i in after.items.values()}) < len(
        {i.path for i in before.items.values()}
    )


@pytest.mark.parametrize("case", sorted(CASES))
def test_before_after_never_increases_beyond_targeted_rule_sections(case: str) -> None:
    """Graph mode may only add targeted rule sections recommended by a task category."""
    task, db = CASES[case]
    before, after = _route(task, db, graph_mode=False), _route(task, db)
    extra = sum(
        i.tokens
        for i in after.by_kind("rule")
        if all(r.startswith("task.") for r in i.requested_by)
    )
    assert after.totals["total"] <= before.totals["total"] + extra


def test_direct_mode_is_the_v11_router() -> None:
    pkg = _route(*CASES["k8s_deploy"], graph_mode=False)
    assert pkg.mode == "direct" and pkg.tier is None and pkg.tier_limit is None
    assert all(i.rank is None for i in pkg.items.values())


def test_levels_l0_to_l3() -> None:
    pkg = _route("Fix SQL injection vulnerability in customer search")
    layers = {(i.kind, i.id): i.layer for i in pkg.items.values()}
    assert layers[("core", "AGENTS.md")] == "L0" and layers[("agent", "00-master")] == "L0"
    assert layers[("agent", "02-backend")] == "L1"
    assert layers[("stack", "python")] == "L2"
    assert layers[("agent", "09-security")] == "L3"  # deep review loaded: task is about security


def test_deduplication_in_graph_mode() -> None:
    pkg = _route("Fix SQL injection vulnerability in customer search")
    paths = [i.path for i in pkg.items.values()]
    assert len(paths) == len(set(paths))
    assert any("loaded once" in line for line in pkg.deduplicated)


def test_every_selected_and_skipped_item_is_explained() -> None:
    pkg = _route(*CASES["k8s_deploy"])
    for entry in pkg.selected_list():
        assert entry["reason"] and 0.0 <= entry["score"] <= 1.0, entry
        assert entry["relevance"] in (REQUIRED, RECOMMENDED)
    for entry in pkg.skipped_list():
        assert entry["reason"], entry
    backend = next(e for e in pkg.skipped_list() if e["id"] == "agent.02-backend")
    assert "low relevance" in backend["reason"] and "score" in backend


def test_metrics_are_measured() -> None:
    pkg = _route(*CASES["fastapi_endpoint"])
    metrics = pkg.metrics()
    assert isinstance(metrics["routing_time_ms"], float) and metrics["routing_time_ms"] > 0
    assert metrics["selected_nodes"] == len(pkg.selected_list())
    assert metrics["skipped_nodes"] == len(pkg.skipped_list())
    assert metrics["optimized_context_tokens"] == pkg.totals["total"]
    full, opt = metrics["full_context_tokens"], metrics["optimized_context_tokens"]
    assert metrics["context_reduction_percentage"] == round((full - opt) / full * 100, 1)
    assert metrics["characters_selected"] > 0 and metrics["budget_tier"] == "normal"


def test_tiny_budget_keeps_required_and_reports_over_budget_in_router() -> None:
    pkg = _route(*CASES["clickhouse_fix"], tiers=dict.fromkeys(DEFAULT_TIERS, 1000))
    assert {"03-database", "10-testing"} <= _ids(pkg, "agent")  # never dropped
    assert pkg.status == "OVER_BUDGET"
    assert "fastapi" not in _ids(pkg, "stack")  # RECOMMENDED dropped for budget
    reason = next(e["reason"] for e in pkg.skipped_list() if e["id"] == "stack.fastapi")
    assert "budget" in reason


def test_large_budget_keeps_recommended_above_threshold() -> None:
    pkg = _route(*CASES["k8s_deploy"], tiers=dict.fromkeys(DEFAULT_TIERS, 10_000_000))
    assert "python" in _ids(pkg, "stack")  # recommended, score >= threshold, fits
    assert "linux" not in _ids(pkg, "stack")  # still below the relevance threshold
    assert pkg.status == "OK"


def test_json_keeps_v11_keys_and_adds_v12_keys() -> None:
    data = _route(*CASES["fastapi_endpoint"]).to_dict()
    for key in (
        "task",
        "selected_agents",
        "selected_rules",
        "selected_workflows",
        "selected_stacks",
        "project_context",
        "skipped_context",
        "reasons",
        "estimated_tokens",
        "budget",
        "full_context_tokens",
        "reduction_percentage",
    ):
        assert key in data, key
    for key in (
        "classification",
        "selected",
        "skipped",
        "metrics",
        "mode",
        "graph",
        "estimation_method",
    ):
        assert key in data, key
    assert data["estimation_method"] == "characters_div_4"
    assert {"tier", "limit", "estimated_tokens", "status"} <= set(data["budget"])


def test_graph_routing_is_deterministic() -> None:
    a = _route("Fix SQL injection vulnerability in customer search").to_dict()
    b = _route("Fix SQL injection vulnerability in customer search").to_dict()
    for d in (a, b):
        d["metrics"].pop("routing_time_ms")
    assert a == b


def test_empty_task_in_graph_mode() -> None:
    pkg = _route("")
    assert pkg.tier is None and _ids(pkg, "agent") == set() and pkg.status == "OK"
