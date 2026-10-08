"""Context budget: limits, tiers and the budget slicer.

Budgets are ESTIMATED tokens (characters / 4). They limit how much context the kit prepares;
they do not control or measure the tokens billed by any AI provider.

Slicing policy (priority order: correctness > security > architecture > testing >
maintainability > context efficiency):

* REQUIRED items are always kept, even over budget (status OVER_BUDGET is reported);
* RECOMMENDED items are kept by descending score while ``score >= min_recommended_score``
  and the tier limit allows;
* OPTIONAL items are listed, never loaded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from ai_project.context_index import BUDGET_PATH
from ai_project.errors import KitError

REQUIRED, RECOMMENDED, OPTIONAL = "REQUIRED", "RECOMMENDED", "OPTIONAL"

# Calibrated on measured packages: planning ~6.5k, typical totals 12k-17k estimated.
DEFAULT_BUDGET = {
    "default_token_budget": 20000,
    "planning_budget": 8000,
    "implementation_budget": 10000,
    "review_budget": 5000,
    "max_agent_context": 2500,
    "max_stack_context": 2500,
}
PHASE_BUDGET_KEYS = {
    "planning": "planning_budget",
    "implementation": "implementation_budget",
    "review": "review_budget",
}
# Tier limits, calibrated on the reference tasks measured with the graph router.
DEFAULT_TIERS = {"simple": 12000, "normal": 16000, "complex": 24000, "security": 24000}
TIER_NAMES = tuple(DEFAULT_TIERS)
COMPLEX_DOMAINS = frozenset({"frontend", "backend", "database", "deployment", "performance"})
_MAX_VALUE = 10_000_000


def _positive_int(value: Any, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= _MAX_VALUE:
        raise KitError(f"{where} must be a positive integer.")
    return value


def _load(text: str | None, source: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise KitError(f"{source} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise KitError(f"{source} must be a JSON object.")
    return data


def parse_budget(text: str | None, source: str = BUDGET_PATH) -> dict[str, int]:
    """Validate a budget file. Missing keys fall back to defaults; bad values are errors.
    The optional ``budgets`` block (tier limits) is validated too (see ``parse_tiers``)."""
    budget = dict(DEFAULT_BUDGET)
    data = _load(text, source)
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if key == "budgets":
            parse_tiers(text, source)
            continue
        if key not in DEFAULT_BUDGET:
            raise KitError(
                f"{source}: unknown key '{key}'. Known: {', '.join([*DEFAULT_BUDGET, 'budgets'])}"
            )
        budget[key] = _positive_int(value, f"{source}: '{key}'")
    return budget


def parse_tiers(text: str | None, source: str = BUDGET_PATH) -> dict[str, int]:
    """Tier limits. Missing tiers use the defaults. A single-budget file
    (``default_token_budget`` without ``budgets``) applies that one value to every tier."""
    data = _load(text, source)
    tiers = dict(DEFAULT_TIERS)
    if "default_token_budget" in data and "budgets" not in data:
        # Single-budget file: the same limit applies to every task.
        single = _positive_int(data["default_token_budget"], f"{source}: default_token_budget")
        return dict.fromkeys(tiers, single)
    raw = data.get("budgets", {})
    if not isinstance(raw, dict):
        raise KitError(f"{source}: 'budgets' must be an object.")
    for name, value in raw.items():
        if name not in DEFAULT_TIERS:
            raise KitError(
                f"{source}: unknown budget tier '{name}'. Known: {', '.join(TIER_NAMES)}"
            )
        tiers[name] = _positive_int(value, f"{source}: budgets.{name}")
    return tiers


def choose_tier(categories: Iterable[str], deep_review: bool) -> tuple[str, str]:
    """Pick the tier from the classification. Returns (tier, reason)."""
    cats = set(categories)
    if "security" in cats:
        return "security", "security task"
    domains = cats & COMPLEX_DOMAINS
    if "new_project" in cats:
        return "complex", "new project"
    if len(domains) >= 3:
        return "complex", f"{len(domains)} domains: {', '.join(sorted(domains))}"
    if deep_review:
        return "complex", "deep review (L3) requested"
    if len(cats) <= 1:
        return "simple", "single category" if cats else "no category detected"
    return "normal", f"{len(cats)} categories"


@dataclass(frozen=True)
class Candidate:
    key: str
    tokens: int
    relevance: str  # REQUIRED | RECOMMENDED | OPTIONAL
    score: float


@dataclass
class SliceResult:
    selected: list[str]
    dropped: dict[str, str] = field(default_factory=dict)
    required_tokens: int = 0
    total_tokens: int = 0
    limit: int = 0

    @property
    def over_budget(self) -> bool:
        return self.required_tokens > self.limit


def slice_to_budget(
    candidates: Iterable[Candidate], limit: int, min_score: float, base_tokens: int = 0
) -> SliceResult:
    """Greedy, deterministic selection. ``base_tokens`` = context already committed
    (core files, workflow...). Required items are never dropped."""
    items = sorted(candidates, key=lambda c: c.key)
    required = [c for c in items if c.relevance == REQUIRED]
    result = SliceResult([c.key for c in required], limit=limit)
    total = base_tokens + sum(c.tokens for c in required)
    result.required_tokens = total
    for c in items:
        if c.relevance == OPTIONAL:
            result.dropped[c.key] = "optional: listed, not loaded"
    recommended = sorted(
        (c for c in items if c.relevance == RECOMMENDED), key=lambda c: (-c.score, c.key)
    )
    for c in recommended:
        if c.score < min_score:
            result.dropped[c.key] = (
                f"low relevance: score {c.score:.2f} < threshold {min_score:.2f}"
            )
        elif total + c.tokens > limit:
            result.dropped[c.key] = (
                f"budget: +{c.tokens:,} would exceed the tier limit {limit:,} (at {total:,})"
            )
        else:
            result.selected.append(c.key)
            total += c.tokens
    result.total_tokens = total
    return result
