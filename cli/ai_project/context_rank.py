"""Task classification and context ranking (deterministic, explainable, no ML).

Classification: each task category in ``catalog/context.json`` (``tasks``) has weighted
triggers; a category is detected when its score reaches ``CATEGORY_THRESHOLD``.
Technologies are detected from stack triggers.

Ranking: every candidate gets a score in [0, 1]:

    score = sum(weight_i * component_i)          # task, graph, profile, technology, dependency
            - weight_token_cost * token_cost
            - redundancy_penalty

All components are in [0, 1] and returned with the score, so every number is explainable.
Weights come from ``catalog/context.json`` (``ranking``), with the defaults below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CATEGORY_THRESHOLD = 2
TASK_MATCH_SATURATION = 3  # a trigger score of 3 or more is a full task match

DEFAULT_WEIGHTS = {
    "task_match": 0.35,
    "graph_weight": 0.30,
    "profile_match": 0.05,
    "technology_match": 0.20,
    "dependency_bonus": 0.15,
    "token_cost": 0.05,
}
POSITIVE_COMPONENTS = (
    "task_match",
    "graph_weight",
    "profile_match",
    "technology_match",
    "dependency_bonus",
)


@dataclass(frozen=True)
class RankingConfig:
    weights: Mapping[str, float]
    redundancy_penalty: float = 0.2
    min_recommended_score: float = 0.30
    protected_agents: tuple[str, ...] = ("09-security", "10-testing")
    max_depth: int = 3
    category_rule_weight: float = 0.5

    @classmethod
    def from_meta(cls, meta: Mapping[str, Any]) -> RankingConfig:
        ranking = meta.get("ranking", {})
        return cls(
            weights={**DEFAULT_WEIGHTS, **ranking.get("weights", {})},
            redundancy_penalty=float(ranking.get("redundancy_penalty", 0.2)),
            min_recommended_score=float(ranking.get("min_recommended_score", 0.30)),
            protected_agents=tuple(ranking.get("protected_agents", cls.protected_agents)),
            max_depth=int(ranking.get("max_depth", 3)),
            category_rule_weight=float(ranking.get("category_rule_weight", 0.5)),
        )


@dataclass(frozen=True)
class Classification:
    categories: tuple[str, ...]
    matches: Mapping[str, tuple[str, ...]]  # category -> matched triggers
    technologies: tuple[str, ...]  # stack ids named in the task

    @property
    def labels(self) -> list[str]:
        return [*self.categories, *self.technologies]

    def to_dict(self) -> dict[str, Any]:
        return {
            "categories": list(self.categories),
            "technologies": list(self.technologies),
            "matched_triggers": {c: list(t) for c, t in self.matches.items()},
        }


def classify_task(text: str, meta: Mapping[str, Any], match_triggers) -> Classification:
    """``text`` is the normalized task; ``match_triggers`` is the router's matcher."""
    scored = []
    matches: dict[str, tuple[str, ...]] = {}
    for order, (category, spec) in enumerate(meta.get("tasks", {}).items()):
        hits = match_triggers(spec.get("triggers", {}), text)
        score = sum(w for _, w in hits)
        if score >= CATEGORY_THRESHOLD:
            scored.append((-score, order, category))
            matches[category] = tuple(t.rstrip("*") for t, _ in hits)
    technologies = tuple(
        stack
        for stack, spec in meta.get("stacks", {}).items()
        if any(w >= 2 for _, w in match_triggers(spec.get("triggers", {}), text))
    )
    categories = tuple(c for _, _, c in sorted(scored))
    return Classification(categories, {c: matches[c] for c in categories}, technologies)


@dataclass
class Score:
    value: float
    components: dict[str, float]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.value, "components": self.components, "reasons": self.reasons}


def task_match_from_trigger_score(trigger_score: int) -> float:
    return min(1.0, trigger_score / TASK_MATCH_SATURATION) if trigger_score > 0 else 0.0


def token_cost(tokens: int, limit: int) -> float:
    return min(1.0, tokens / limit) if limit > 0 else 0.0


def score_candidate(
    config: RankingConfig, components: Mapping[str, float], reasons: list[str] | None = None
) -> Score:
    """Combine components (each clamped to [0, 1]) into a score in [0, 1]."""
    values = {
        k: round(min(1.0, max(0.0, float(components.get(k, 0.0)))), 3)
        for k in (*POSITIVE_COMPONENTS, "token_cost", "redundancy_penalty")
    }
    weights = config.weights
    total = sum(weights.get(k, 0.0) * values[k] for k in POSITIVE_COMPONENTS)
    total -= weights.get("token_cost", 0.0) * values["token_cost"]
    total -= values["redundancy_penalty"]
    return Score(round(min(1.0, max(0.0, total)), 3), values, list(reasons or []))
