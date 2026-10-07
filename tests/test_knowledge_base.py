"""Integrity of the kit content: profiles, agents, rules, workflows, stacks, templates."""

from __future__ import annotations

import re

import pytest

from ai_project.catalog import Catalog, Selection
from ai_project.generator import build_plan
from ai_project.paths import kit_root

ROOT = kit_root()
AGENT_SECTIONS = [
    "## Role",
    "## Objective",
    "## Responsibilities",
    "## Rules",
    "## Inputs",
    "## Outputs",
    "## Validation",
    "## Forbidden behavior",
    "## Collaboration with other agents",
]
EXPECTED_AGENTS = [
    "00-master",
    "01-frontend",
    "02-backend",
    "03-database",
    "04-architecture",
    "05-quality",
    "06-solid-patterns",
    "07-oop",
    "08-performance",
    "09-security",
    "10-testing",
    "11-documentation",
    "12-devops",
    "13-observability",
    "14-code-review",
    "15-context-token-optimizer",  # added in 1.1.0
]
# Knowledge files are copied verbatim (they may legitimately contain `{{ }}`, e.g. Angular).
VERBATIM_PREFIXES = (".ai/agents/", ".ai/rules/", ".ai/workflows/", ".ai/stacks/")
KIT_REF = re.compile(r"`((?:agents|rules|workflows)/[\w.-]+\.md|stacks/[\w-]+/README\.md)`")


def _h2_outside_code(text: str) -> list[str]:
    headings, in_code = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("## "):
            headings.append(line.strip())
    return headings


def test_all_expected_agents_exist(catalog: Catalog) -> None:
    assert catalog.available_agents() == EXPECTED_AGENTS


@pytest.mark.parametrize("agent", EXPECTED_AGENTS)
def test_agent_has_required_sections_in_order(agent: str) -> None:
    headings = _h2_outside_code((ROOT / "agents" / f"{agent}.md").read_text("utf-8"))
    positions = [headings.index(section) for section in AGENT_SECTIONS]
    assert positions == sorted(positions), f"{agent}: sections out of order"


@pytest.mark.parametrize(
    "rel",
    sorted(
        p.relative_to(ROOT).as_posix()
        for d in ("agents", "rules", "workflows", "stacks")
        for p in (ROOT / d).rglob("*.md")
    ),
)
def test_knowledge_cross_references_resolve(rel: str) -> None:
    text = (ROOT / rel).read_text("utf-8")
    broken = [ref for ref in KIT_REF.findall(text) if "<" not in ref and not (ROOT / ref).is_file()]
    assert not broken, f"{rel} references missing kit files: {broken}"
    assert "../" not in text, f"{rel} must use AI-root-relative paths"


def test_rules_and_workflows_present(catalog: Catalog) -> None:
    for profile in catalog.profiles.values():
        for rule in profile.rules:
            assert (ROOT / "rules" / f"{rule}.md").is_file(), rule
        for workflow in profile.workflows:
            assert (ROOT / "workflows" / f"{workflow}.md").is_file(), workflow


def test_catalog_stacks_exist(catalog: Catalog) -> None:
    available = set(catalog.available_stacks())
    for group in (catalog.technologies, catalog.databases, catalog.deployments):
        for option in group.values():
            assert set(option.stacks) <= available, option


def test_profiles_reference_known_technologies(catalog: Catalog) -> None:
    assert list(catalog.profiles)[:7] == [
        "backend-api",
        "frontend",
        "fullstack",
        "python-automation",
        "data-engineering",
        "microservice",
        "custom",
    ]
    for profile in catalog.profiles.values():
        assert set(profile.technologies) <= set(catalog.technologies), profile.name
        assert (ROOT / "templates" / profile.template).is_dir(), profile.name


def _all_selections(catalog: Catalog):
    for profile in catalog.profiles.values():
        for technology in profile.technologies:
            for database in ("postgresql", "none"):
                yield Selection(
                    profile.name, technology, database, "kubernetes", tuple(catalog.assistants)
                )


def test_every_profile_and_technology_renders(catalog: Catalog) -> None:
    """No template may use an unknown variable or produce an unsafe path, in any combination."""
    count = 0
    for selection in _all_selections(catalog):
        resolved = catalog.resolve(selection)
        plan = build_plan(catalog, resolved, selection, {"project_name": "x-app"})
        paths = [p.path for p in plan]
        assert "AGENTS.md" in paths and ".ai/context/project.md" in paths
        assert len(paths) == len(set(paths))
        assert all(".." not in p.split("/") and not p.startswith("/") for p in paths)
        rendered = [p for p in plan if not p.path.startswith(VERBATIM_PREFIXES)]
        assert not any("{{" in p.content for p in rendered), selection
        agents_md = next(p.content for p in plan if p.path == "AGENTS.md")
        for ref in re.findall(r"`(\.ai/[\w./-]+\.md)`", agents_md):
            assert ref in paths, f"AGENTS.md links to {ref} which is not generated"
        assert ("03-database" in resolved.agents) == (
            selection.database != "none" or "03-database" in resolved.profile.agents
        )
        count += 1
    assert count > 30
