"""Context index: token estimates, section slicing and routing metadata.

Token counts are ESTIMATES (characters / 4). They are not the token count of any AI
provider (Claude, OpenAI, Copilot...), and the kit does not control provider billing.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from ai_project.errors import KitError

CHARS_PER_TOKEN = 4
ESTIMATION_NOTE = (
    "Token counts are estimates (characters / 4), not the provider's actual token count."
)
INDEX_PATH = ".ai/context/index.json"
BUDGET_PATH = ".ai/context/budget.json"
CORE_FILES = ("AGENTS.md", ".ai/context/project.md")
LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH")
LAYERS = ("L0", "L1", "L3", "router")
KINDS = ("agents", "rules", "workflows", "stacks")
INDEX_SCHEMA = 1

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_TRIGGER = re.compile(r"^[a-z0-9][a-z0-9 +#./-]{0,40}\*?$")


def estimate_tokens(text: str) -> int:
    """Deterministic, local estimate: ceil(characters / 4)."""
    return math.ceil(len(text) / CHARS_PER_TOKEN) if text else 0


def knowledge_path(kind: str, item_id: str) -> str:
    """Where a knowledge item lives in a generated project."""
    if not _ID.match(item_id):
        raise KitError(f"Invalid {kind} identifier: {item_id!r}")
    if kind == "stacks":
        return f".ai/stacks/{item_id}/README.md"
    return f".ai/{kind}/{item_id}.md"


@dataclass(frozen=True)
class Section:
    heading: str  # "" for the preamble (title + notice before the first H2)
    start: int  # 1-based, inclusive
    end: int  # 1-based, inclusive
    tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {"heading": self.heading, "lines": [self.start, self.end], "tokens": self.tokens}


def split_sections(text: str) -> list[Section]:
    """Split Markdown on H2 headings outside fenced code blocks. Lines are 1-based."""
    lines = text.splitlines()
    starts: list[tuple[int, str]] = [(1, "")]
    in_code = False
    for number, line in enumerate(lines, start=1):
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("## "):
            starts.append((number, line[3:].strip()))
    sections = []
    for i, (start, heading) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else len(lines)
        if end < start:
            continue
        body = "\n".join(lines[start - 1 : end])
        sections.append(Section(heading, start, end, estimate_tokens(body)))
    return sections


def slice_text(text: str, sections: Iterable[Section]) -> str:
    """Return only the given sections (used by assistants or tools that load slices)."""
    lines = text.splitlines()
    return "\n".join("\n".join(lines[s.start - 1 : s.end]) for s in sections)


# --- Metadata validation ---------------------------------------------------------------------
def load_routing(kit_root: Path) -> dict[str, Any]:
    path = kit_root / "catalog" / "context.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KitError(f"Cannot read routing metadata {path}: {exc}") from None
    validate_routing(data)
    return data


def validate_routing(meta: Mapping[str, Any]) -> None:
    """Reject malformed metadata, unknown references and circular 'requires' chains.

    Metadata is data only: it is never evaluated, imported or executed.
    """
    if not isinstance(meta, Mapping):
        raise KitError("Routing metadata must be a JSON object.")
    agents = _mapping(meta, "agents")
    rules = _mapping(meta, "rules")
    stacks = _mapping(meta, "stacks")
    workflows = _mapping(meta, "workflows")
    domains = _mapping(meta, "domains")
    for collection in (agents, rules, stacks, workflows):
        for item_id in collection:
            if not _ID.match(item_id):
                raise KitError(f"Invalid identifier in routing metadata: {item_id!r}")

    for agent_id, spec in agents.items():
        where = f"agents.{agent_id}"
        if spec.get("layer") not in LAYERS:
            raise KitError(f"{where}.layer must be one of {LAYERS}")
        _check_triggers(spec.get("triggers", {}), where)
        requires = spec.get("requires", {})
        if not isinstance(requires, Mapping):
            raise KitError(f"{where}.requires must be an object")
        for target, level in requires.items():
            _known(target, agents, f"{where}.requires")
            if level not in LEVELS[1:]:
                raise KitError(f"{where}.requires.{target} must be LOW, MEDIUM or HIGH")
        for key in ("recommended", "optional"):
            for target in spec.get(key, []):
                _known(target, agents, f"{where}.{key}")
        for domain in spec.get("domains", []):
            _known(domain, domains, f"{where}.domains")
    for domain, owners in domains.items():
        for owner in owners:
            _known(owner, agents, f"domains.{domain}")
    for rule_id, spec in rules.items():
        for owner in spec.get("agents", []):
            _known(owner, agents, f"rules.{rule_id}.agents")
        for heading, section in spec.get("sections", {}).items():
            _check_triggers(section.get("triggers", []), f"rules.{rule_id}.{heading}")
    for stack_id, spec in stacks.items():
        _check_triggers(spec.get("triggers", {}), f"stacks.{stack_id}")
        for domain in spec.get("domains", []):
            _known(domain, domains, f"stacks.{stack_id}.domains")
        for companion in spec.get("companions", []):
            _known(companion, stacks, f"stacks.{stack_id}.companions")
    for workflow_id, spec in workflows.items():
        _check_triggers(spec.get("triggers", {}), f"workflows.{workflow_id}")

    cycle = find_cycle({a: list(s.get("requires", {})) for a, s in agents.items()})
    if cycle:
        raise KitError("Circular agent dependency: " + " -> ".join(cycle))
    _validate_v12_blocks(meta, agents, stacks, workflows)


def _validate_v12_blocks(meta, agents, stacks, workflows) -> None:
    """v1.2 additions: stack relations, task categories, tools, ranking (all optional)."""
    for stack_id, spec in stacks.items():
        where = f"stacks.{stack_id}"
        for key in ("depends_on", "specializes", "conflicts"):
            for target in spec.get(key, []):
                _known(target, stacks, f"{where}.{key}")
        for target, weight in spec.get("related", {}).items():
            _known(target, stacks, f"{where}.related")
            _check_weight(weight, f"{where}.related.{target}")
    cycle = find_cycle(
        {
            s: [
                *spec.get("depends_on", []),
                *spec.get("specializes", []),
                *spec.get("companions", []),
            ]
            for s, spec in stacks.items()
        }
    )
    if cycle:
        raise KitError("Circular stack dependency: " + " -> ".join(cycle))
    for task_id, spec in _mapping(meta, "tasks").items():
        where = f"tasks.{task_id}"
        if not _ID.match(task_id):
            raise KitError(f"Invalid identifier in routing metadata: {task_id!r}")
        _check_triggers(spec.get("triggers", {}), where)
        for target in spec.get("requires", []):
            _known(target, agents, f"{where}.requires")
        for target, weight in spec.get("recommends", {}).items():
            _known(target, agents, f"{where}.recommends")
            _check_weight(weight, f"{where}.recommends.{target}")
        if spec.get("workflow"):
            _known(spec["workflow"], workflows, f"{where}.workflow")
    for tool_id, spec in _mapping(meta, "tools").items():
        if not _ID.match(tool_id):
            raise KitError(f"Invalid identifier in routing metadata: {tool_id!r}")
        for target in spec.get("stacks", []):
            _known(target, stacks, f"tools.{tool_id}.stacks")
        for target in spec.get("validates", []):
            _known(target, agents, f"tools.{tool_id}.validates")
    ranking = _mapping(meta, "ranking")
    for name, weight in ranking.get("weights", {}).items():
        if name not in RANKING_COMPONENTS:
            raise KitError(f"ranking.weights: unknown component '{name}'")
        _check_weight(weight, f"ranking.weights.{name}")
    for key in ("redundancy_penalty", "min_recommended_score", "category_rule_weight"):
        if key in ranking:
            _check_weight(ranking[key], f"ranking.{key}")
    for target in ranking.get("protected_agents", []):
        _known(target, agents, "ranking.protected_agents")
    depth = ranking.get("max_depth", 3)
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 10:
        raise KitError("ranking.max_depth must be an integer 1-10")


RANKING_COMPONENTS = (
    "task_match",
    "graph_weight",
    "profile_match",
    "technology_match",
    "dependency_bonus",
    "token_cost",
)


def _check_weight(value: Any, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise KitError(f"{where} must be a number between 0 and 1")


def find_cycle(graph: Mapping[str, list[str]]) -> list[str] | None:
    """Return one dependency cycle (``a -> b -> a``) or None. Iterative DFS, no recursion."""
    white, grey, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    for root in graph:
        if color[root] != white:
            continue
        stack: list[tuple[str, Iterator[str]]] = [(root, iter(graph.get(root, [])))]
        path = [root]
        color[root] = grey
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                color[node] = black
                stack.pop()
                path.pop()
            elif color.get(child, white) == grey:
                return [*path[path.index(child) :], child]
            elif color.get(child, white) == white:
                color[child] = grey
                path.append(child)
                stack.append((child, iter(graph.get(child, []))))
    return None


def _mapping(meta: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = meta.get(key, {})
    if not isinstance(value, Mapping):
        raise KitError(f"Routing metadata '{key}' must be an object.")
    return value


def _known(item: str, collection: Mapping[str, Any], where: str) -> None:
    if item not in collection:
        raise KitError(f"Unknown reference '{item}' in {where}")


def _check_triggers(triggers: Any, where: str) -> None:
    items = triggers.items() if isinstance(triggers, Mapping) else ((t, 1) for t in triggers)
    for trigger, weight in items:
        if not isinstance(trigger, str) or not _TRIGGER.match(trigger):
            raise KitError(f"Invalid trigger {trigger!r} in {where}")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 5:
            raise KitError(f"Trigger weight for {trigger!r} in {where} must be an integer 1-5")


# --- Index ------------------------------------------------------------------------------------
def build_index(
    files: Mapping[str, str],
    meta: Mapping[str, Any],
    catalog_info: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    """Build ``.ai/context/index.json`` from the knowledge files of a project.

    Derived artefact (v1.2): regenerated by ``update``; never edit it by hand. Compact on
    purpose (one entry per line): assistants read it to discover what exists without opening
    every document. ``catalog_info`` adds technologies, databases, integrations, profiles.
    """
    index: dict[str, Any] = {
        "schema_version": INDEX_SCHEMA,
        "estimation": ESTIMATION_NOTE,
        "usage": "Select the minimum context: run 'ai-project context --task \"...\" --json' "
        "(see .ai/agents/00-master.md). Derived file: do not edit. Paths are relative to the "
        "project root.",
        "core": {p: {"tokens": estimate_tokens(files[p])} for p in CORE_FILES if p in files},
    }
    for kind in KINDS:
        entries: dict[str, Any] = {}
        for item_id, spec in meta.get(kind, {}).items():
            path = knowledge_path(kind, item_id)
            if path not in files:
                continue
            entries[item_id] = _index_entry(kind, path, files[path], spec)
        index[kind] = entries
    index["not_installed_agents"] = [a for a in meta.get("agents", {}) if a not in index["agents"]]
    index["tools"] = {
        t: {"name": s.get("name", t), "stacks": s.get("stacks", [])}
        for t, s in meta.get("tools", {}).items()
    }
    for key, catalog_entries in (catalog_info or {}).items():
        index[key] = {k: dict(v) for k, v in catalog_entries.items()}
    return _compact_json(index)


def _index_entry(kind: str, path: str, text: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": path, "tokens": estimate_tokens(text)}
    if kind == "agents":
        for key in ("layer", "priority", "summary", "requires", "recommended", "domains"):
            entry[key] = spec.get(key)
        entry["triggers"] = sorted(spec.get("triggers", {}))
    elif kind == "rules":
        meta_sections = spec.get("sections", {})
        entry["agents"] = spec.get("agents", [])
        entry["sections"] = [
            {
                **section.to_dict(),
                **(
                    {"always": True} if meta_sections.get(section.heading, {}).get("always") else {}
                ),
            }
            for section in split_sections(text)
        ]
    elif kind == "stacks":
        entry["domains"] = spec.get("domains", [])
        entry["triggers"] = sorted(spec.get("triggers", {}))
    else:
        entry["triggers"] = sorted(spec.get("triggers", {}))
    return entry


def _compact_json(index: Mapping[str, Any]) -> str:
    """Deterministic JSON with one entry per line: small and diff-friendly."""

    def dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    lines = ["{"]
    keys = list(index)
    for i, key in enumerate(keys):
        value = index[key]
        comma = "," if i < len(keys) - 1 else ""
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            lines.append(f"  {json.dumps(key)}: {{")
            items = list(value.items())
            for j, (item_id, entry) in enumerate(items):
                inner = "," if j < len(items) - 1 else ""
                lines.append(f"    {json.dumps(item_id)}: {dumps(entry)}{inner}")
            lines.append(f"  }}{comma}")
        else:
            lines.append(f"  {json.dumps(key)}: {dumps(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def read_index(text: str) -> dict[str, Any] | None:
    """Parse an index; None when absent, corrupt or from an unknown schema (never fatal)."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("schema_version") != INDEX_SCHEMA:
        return None
    return data
