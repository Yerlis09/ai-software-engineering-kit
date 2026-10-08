"""Context Router: select the minimum context a task needs, and explain why.

Deterministic, local and vendor-neutral: keyword triggers from ``catalog/context.json``,
explicit dependency levels, no network, no model calls. Token figures are estimates
(characters / 4); see ``context_index.ESTIMATION_NOTE``.

Pipeline: classify agents -> propagate dependencies -> decide loading per layer
(L0 core, L1 specialist, L2 technology, L3 deep review) -> pick rule sections, workflow
and stacks -> deduplicate -> estimate -> compare with the budget.

Two modes, one router:

* **direct**: metadata only. Always available; it is the mandatory fallback
  when the knowledge graph is missing, corrupt or cannot be rebuilt.
* **graph**: adds task categories, REQUIRED / RECOMMENDED / OPTIONAL relevance, scores
  from weighted graph traversal (``context_rank``) and the budget slicer (``context_budget``).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Protocol, TypeVar

from ai_project import __version__
from ai_project.context_budget import (  # DEFAULT_BUDGET/parse_budget re-exported for importers
    DEFAULT_BUDGET,  # noqa: F401
    DEFAULT_TIERS,
    OPTIONAL,
    PHASE_BUDGET_KEYS,
    RECOMMENDED,
    REQUIRED,
    Candidate,
    choose_tier,
    parse_budget,  # noqa: F401
    slice_to_budget,
)
from ai_project.context_graph import Graph, expand_dependencies, slug, traverse_graph
from ai_project.context_index import (
    CORE_FILES,
    ESTIMATION_NOTE,
    INDEX_PATH,
    LEVELS,
    estimate_tokens,
    knowledge_path,
    read_index,
    slice_text,
    split_sections,
)
from ai_project.context_rank import (
    Classification,
    RankingConfig,
    Score,
    classify_task,
    score_candidate,
    task_match_from_trigger_score,
    token_cost,
)
from ai_project.errors import KitError
from ai_project.paths import safe_join

NONE, LOW, MEDIUM, HIGH = range(4)
MAX_FILE_BYTES = 1_000_000
CORE_ID = "00-master"

# Decision statuses
CORE, LOADED, TARGETED, CONSIDERED, SKIPPED, NOT_INSTALLED, ROUTER = (
    "core",
    "loaded",
    "targeted",
    "considered",
    "skipped",
    "not_installed",
    "router",
)


# --- Sources ------------------------------------------------------------------------------
class ContextSource(Protocol):
    project: str | None
    profile: str | None

    def installed(self, kind: str) -> list[str]: ...

    def read(self, path: str) -> str | None: ...

    def cached_tokens(self, path: str) -> int | None: ...


class ProjectSource:
    """Files of a generated project. Reads are limited to known context paths."""

    def __init__(self, root: Path, project: str | None = None, profile: str | None = None):
        self.root = root
        self.project = project
        self.profile = profile
        self._cache: dict[str, str | None] = {}
        self._installed = {kind: self._scan(kind) for kind in ("agents", "rules", "workflows")}
        self._installed["stacks"] = self._scan_stacks()
        index_text = self._read_any(INDEX_PATH)
        self.index = read_index(index_text) if index_text else None

    def _scan(self, kind: str) -> list[str]:
        folder = safe_join(self.root, f".ai/{kind}")
        if not folder.is_dir():
            return []
        return sorted(p.stem for p in folder.glob("*.md") if p.is_file() and _valid_id(p.stem))

    def _scan_stacks(self) -> list[str]:
        folder = safe_join(self.root, ".ai/stacks")
        if not folder.is_dir():
            return []
        return sorted(
            p.name for p in folder.iterdir() if _valid_id(p.name) and (p / "README.md").is_file()
        )

    def installed(self, kind: str) -> list[str]:
        return self._installed.get(kind, [])

    def _allowed(self, path: str) -> bool:
        if path in CORE_FILES:
            return True
        return any(
            path == knowledge_path(kind, item)
            for kind in self._installed
            for item in self._installed[kind]
        )

    def read(self, path: str) -> str | None:
        if not self._allowed(path):
            raise KitError(f"Context path not allowed: {path!r}")
        return self._read_any(path)

    def _read_any(self, path: str) -> str | None:
        if path not in self._cache:  # each file is read at most once per analysis
            target = safe_join(self.root, path)
            try:
                if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
                    self._cache[path] = None
                else:
                    self._cache[path] = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self._cache[path] = None
        return self._cache[path]

    def cached_tokens(self, path: str) -> int | None:
        if not self.index:
            return None
        for kind in ("agents", "rules", "workflows", "stacks"):
            for entry in self.index.get(kind, {}).values():
                if isinstance(entry, dict) and entry.get("path") == path:
                    tokens = entry.get("tokens")
                    return tokens if isinstance(tokens, int) and tokens >= 0 else None
        return None


class PlanSource:
    """In-memory files (a simulated project built from a profile, without writing)."""

    def __init__(self, files: Mapping[str, str], project: str | None, profile: str | None):
        self.files = dict(files)
        self.project = project
        self.profile = profile

    def installed(self, kind: str) -> list[str]:
        prefix = f".ai/{kind}/"
        found = set()
        for path in self.files:
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix) :]
            if kind == "stacks" and rest.endswith("/README.md") and rest.count("/") == 1:
                found.add(rest.split("/")[0])
            elif kind != "stacks" and rest.endswith(".md") and "/" not in rest:
                found.add(rest[:-3])
        return sorted(found)

    def read(self, path: str) -> str | None:
        return self.files.get(path)

    def cached_tokens(self, path: str) -> int | None:
        return None


def _valid_id(name: str) -> bool:
    try:
        knowledge_path("agents", name)
    except KitError:
        return False
    return True


# --- Matching ------------------------------------------------------------------------------
def normalize(task: str) -> str:
    return re.sub(r"[^a-z0-9+#.\-]+", " ", task.lower()).strip()


@lru_cache(maxsize=4096)
def _pattern(trigger: str) -> re.Pattern[str]:
    prefix = trigger.endswith("*")
    body = r"\s+".join(re.escape(word) for word in trigger.rstrip("*").split())
    tail = r"[a-z0-9]*" if prefix else ""
    return re.compile(rf"(?<![a-z0-9]){body}{tail}(?![a-z0-9])")


def match_triggers(triggers: Any, text: str) -> list[tuple[str, int]]:
    items = triggers.items() if isinstance(triggers, Mapping) else ((t, 1) for t in triggers)
    return [(t, int(w)) for t, w in items if text and _pattern(t).search(text)]


def level_from_score(score: int) -> int:
    return HIGH if score >= 2 else (MEDIUM if score == 1 else NONE)


_T = TypeVar("_T")


def _need(value: _T | None, what: str) -> _T:
    """Internal invariant for graph mode (explicit check instead of a stripped ``assert``)."""
    if value is None:
        raise KitError(f"Internal error: graph mode without {what}")
    return value


# --- Results ---------------------------------------------------------------------------------
@dataclass
class AgentDecision:
    id: str
    title: str
    layer: str
    level: int = NONE
    score: int = 0
    matched: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    status: str = SKIPPED
    installed: bool = True
    # Graph mode only
    required_by_task: list[str] = field(default_factory=list)
    relevance: str = ""
    rank: Score | None = None
    demoted: bool = False  # a RECOMMENDED agent left out (low relevance or budget)
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "level": LEVELS[self.level],
            "layer": self.layer,
            "status": self.status,
            "score": self.score,  # raw trigger score (direct-mode signal)
            "matched": self.matched,
            "reasons": self.reasons,
            "installed": self.installed,
        }
        if self.relevance:
            data["relevance"] = self.relevance
        if self.rank is not None:
            data["rank"] = self.rank.to_dict()
        return data


@dataclass
class ContextItem:
    kind: str  # core | agent | rule | workflow | stack
    id: str
    path: str
    layer: str
    phase: str
    tokens: int
    reason: str
    requested_by: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] | None = None  # None = whole file
    chars: int = 0
    relevance: str = REQUIRED
    rank: Score | None = None

    @property
    def node(self) -> str:
        """Knowledge-graph node id of this item."""
        return f"file.{slug(self.path)}" if self.kind == "core" else f"{self.kind}.{self.id}"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "path": self.path,
            "layer": self.layer,
            "phase": self.phase,
            "estimated_tokens": self.tokens,
            "reason": self.reason,
        }
        if self.requested_by:
            data["requested_by"] = self.requested_by
        if self.kind == "rule":
            data["sections"] = self.sections  # None means the whole file
        if self.rank is not None:
            data["relevance"] = self.relevance
            data["score"] = self.rank.value
        return data


@dataclass
class ContextPackage:
    task: str
    project: str | None
    profile: str | None
    decisions: dict[str, AgentDecision]
    items: dict[tuple[str, str], ContextItem]
    skipped: dict[str, dict[str, str]]
    deduplicated: list[str]
    budget: dict[str, int]
    full_context_tokens: int
    warnings: list[str] = field(default_factory=list)
    # Routing mode and graph-mode details
    mode: str = "direct"
    classification: Classification | None = None
    tier: str | None = None
    tier_reason: str = ""
    tier_limit: int | None = None
    graph_info: dict[str, Any] = field(default_factory=dict)
    routing_time_ms: float | None = None
    stack_ranks: dict[str, tuple[str, Score]] = field(default_factory=dict)

    def by_kind(self, kind: str) -> list[ContextItem]:
        return [item for (k, _), item in self.items.items() if k == kind]

    @property
    def totals(self) -> dict[str, int]:
        totals = {
            k: sum(i.tokens for i in self.by_kind(k))
            for k in ("core", "agent", "rule", "workflow", "stack")
        }
        totals["task"] = estimate_tokens(self.task)
        totals["total"] = sum(totals.values())
        return totals

    @property
    def phases(self) -> dict[str, dict[str, int]]:
        result = {}
        for phase, key in PHASE_BUDGET_KEYS.items():
            used = sum(i.tokens for i in self.items.values() if i.phase == phase)
            result[phase] = {"estimated_tokens": used, "budget": self.budget[key]}
        return result

    @property
    def violations(self) -> list[str]:
        found = []
        total = self.totals["total"]
        if self.tier_limit is not None:  # graph mode: the task's budget tier
            if total > self.tier_limit:
                found.append(f"total {total} > {self.tier} budget {self.tier_limit}")
        elif total > self.budget["default_token_budget"]:
            found.append(
                f"total {total} > default_token_budget {self.budget['default_token_budget']}"
            )
        for phase, data in self.phases.items():
            if data["estimated_tokens"] > data["budget"]:
                found.append(
                    f"{phase} {data['estimated_tokens']} > {PHASE_BUDGET_KEYS[phase]} "
                    f"{data['budget']}"
                )
        for item in self.items.values():
            limit = {"agent": "max_agent_context", "stack": "max_stack_context"}.get(item.kind)
            if limit and item.tokens > self.budget[limit]:
                found.append(f"{item.path} {item.tokens} > {limit} {self.budget[limit]}")
        return found

    @property
    def status(self) -> str:
        return "OVER_BUDGET" if self.violations else "OK"

    @property
    def reduction_percentage(self) -> float:
        full = self.full_context_tokens
        if full <= 0:
            return 0.0
        return round((full - self.totals["total"]) / full * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        def items(kind: str) -> list[dict[str, Any]]:
            return [i.to_dict() for i in self.by_kind(kind)]

        selected_agents = []
        for item in self.by_kind("agent"):
            entry = item.to_dict()
            decision = self.decisions.get(item.id)
            if decision:
                entry["level"] = "CORE" if decision.layer == "L0" else LEVELS[decision.level]
            selected_agents.append(entry)
        return {
            "schema_version": 1,
            "kit_version": __version__,
            "estimation": ESTIMATION_NOTE,
            "task": self.task,
            "project": self.project,
            "profile": self.profile,
            "project_context": items("core"),
            "selected_agents": selected_agents,
            "selected_rules": items("rule"),
            "selected_workflows": items("workflow"),
            "selected_stacks": items("stack"),
            "skipped_context": self.skipped,
            "reasons": {a: d.to_dict() for a, d in self.decisions.items()},
            "deduplicated": self.deduplicated,
            "estimated_tokens": self.totals,
            "budget": {
                "limits": self.budget,
                "phases": self.phases,
                "status": self.status,
                "violations": self.violations,
                # Tier selection
                "tier": self.tier,
                "tier_reason": self.tier_reason,
                "limit": self.limit,
                "estimated_tokens": self.totals["total"],
            },
            "full_context_tokens": self.full_context_tokens,
            "reduction_percentage": self.reduction_percentage,
            "warnings": self.warnings,
            # Graph-mode details
            "mode": self.mode,
            "graph": self.graph_info,
            "estimation_method": "characters_div_4",
            "classification": self.classification.labels if self.classification else [],
            "classification_details": (
                self.classification.to_dict() if self.classification else {}
            ),
            "selected": self.selected_list(),
            "skipped": self.skipped_list(),
            "metrics": self.metrics(),
        }

    @property
    def limit(self) -> int:
        return (
            self.tier_limit if self.tier_limit is not None else self.budget["default_token_budget"]
        )

    def selected_list(self) -> list[dict[str, Any]]:
        out = []
        for item in self.items.values():
            entry: dict[str, Any] = {
                "id": item.node,
                "kind": item.kind,
                "path": item.path,
                "level": item.layer,
                "relevance": item.relevance,
                "estimated_tokens": item.tokens,
                "characters": item.chars,
                "reason": item.reason,
            }
            if item.rank is not None:
                entry["score"] = item.rank.value
                entry["score_components"] = item.rank.components
                entry["reasons"] = item.rank.reasons
            if item.kind == "rule" and item.sections is not None:
                entry["concepts"] = [
                    f"concept.{item.id}.{slug(s['heading'])}"
                    for s in item.sections
                    if s["heading"] != "(preamble)"
                ]
            out.append(entry)
        return out

    def skipped_list(self) -> list[dict[str, Any]]:
        out = []
        for kind_plural, entries in self.skipped.items():
            kind = kind_plural[:-1]
            for item_id, reason in entries.items():
                entry: dict[str, Any] = {"id": f"{kind}.{item_id}", "kind": kind, "reason": reason}
                decision = self.decisions.get(item_id) if kind == "agent" else None
                rank = decision.rank if decision else None
                relevance = decision.relevance if decision else ""
                if kind == "stack" and item_id in self.stack_ranks:
                    relevance, rank = self.stack_ranks[item_id]
                if relevance:
                    entry["relevance"] = relevance
                if rank is not None:
                    entry["score"] = rank.value
                out.append(entry)
        return out

    def metrics(self) -> dict[str, Any]:
        """Measured values only; routing_time_ms is None when not measured."""
        sections = sum(len(i.sections or []) for i in self.by_kind("rule"))
        return {
            "routing_time_ms": self.routing_time_ms,
            "full_context_tokens": self.full_context_tokens,
            "optimized_context_tokens": self.totals["total"],
            "context_reduction_percentage": self.reduction_percentage,
            "selected_nodes": len(self.items),
            "selected_rule_sections": sections,
            "skipped_nodes": len(self.skipped_list()),
            "files_selected": len({i.path for i in self.items.values()}),
            "characters_selected": sum(i.chars for i in self.items.values()),
            "classification": self.classification.labels if self.classification else [],
            "budget_tier": self.tier,
            "status": self.status,
            "mode": self.mode,
        }


# --- Router ----------------------------------------------------------------------------------
class Router:
    def __init__(
        self,
        meta: Mapping[str, Any],
        source: ContextSource,
        budget: dict[str, int],
        graph: Graph | None = None,
        tiers: Mapping[str, int] | None = None,
        selection: Mapping[str, Any] | None = None,
    ):
        self.meta = meta
        self.source = source
        self.budget = budget
        self.graph = graph  # None -> direct mode
        self.tiers = dict(tiers or DEFAULT_TIERS)
        self.selection = dict(selection or {})
        self.ranking = RankingConfig.from_meta(meta)

    def route(self, task: str) -> ContextPackage:
        started = time.perf_counter()
        text = normalize(task)
        classification = classify_task(text, self.meta, match_triggers)
        installed_agents = set(self.source.installed("agents"))
        graph_mode = self.graph is not None
        categories = classification.categories if graph_mode else ()
        decisions = self._classify(text, installed_agents, categories)
        package = ContextPackage(
            task=task,
            project=self.source.project,
            profile=self.source.profile,
            decisions=decisions,
            items={},
            skipped={"agents": {}, "rules": {}, "workflows": {}, "stacks": {}},
            deduplicated=[],
            budget=self.budget,
            full_context_tokens=self._full_context(),
            mode="graph" if graph_mode else "direct",
            classification=classification,
        )
        if graph_mode and text:
            self._rank_agents(package)
            deep = any(
                d.layer == "L3" and d.status == LOADED and d.id != "09-security"
                for d in decisions.values()
            )
            package.tier, package.tier_reason = choose_tier(classification.categories, deep)
            package.tier_limit = self.tiers[package.tier]
        self._build(package, text)
        if graph_mode and text:
            self._rank_items(package, text)
            self._apply_budget(package, text)
        package.routing_time_ms = round((time.perf_counter() - started) * 1000, 2)
        return package

    def _build(self, package: ContextPackage, text: str) -> None:
        """(Re)build the items from the current decisions (deduplicated)."""
        package.items.clear()
        package.deduplicated.clear()
        package.skipped = {"agents": {}, "rules": {}, "workflows": {}, "stacks": {}}
        self._add_core(package)
        self._add_agents(package)
        self._add_rules(package, text)
        self._add_workflow(package, text)
        self._add_stacks(package, text)

    # Classification ---------------------------------------------------------------------
    def _classify(
        self, text: str, installed: set[str], categories: tuple[str, ...] = ()
    ) -> dict[str, AgentDecision]:
        agents_meta = self.meta["agents"]
        decisions: dict[str, AgentDecision] = {}
        for agent_id, spec in agents_meta.items():
            decision = AgentDecision(
                agent_id,
                spec.get("summary", agent_id),
                spec["layer"],
                installed=agent_id in installed,
            )
            if spec["layer"] != "L0":
                hits = match_triggers(spec.get("triggers", {}), text)
                decision.score = sum(w for _, w in hits)
                decision.matched = [t.rstrip("*") for t, _ in hits]
                decision.level = level_from_score(decision.score)
                if hits:
                    decision.reasons.append(f"Task mentions: {', '.join(decision.matched)}")
            decisions[agent_id] = decision
        for agent_id in sorted(installed - set(agents_meta)):  # custom agents: no metadata
            decisions[agent_id] = AgentDecision(agent_id, agent_id, "L1", installed=True)
        tasks_meta = self.meta.get("tasks", {})
        for category in categories:  # graph mode: task categories require agents
            for agent_id in tasks_meta.get(category, {}).get("requires", []):
                decision = decisions[agent_id]
                decision.required_by_task.append(category)
                if decision.level < MEDIUM:
                    decision.level = MEDIUM
                decision.reasons.append(f"Required by task category {category}")
        self._propagate(decisions)
        for decision in decisions.values():
            decision.status = self._status(decision, bool(text), decision.id in agents_meta)
        return decisions

    def _propagate(self, decisions: dict[str, AgentDecision]) -> None:
        """Apply 'requires' (capped at the edge level and the parent level) and
        'recommended' (LOW). Monotone, so it terminates; cycles are rejected upstream."""
        agents_meta = self.meta["agents"]
        for _ in range(len(decisions) * len(LEVELS) + 1):
            changed = False
            for parent_id, spec in agents_meta.items():
                parent = decisions[parent_id].level
                if parent < MEDIUM:
                    continue
                for child_id, edge in spec.get("requires", {}).items():
                    new_level = min(LEVELS.index(edge), parent)
                    child = decisions[child_id]
                    if new_level > child.level:
                        child.level = new_level
                        child.reasons.append(f"Required by {parent_id} ({LEVELS[new_level]})")
                        changed = True
                for child_id in spec.get("recommended", []):
                    child = decisions[child_id]
                    if child.level < LOW:
                        child.level = LOW
                        child.reasons.append(f"Recommended by {parent_id}")
                        changed = True
            if not changed:
                return

    @staticmethod
    def _status(decision: AgentDecision, has_task: bool, agent_id_known: bool) -> str:
        if decision.layer == "router":  # loaded only when the task is about context routing
            return LOADED if decision.level == HIGH and decision.installed else ROUTER
        if decision.layer == "L0":
            return CORE if decision.installed else NOT_INSTALLED
        if not agent_id_known or not has_task:
            return SKIPPED
        if not decision.installed:
            return NOT_INSTALLED if decision.level >= MEDIUM else SKIPPED
        if decision.level == NONE:
            return SKIPPED
        if decision.level == LOW:
            return CONSIDERED
        if decision.layer == "L3":
            return LOADED if decision.level == HIGH else TARGETED
        return LOADED

    # Package building -------------------------------------------------------------------
    def _add(self, package: ContextPackage, item: ContextItem) -> None:
        """Deduplication: an item is loaded once; extra requesters are merged and recorded."""
        key = (item.kind, item.id)
        existing = package.items.get(key)
        if existing is None:
            package.items[key] = item
            return
        new = [r for r in item.requested_by if r not in existing.requested_by]
        if new:
            existing.requested_by.extend(new)
            package.deduplicated.append(
                f"{existing.path} requested by {', '.join(existing.requested_by)}: loaded once"
            )

    def _tokens(self, path: str) -> tuple[str | None, int]:
        text = self.source.read(path)
        return text, estimate_tokens(text or "")

    def _add_core(self, package: ContextPackage) -> None:
        for path in CORE_FILES:
            text, tokens = self._tokens(path)
            if text is None:
                package.warnings.append(f"{path} not found (L0 core context incomplete)")
                continue
            reason = "L0: entry point" if path == "AGENTS.md" else "L0: compact project summary"
            self._add(
                package,
                ContextItem("core", path, path, "L0", "planning", tokens, reason, chars=len(text)),
            )
        if CORE_ID in self.source.installed("agents"):
            path = knowledge_path("agents", CORE_ID)
            text, tokens = self._tokens(path)
            self._add(
                package,
                ContextItem(
                    "agent",
                    CORE_ID,
                    path,
                    "L0",
                    "planning",
                    tokens,
                    "L0: orchestrator, receives the context package",
                    chars=len(text or ""),
                ),
            )

    def _add_agents(self, package: ContextPackage) -> None:
        skipped = package.skipped["agents"]
        for agent_id, decision in package.decisions.items():
            level = LEVELS[decision.level]
            why = "; ".join(decision.reasons)
            if decision.status == LOADED:
                path = knowledge_path("agents", agent_id)
                text, tokens = self._tokens(path)
                phase = (
                    "planning"
                    if agent_id == "04-architecture"
                    else ("review" if decision.layer == "L3" else "implementation")
                )
                layer = "L3" if decision.layer == "L3" else "L1"
                reason = f"{decision.title} ({level}). {why}".strip()
                self._add(
                    package,
                    ContextItem(
                        "agent",
                        agent_id,
                        path,
                        layer,
                        phase,
                        tokens,
                        reason,
                        chars=len(text or ""),
                    ),
                )
            elif decision.demoted:
                skipped[agent_id] = decision.skip_reason
            elif decision.status == TARGETED:
                skipped[agent_id] = (
                    f"Targeted review only ({level}): relevant rule sections "
                    f"are loaded instead of the full agent. {why}"
                )
            elif decision.status == CONSIDERED:
                skipped[agent_id] = f"Not loaded (LOW): {why}; AGENTS.md core rules apply"
            elif decision.status == NOT_INSTALLED:
                skipped[agent_id] = (
                    f"Needed ({level}) but not installed in this project; "
                    f"its rules are loaded. {why}"
                )
            elif decision.status == ROUTER:
                skipped[agent_id] = "Routing specialist: loaded only for context-optimisation tasks"
            elif decision.status == SKIPPED:
                if agent_id not in self.meta["agents"]:
                    skipped[agent_id] = "No routing metadata (custom agent): load it manually"
                elif not package.task.strip():
                    skipped[agent_id] = "No task given"
                elif decision.installed:
                    skipped[agent_id] = "Not related to the task (no trigger matched)"
                else:
                    skipped[agent_id] = "Not related to the task (not installed in this profile)"

    def _add_rules(self, package: ContextPackage, text: str) -> None:
        active = {
            a for a, d in package.decisions.items() if d.status in (LOADED, TARGETED, NOT_INSTALLED)
        }
        installed = set(self.source.installed("rules"))
        via_task = self._category_recommended_agents(package, active)
        for rule_id, spec in self.meta.get("rules", {}).items():
            if rule_id not in installed:
                continue
            owners = [a for a in spec.get("agents", []) if a in active]
            # graph mode: a task category recommending an agent that is not loaded brings in
            # that agent's rule sections (targeted), e.g. security task -> architecture rules
            categories = sorted({c for a in spec.get("agents", []) for c in via_task.get(a, [])})
            if not owners and not categories:
                package.skipped["rules"][rule_id] = "No selected agent needs these rules"
                continue
            path = knowledge_path("rules", rule_id)
            content = self.source.read(path) or ""
            sections, chosen = self._slice(content, spec.get("sections", {}), text)
            tokens = sum(s.tokens for s in chosen)
            chars = len(slice_text(content, chosen))
            review_only = (
                all(package.decisions[o].layer == "L3" for o in owners)
                if owners
                else (any(self.meta["agents"][a]["layer"] == "L3" for a in spec.get("agents", [])))
            )
            owners = [*owners, *(f"task.{c}" for c in categories)]
            reason = (
                "Whole file"
                if sections is None
                else f"{len(chosen) - 1} of {len(split_sections(content)) - 1} sections"
            )
            self._add(
                package,
                ContextItem(
                    "rule",
                    rule_id,
                    path,
                    "L1",
                    "review" if review_only else "implementation",
                    tokens,
                    f"{reason}, for {', '.join(owners)}",
                    list(owners),
                    sections,
                    chars=chars,
                ),
            )

    def _category_recommended_agents(
        self, package: ContextPackage, active: set[str]
    ) -> dict[str, list[str]]:
        """Agents recommended by a detected task category (weight >= category_rule_weight)
        that are not loaded: their rule sections are added. Graph mode only."""
        if self.graph is None or package.classification is None:
            return {}
        found: dict[str, list[str]] = {}
        tasks_meta = self.meta.get("tasks", {})
        for category in package.classification.categories:
            for agent_id, weight in tasks_meta.get(category, {}).get("recommends", {}).items():
                if weight >= self.ranking.category_rule_weight and agent_id not in active:
                    found.setdefault(agent_id, []).append(category)
        return found

    @staticmethod
    def _slice(content: str, meta_sections: Mapping[str, Any], text: str):
        """Context slicing: preamble + 'always' sections + sections whose triggers match.
        Sections without metadata (custom) are kept, so slicing never drops unknown rules."""
        all_sections = split_sections(content)
        chosen = []
        for section in all_sections:
            spec = meta_sections.get(section.heading)
            if (
                not section.heading
                or spec is None
                or spec.get("always")
                or match_triggers(spec.get("triggers", []), text)
            ):
                chosen.append(section)
        if len(chosen) == len(all_sections):
            return None, chosen
        return [
            {"heading": s.heading or "(preamble)", "lines": [s.start, s.end]} for s in chosen
        ], chosen

    def _add_workflow(self, package: ContextPackage, text: str) -> None:
        installed = set(self.source.installed("workflows"))
        candidates = [(w, s) for w, s in self.meta.get("workflows", {}).items() if w in installed]
        if not text or not candidates:
            for workflow_id in installed:
                package.skipped["workflows"][workflow_id] = "No task given"
            return
        scored = [
            (sum(wt for _, wt in match_triggers(s.get("triggers", {}), text)), w, s)
            for w, s in candidates
        ]
        best_score, best_id, _ = max(scored, key=lambda x: x[0])  # first wins on ties
        if best_score == 0:
            best_id = next((w for w, s in candidates if s.get("default")), candidates[0][0])
            reason = "Default workflow (no specific trigger matched)"
        else:
            hits = match_triggers(dict(candidates)[best_id].get("triggers", {}), text)
            reason = f"Task mentions: {', '.join(t.rstrip('*') for t, _ in hits)}"
        path = knowledge_path("workflows", best_id)
        content, tokens = self._tokens(path)
        self._add(
            package,
            ContextItem(
                "workflow",
                best_id,
                path,
                "L1",
                "planning",
                tokens,
                reason,
                chars=len(content or ""),
            ),
        )
        for workflow_id in sorted(installed - {best_id}):
            package.skipped["workflows"][workflow_id] = "One primary workflow per task"

    def _add_stacks(self, package: ContextPackage, text: str) -> None:
        stacks_meta = self.meta.get("stacks", {})
        installed = set(self.source.installed("stacks"))
        domain_agents = self.meta.get("domains", {})
        active: dict[str, list[str]] = {}
        for domain, owners in domain_agents.items():
            hits = [
                o
                for o in owners
                if package.decisions[o].level >= MEDIUM
                and package.decisions[o].status != ROUTER
                and not package.decisions[o].demoted  # left out by ranking/budget
            ]
            if hits:
                active[domain] = hits
        if set(active) & {"frontend", "backend", "database", "data"}:
            active.pop("language", None)  # language is only a fallback
        selected: dict[str, tuple[str, list[str]]] = {}
        for stack_id, spec in stacks_meta.items():
            hits = match_triggers(spec.get("triggers", {}), text)
            domains = [d for d in spec.get("domains", []) if d in active]
            if stack_id not in installed:
                if hits:
                    package.skipped["stacks"][stack_id] = (
                        "Mentioned in the task but not installed in this project "
                        f"(add it with: ai-project init . --force --stacks {stack_id})"
                    )
                continue
            requesters = [a for d in domains for a in active[d]]
            if hits:
                requesters.append("task")
            if requesters:
                why = (f"Domain {', '.join(domains)}" if domains else "") + (
                    (" + " if domains and hits else "")
                    + (f"mentioned: {', '.join(t.rstrip('*') for t, _ in hits)}" if hits else "")
                )
                selected[stack_id] = (why, list(dict.fromkeys(requesters)))
        for stack_id in list(selected):
            for companion in stacks_meta[stack_id].get("companions", []):
                if companion in installed:
                    reason, requesters = selected.get(companion, (f"Companion of {stack_id}", []))
                    selected[companion] = (reason, [*requesters, f"companion:{stack_id}"])
        if self.graph is not None:  # dependency expansion: fastapi -> python, kubernetes -> docker
            named = [f"stack.{s}" for s, (_, r) in selected.items() if "task" in r]
            for node_id in expand_dependencies(self.graph, named):
                stack_id = node_id.split(".", 1)[1]
                if node_id.startswith("stack.") and stack_id in installed and node_id not in named:
                    reason, requesters = selected.get(stack_id, ("Dependency of a named stack", []))
                    selected[stack_id] = (reason, [*requesters, "dependency"])
        for stack_id, (reason, requesters) in selected.items():
            path = knowledge_path("stacks", stack_id)
            content, tokens = self._tokens(path)
            for requester in requesters:  # every requester is recorded, the file is loaded once
                self._add(
                    package,
                    ContextItem(
                        "stack",
                        stack_id,
                        path,
                        "L2",
                        "implementation",
                        tokens,
                        reason,
                        [requester],
                        chars=len(content or ""),
                    ),
                )
        for stack_id in sorted(installed - set(selected)):
            if stack_id not in stacks_meta:
                package.skipped["stacks"][stack_id] = "No routing metadata: load it manually"
            else:
                package.skipped["stacks"][stack_id] = (
                    "No task given" if not text else "Technology not involved in this task"
                )

    # Graph mode: relevance, ranking, budget ---------------------------------------------------
    def _profile_name(self) -> str | None:
        return self.selection.get("profile") or self.source.profile

    def _seeds(self, package: ContextPackage, required_agents: set[str]) -> dict[str, float]:
        """Traversal starts from what the task is certainly about."""
        classification = _need(package.classification, "classification")
        seeds = {f"task.{c}": 1.0 for c in classification.categories}
        seeds.update({f"agent.{a}": 1.0 for a in required_agents})
        seeds.update({f"stack.{s}": 1.0 for s in classification.technologies})
        return seeds

    def _required_agents(self, package: ContextPackage) -> set[str]:
        """REQUIRED = strong task match, task category, protected (security/testing) at
        MEDIUM+, the routing specialist when asked for, or 'requires' from a REQUIRED agent."""
        dec, cfg, meta_agents = package.decisions, self.ranking, self.meta["agents"]
        live = {
            a
            for a, d in dec.items()
            if a in meta_agents
            and d.layer != "L0"
            and d.status in (LOADED, TARGETED, NOT_INSTALLED)
        }
        required = {
            a
            for a in live
            if dec[a].score >= 2
            or dec[a].required_by_task
            or dec[a].layer == "router"
            or (a in cfg.protected_agents and dec[a].level >= MEDIUM)
        }
        changed = True
        while changed:  # bounded: the set only grows, at most len(live) rounds
            changed = False
            for parent in sorted(required):
                for child, edge in meta_agents[parent].get("requires", {}).items():
                    if LEVELS.index(edge) >= MEDIUM and child in live and child not in required:
                        required.add(child)
                        changed = True
        return required

    def _rank_agents(self, package: ContextPackage) -> None:
        dec, cfg = package.decisions, self.ranking
        graph = _need(self.graph, "graph")
        required = self._required_agents(package)
        reached = traverse_graph(graph, self._seeds(package, required), cfg.max_depth)
        profile = self._profile_name()
        for agent_id in sorted(dec):
            d = dec[agent_id]
            if (
                agent_id not in self.meta["agents"]
                or d.layer == "L0"
                or d.status in (SKIPPED, ROUTER)
            ):
                continue
            node = f"agent.{agent_id}"
            reasons = [f"task matched: {', '.join(d.matched)}"] if d.matched else []
            reasons += [f"required by task category {c}" for c in d.required_by_task]
            dependency = 0.0
            for e in graph.incoming(node, ["requires", "recommends"]):
                parent = e.source.split(".", 1)[1]
                if e.source.startswith("agent.") and parent in required:
                    dependency = max(dependency, 1.0 if e.type == "requires" else 0.5)
                    verb = "required" if e.type == "requires" else "recommended"
                    reasons.append(f"{verb} by {parent}")
            weight, via = reached.get(node, (0.0, ""))
            if weight and via != node:
                reasons.append(f"graph: reached from {via} (weight {weight:.2f})")
            profile_match = (
                1.0
                if any(e.source == f"profile.{profile}" for e in graph.incoming(node, ["requires"]))
                else 0.0
            )
            if profile_match:
                reasons.append(f"profile {profile} includes it")
            if agent_id in cfg.protected_agents and d.level >= MEDIUM:
                reasons.append("protected: security and tests are never dropped for budget")
            tokens = (graph.nodes[node].tokens or 0) if node in graph.nodes else 0
            d.rank = score_candidate(
                cfg,
                {
                    "task_match": 1.0
                    if d.required_by_task
                    else task_match_from_trigger_score(d.score),
                    "graph_weight": weight,
                    "profile_match": profile_match,
                    "technology_match": 0.0,
                    "dependency_bonus": dependency,
                    "token_cost": token_cost(tokens, self.budget["max_agent_context"]),
                },
                reasons,
            )
            if d.status == CONSIDERED:
                d.relevance = OPTIONAL
            else:
                d.relevance = REQUIRED if agent_id in required else RECOMMENDED
            if (
                d.relevance == RECOMMENDED
                and d.status in (LOADED, TARGETED)
                and d.rank.value < cfg.min_recommended_score
            ):
                d.status, d.demoted = CONSIDERED, True
                d.skip_reason = (
                    f"RECOMMENDED but low relevance: score {d.rank.value:.2f} < threshold "
                    f"{cfg.min_recommended_score:.2f} ({'; '.join(reasons) or 'no strong signal'})"
                )

    def _rank_items(self, package: ContextPackage, text: str) -> None:
        """Relevance + score for every selected item; drop low-relevance RECOMMENDED stacks."""
        graph = _need(self.graph, "graph")
        classification = _need(package.classification, "classification")
        dec, cfg = package.decisions, self.ranking
        required_agents = {a for a, d in dec.items() if d.relevance == REQUIRED and not d.demoted}
        named = {i.id for i in package.by_kind("stack") if "task" in i.requested_by}
        named |= set(classification.technologies) & set(self.source.installed("stacks"))
        required_stacks = set(expand_dependencies(graph, [f"stack.{s}" for s in named]))
        reached = traverse_graph(graph, self._seeds(package, required_agents), cfg.max_depth)
        tech_nodes = {
            f"technology.{self.selection.get('technology')}",
            f"database.{self.selection.get('database')}",
        }
        stacks_meta = self.meta.get("stacks", {})
        for item in list(package.items.values()):
            if item.kind == "core" or (item.kind == "agent" and item.id == CORE_ID):
                item.relevance, item.rank = REQUIRED, Score(1.0, {}, ["L0 core: always loaded"])
            elif item.kind == "agent":
                d = dec[item.id]
                item.relevance, item.rank = d.relevance or REQUIRED, d.rank
            elif item.kind == "rule" and not any(o in dec for o in item.requested_by):
                item.relevance = RECOMMENDED  # brought in by a task category only
                weight = self._category_rule_weight(item)
                item.rank = score_candidate(
                    cfg,
                    {
                        "graph_weight": weight,
                        "profile_match": 1.0,
                        "dependency_bonus": 0.5,
                    },
                    [
                        f"targeted rule sections recommended by {', '.join(item.requested_by)} "
                        f"(weight {weight:.2f})"
                    ],
                )
            elif item.kind == "rule":
                owners = [dec[o] for o in item.requested_by if o in dec]
                item.relevance = (
                    REQUIRED if any(o.relevance == REQUIRED for o in owners) else (RECOMMENDED)
                )
                ranked = [o.rank for o in owners if o.rank is not None]
                best = max(ranked, key=lambda r: r.value) if ranked else Score(1.0, {}, [])
                item.rank = Score(
                    best.value,
                    best.components,
                    [f"rules of {', '.join(item.requested_by)} (follow their owners)"],
                )
            elif item.kind == "workflow":
                hits = match_triggers(self.meta["workflows"][item.id].get("triggers", {}), text)
                weight, via = reached.get(f"workflow.{item.id}", (0.0, ""))
                reasons = [item.reason] + ([f"graph: related to {via}"] if weight else [])
                item.relevance = REQUIRED
                item.rank = score_candidate(
                    cfg,
                    {
                        "task_match": task_match_from_trigger_score(sum(w for _, w in hits)),
                        "graph_weight": weight,
                        "profile_match": 1.0,
                    },
                    reasons,
                )
            elif item.kind == "stack":
                self._rank_stack(
                    package,
                    item,
                    text,
                    required_agents,
                    required_stacks,
                    reached,
                    tech_nodes,
                    stacks_meta,
                )

    def _category_rule_weight(self, item: ContextItem) -> float:
        rule_agents = self.meta["rules"].get(item.id, {}).get("agents", [])
        weights = [
            self.meta["tasks"][r[5:]]["recommends"].get(a, 0.0)
            for r in item.requested_by
            if r.startswith("task.") and r[5:] in self.meta["tasks"]
            for a in rule_agents
        ]
        return max(weights, default=0.0)

    def _rank_stack(
        self,
        package,
        item,
        text,
        required_agents,
        required_stacks,
        reached,
        tech_nodes,
        stacks_meta,
    ) -> None:
        graph = _need(self.graph, "graph")
        cfg, node = self.ranking, f"stack.{item.id}"
        spec = stacks_meta.get(item.id, {})
        hits = match_triggers(spec.get("triggers", {}), text)
        reasons = (
            [f"named in the task: {', '.join(t.rstrip('*') for t, _ in hits)}"] if hits else []
        )
        if node in required_stacks and not hits:
            reasons.append("dependency of a stack named in the task")
        owners = [e.target.split(".", 1)[1] for e in graph.outgoing(node, ["implemented_by"])]
        dependency = 0.0
        if any(o in required_agents for o in owners):
            dependency = 0.5
            reasons.append(
                f"domain of required agent {', '.join(o for o in owners if o in required_agents)}"
            )
        elif any(
            package.decisions[o].status in (LOADED, TARGETED)
            for o in owners
            if o in package.decisions
        ):
            dependency = 0.25
        weight, via = reached.get(node, (0.0, ""))
        if weight and via != node:
            reasons.append(f"graph: reached from {via} (weight {weight:.2f})")
        technology = (
            1.0
            if (
                spec.get("domains", []) != ["infra"]
                and any(e.source in tech_nodes for e in graph.incoming(node, ["uses"]))
            )
            else 0.0
        )
        if technology:
            reasons.append("project technology uses it")
        conflicts = [
            e.target
            for e in graph.outgoing(node, ["conflicts_with"])
            if e.target in required_stacks
        ]
        if conflicts:
            reasons.append(f"conflicts with required {', '.join(conflicts)}")
        item.rank = score_candidate(
            cfg,
            {
                "task_match": task_match_from_trigger_score(sum(w for _, w in hits)),
                "graph_weight": weight,
                "profile_match": 1.0,  # installed by the project's profile/technology
                "technology_match": technology,
                "dependency_bonus": dependency,
                "token_cost": token_cost(item.tokens, self.budget["max_stack_context"]),
                "redundancy_penalty": cfg.redundancy_penalty if conflicts else 0.0,
            },
            reasons,
        )
        item.relevance = REQUIRED if node in required_stacks else RECOMMENDED
        package.stack_ranks[item.id] = (item.relevance, item.rank)
        if item.relevance == RECOMMENDED and item.rank.value < cfg.min_recommended_score:
            package.items.pop(("stack", item.id))
            package.skipped["stacks"][item.id] = (
                f"RECOMMENDED but low relevance: score {item.rank.value:.2f} < threshold "
                f"{cfg.min_recommended_score:.2f}"
            )

    def _apply_budget(self, package: ContextPackage, text: str) -> None:
        """Keep RECOMMENDED agents/stacks by score while the tier allows. REQUIRED items are
        never removed (security, correctness and tests come before tokens)."""
        tier_limit = _need(package.tier_limit, "tier limit")
        for _ in range(len(package.decisions) + 2):  # each round removes >= 1 agent or ends
            recommended = [
                i
                for i in package.items.values()
                if i.relevance == RECOMMENDED and i.kind in ("agent", "stack") and i.rank
            ]
            base = package.totals["total"] - sum(i.tokens for i in recommended)
            result = slice_to_budget(
                [
                    Candidate(f"{i.kind}:{i.id}", i.tokens, RECOMMENDED, i.rank.value)
                    for i in recommended
                    if i.rank is not None
                ],
                tier_limit,
                self.ranking.min_recommended_score,
                base,
            )
            dropped_agent = False
            for key, reason in result.dropped.items():
                kind, item_id = key.split(":", 1)
                if kind == "agent":
                    d = package.decisions[item_id]
                    d.status, d.demoted = CONSIDERED, True
                    d.skip_reason = f"RECOMMENDED but left out: {reason}"
                    dropped_agent = True
                else:
                    package.items.pop(("stack", item_id), None)
                    package.skipped["stacks"][item_id] = f"RECOMMENDED but left out: {reason}"
            if not dropped_agent:
                return
            self._build(package, text)  # its rule sections and domain stacks go with it
            self._rank_items(package, text)

    # Full context (for the reduction metric) ------------------------------------------------
    def _full_context(self) -> int:
        """What loading everything would cost: core + every installed knowledge file."""
        total = sum(estimate_tokens(self.source.read(p) or "") for p in CORE_FILES)
        for kind in ("agents", "rules", "workflows", "stacks"):
            for item_id in self.source.installed(kind):
                path = knowledge_path(kind, item_id)
                cached = self.source.cached_tokens(path)
                total += (
                    cached if cached is not None else estimate_tokens(self.source.read(path) or "")
                )
        return total
