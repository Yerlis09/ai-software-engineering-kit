"""Plugin structure, metadata and the thin-adapter / core-separation rules."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
NAME = "netsf-ai-software-engineering"
EXPECTED_AGENTS = {
    "architect",
    "backend",
    "frontend",
    "api",
    "database",
    "security",
    "testing",
    "performance",
    "devops",
    "documentation",
    "refactoring",
    "debugging",
    "context-optimizer",
}


def frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text("utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields = dict(line.split(":", 1) for line in match[1].splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in fields.items()}, match[2]


def test_manifest_and_marketplace_are_consistent() -> None:
    plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text("utf-8"))
    market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text("utf-8"))
    assert plugin["name"] == NAME and plugin["displayName"] == "NETSF AI Software Engineering"
    assert re.fullmatch(r"[a-z0-9][a-z0-9._-]*", plugin["name"])
    assert market["name"] == "netsf"
    entry = next(p for p in market["plugins"] if p["name"] == NAME)
    assert entry["source"] == f"./plugins/{NAME}" and entry["version"] == plugin["version"]
    assert plugin["metadata"]["coreCompatibility"] == ">=1.2.0,<1.3.0"


def test_compatibility_constant_matches_manifest() -> None:
    from netsf import CORE_RANGE, PLUGIN_VERSION

    plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text("utf-8"))
    assert plugin["version"] == PLUGIN_VERSION
    assert plugin["metadata"]["coreCompatibility"] == CORE_RANGE


def test_skills() -> None:
    skills = {p.parent.name: frontmatter(p) for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    assert set(skills) == {"netsf-ai-engineer", "plan", "context", "setup"}
    for name, (fields, _body) in skills.items():
        assert fields["name"] == name
        assert 20 <= len(fields["description"]) <= 300, name  # descriptions cost context
    assert "disable-model-invocation" not in skills["netsf-ai-engineer"][0]  # auto-invoked
    for name in ("plan", "context", "setup"):  # user-invoked only: no automatic loading
        assert skills[name][0]["disable-model-invocation"] == "true"


def test_master_skill_contains_mandatory_controls() -> None:
    _fields, body = frontmatter(PLUGIN / "skills/netsf-ai-engineer/SKILL.md")
    for required in (
        "UNTRUSTED PROJECT DATA",
        "Maximum 5 repair cycles",
        "explicit approval",
        "NOT VERIFIED",
        "risk --task",
        "context --task",
        "--lean",
        "REQ-",
        "DIRECT",
        "BLOCKED",
        "Never commit",
    ):
        assert required in body, required


@pytest.mark.parametrize("name", sorted(EXPECTED_AGENTS))
def test_agents_are_thin_adapters_over_the_core(name: str) -> None:
    from ai_project.paths import kit_root

    fields, body = frontmatter(PLUGIN / "agents" / f"{name}.md")
    assert fields["name"] == name and fields["description"] and fields["tools"]
    focus = re.search(r"--focus ([\w-]+)", body)[1]
    assert (kit_root() / "agents" / f"{focus}.md").is_file()  # role comes from the core
    assert len(body) < 2000  # thin: no copied knowledge
    kit_text = (kit_root() / "agents" / f"{focus}.md").read_text("utf-8")
    long_kit_lines = [line for line in kit_text.splitlines() if len(line) > 80]
    assert not any(line in body for line in long_kit_lines)


def test_all_agents_present_and_optimizer_is_restricted() -> None:
    assert {p.stem for p in (PLUGIN / "agents").glob("*.md")} == EXPECTED_AGENTS
    fields, _ = frontmatter(PLUGIN / "agents/context-optimizer.md")
    assert "only for tasks about context" in fields["description"]
    assert "Edit" not in fields["tools"] and "Write" not in fields["tools"]


def test_hooks_are_minimal_security_guardrails() -> None:
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text("utf-8"))["hooks"]
    assert set(hooks) == {"PreToolUse"}
    (entry,) = hooks["PreToolUse"]
    for tool in ("Bash", "PowerShell", "Read", "Edit", "Write"):
        assert tool in entry["matcher"].split("|")
    (command,) = entry["hooks"]
    assert '"${CLAUDE_PLUGIN_ROOT}/scripts/netsf_guard.py"' in command["command"]


def test_no_mcp_no_bin_no_network_code() -> None:
    assert not (PLUGIN / ".mcp.json").exists() and not (PLUGIN / "bin").exists()
    sources = "\n".join(p.read_text("utf-8") for p in (PLUGIN / "scripts").rglob("*.py"))
    for forbidden in (
        "urllib.request",
        "http.client",
        "socket.",
        "requests.",
        "shell=True",
        "os.system(",
        "eval(",
        "exec(",
    ):
        assert forbidden not in sources, forbidden


def test_no_reference_outside_the_plugin_root() -> None:
    for path in PLUGIN.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".json", ".py"):
            assert (
                "../" not in path.read_text("utf-8").replace("../../", "") or path.suffix == ".py"
            )


PROMPT_KEYS = {
    "schema_version",
    "name",
    "description",
    "tags",
    "plugins",
    "runs",
    "expected_outcome",
    "model",
    "max_turns",
    "timeout_seconds",
    "allowed_tools",
    "append_system_prompt",
    "env",
}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}


@pytest.mark.parametrize("case", sorted(p.name for p in (PLUGIN / "evals").iterdir() if p.is_dir()))
def test_eval_cases_use_documented_format(case: str) -> None:
    directory = PLUGIN / "evals" / case
    fields, prompt = frontmatter(directory / "prompt.md")
    assert set(fields) <= PROMPT_KEYS and prompt.strip()
    graders = list((directory / "graders").glob("*.md"))
    assert graders, "a case without graders fails to load"
    for grader in graders:
        assert frontmatter(grader)[0]["type"] in GRADER_TYPES, grader.name
    if (directory / "case.yaml").exists():
        assert (directory / "fixture.sh").is_file()


def test_eight_eval_cases_prepared() -> None:
    assert len([p for p in (PLUGIN / "evals").iterdir() if p.is_dir()]) == 8
