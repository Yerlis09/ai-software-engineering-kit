"""Deterministic execution restrictions requested by the user (dry run, "do not modify"...).

Technical autonomy decides *how* to build; execution authority decides *whether* the project
may be changed now. This module turns the user's own words into per-session prohibitions and
enforces them on every tool call, independently of what the model decides:

* ``UserPromptSubmit``: the submitted prompt (typed by the user, so trusted input — unlike
  repository content) is matched against activation and release phrases. Prohibitions are
  stored per session and stay active until the user releases them explicitly
  ("exit dry-run", "you can modify now", "aplica el plan"...).
* ``PreToolUse``: a prohibited action is denied. In full read-only mode, file-editing tools are
  denied and shell commands run only when every segment is on a read-only allowlist; anything
  unknown is denied (fail-closed). Claude Code's plan permission mode counts as full read-only.

State lives in ``$CLAUDE_PLUGIN_DATA/readonly/<session>.json`` (a temporary directory when the
variable is absent). Phrase matching is a heuristic: a false activation fails safe (changes are
denied with instructions to release the mode).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

MODIFY, INSTALL, GIT_INIT, COMMIT, PUSH, DEPLOY = (
    "modify",
    "install",
    "git-init",
    "commit",
    "push",
    "deploy",
)
ALL = frozenset({MODIFY, INSTALL, GIT_INIT, COMMIT, PUSH, DEPLOY})
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
STATE_MAX_AGE_S = 7 * 24 * 3600
PLAN_SKILL = re.compile(r"^\s*/netsf-ai-software-engineering:plan\b", re.I)

_NOT = r"(?<!\bnot )(?<!n't )(?<!\bno )(?<!\bnever )"
ACTIVATIONS: list[tuple[re.Pattern[str], frozenset[str]]] = [
    (
        re.compile(
            r"(?<![-\w])dry[- ]?run\b(?!\s*(option|flag|param\w*|argument|switch|feature|support"
            r"|command|implementation|parameter|mode for))"
            r"|\banaly[sz](is|e)\s+only\b|\bonly\s+analy[sz]e\b|\bread[- ]only\b"
            r"|\bplan\s+only\b|\bjust\s+(a\s+)?plan\b"
            r"|\b(do not|don't|dont|never)\s+(modify|change|edit|touch|write)\s+"
            r"(anything|any files?|files|the (code|project|repo\w*|files?))\b"
            r"|\bwithout\s+(modifying|changing|touching|editing)\b"
            r"|\bno\s+(modifiques|cambies|toques|edites|escribas)\b|\bsin\s+(modificar|cambiar|tocar)\b"
            r"|\bs[oó]lo\s+(an[aá]lisis|analiza\w*|lectura|planifica\w*|el plan)\b"
            r"|\bmodo\s+(dry[- ]?run|lectura|solo lectura|an[aá]lisis)\b",
            re.I,
        ),
        ALL,
    ),
    (
        re.compile(
            r"\b(do not|don't|never)\s+create\s+(any\s+)?files?\b"
            r"|\bno\s+(crees|generes)\s+(ning[uú]n\s+)?(archivos?|ficheros?)\b",
            re.I,
        ),
        frozenset({MODIFY}),
    ),
    (
        re.compile(
            r"\b(do not|don't|never)\s+install\b|\bno\s+instales\b|\bsin\s+instalar\b", re.I
        ),
        frozenset({INSTALL}),
    ),
    (
        re.compile(r"\b(do not|don't|never)\s+(initiali[sz]e|init)\b|\bno\s+inicialices\b", re.I),
        frozenset({GIT_INIT}),
    ),
    (
        re.compile(
            r"\b(do not|don't|never)\s+commit\b|\bno\s+hagas\s+(ning[uú]n\s+)?commits?\b"
            r"|\bsin\s+commits?\b",
            re.I,
        ),
        frozenset({COMMIT}),
    ),
    (
        re.compile(r"\b(do not|don't|never)\s+push\b|\bno\s+hagas\s+push\b|\bsin\s+push\b", re.I),
        frozenset({PUSH}),
    ),
    (
        re.compile(
            r"\b(do not|don't|never)\s+deploy\b|\bno\s+despliegues\b|\bsin\s+desplegar\b", re.I
        ),
        frozenset({DEPLOY}),
    ),
]
RELEASE = re.compile(
    _NOT + r"\b(exit|end|leave|stop|disable)\s+(the\s+)?(dry[- ]?run|read[- ]only|analysis)"
    r"(\s+mode)?\b"
    r"|" + _NOT + r"\byou\s+(can|may)\s+(now\s+)?(modify|change|edit|implement|apply)\b"
    r"|" + _NOT + r"\b(go ahead and implement|apply the plan|proceed with (the )?implementation"
    r"|implement it now)\b"
    r"|" + _NOT + r"\bsal(ir|ga)?\s+del\s+modo\s+(dry[- ]?run|lectura|solo lectura|an[aá]lisis)\b"
    r"|" + _NOT + r"\bya\s+puedes\s+(modificar|implementar|cambiar|aplicar)\b"
    r"|" + _NOT + r"\b(aplica|implementa|ejecuta)\s+el\s+plan\b"
    r"|" + _NOT + r"\bprocede\s+con\s+la\s+implementaci[oó]n\b",
    re.I,
)

# Read-only shell allowlist -------------------------------------------------------------------
SAFE_COMMANDS = {
    "ls",
    "dir",
    "pwd",
    "cat",
    "type",
    "head",
    "tail",
    "less",
    "more",
    "wc",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "find",
    "tree",
    "stat",
    "file",
    "which",
    "where",
    "whoami",
    "echo",
    "date",
    "sort",
    "uniq",
    "cut",
    "du",
    "df",
    "get-childitem",
    "gci",
    "get-content",
    "gc",
    "select-string",
    "sls",
    "get-item",
    "gi",
    "test-path",
    "resolve-path",
    "get-location",
    "measure-object",
    "select-object",
    "where-object",
    "format-table",
    "format-list",
    "out-string",
    "sort-object",
}
SAFE_GIT = {
    "status",
    "log",
    "diff",
    "show",
    "rev-parse",
    "ls-files",
    "blame",
    "grep",
    "describe",
    "shortlog",
}
FIND_WRITING_ACTIONS = {
    "-delete",
    "-exec",
    "-execdir",
    "-ok",
    "-okdir",
    "-fprint",
    "-fprint0",
    "-fprintf",
    "-fls",
}
BRIDGE_READ = {"check", "detect", "risk", "plan", "context"}
CORE_READ = {"context", "doctor", "version", "list", "help"}
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
_HARMLESS_REDIRECT = re.compile(r"\d?>\s*(&1|/dev/null|\$null)", re.I)
_SUBSHELL = re.compile(r"\$\(|`|<\(")
_INSTALL = re.compile(
    r"\b(pip3?|uv|poetry|pipenv|conda|npm|pnpm|yarn|apt(-get)?|brew|choco"
    r"|winget|gem|cargo|go)\s+(install|add|i|get)\b|\buv\s+pip\s+install\b"
    r"|\binstall-(module|package)\b",
    re.I,
)
_GIT_INIT = re.compile(r"\bgit\s+init\b|\bai-project\s+init\b", re.I)
_COMMIT = re.compile(r"\bgit\s+commit\b", re.I)
_PUSH = re.compile(r"\bgit\s+push\b", re.I)
_DEPLOY = re.compile(
    r"\bkubectl\s+(apply|create|replace|set|rollout|scale|patch|delete)\b"
    r"|\bhelm\s+(install|upgrade|rollback|uninstall)\b|\bterraform\s+(apply|destroy)\b"
    r"|\bdocker\s+push\b|\bdocker\s+compose\s+up\b",
    re.I,
)


def state_dir() -> Path:
    """Directory holding the per-session state."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        tempfile.gettempdir(), "netsf-ai-se"
    )
    return Path(base) / "readonly"


def _state_file(session_id: Any) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(session_id or "default"))[:80] or "default"
    return state_dir() / f"{safe}.json"


def load_state(session_id: Any) -> tuple[frozenset[str], str]:
    """Return (prohibitions, trigger). Raises ValueError when the state file is unreadable."""
    path = _state_file(session_id)
    if not path.is_file():
        return frozenset(), ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        prohibitions = frozenset(p for p in data.get("prohibitions", []) if p in ALL)
        return prohibitions, str(data.get("trigger", ""))[:120]
    except (OSError, ValueError, AttributeError) as exc:
        raise ValueError(f"unreadable read-only state: {exc}") from exc


def save_state(session_id: Any, prohibitions: frozenset[str], trigger: str) -> None:
    """Persist the session prohibitions (an empty set removes the state)."""
    path = _state_file(session_id)
    if not prohibitions:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "prohibitions": sorted(prohibitions),
        "trigger": trigger[:120],
        "updated": int(time.time()),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    _prune(path.parent)


def _prune(directory: Path) -> None:
    now = time.time()
    for old in directory.glob("*.json"):
        try:
            if now - old.stat().st_mtime > STATE_MAX_AGE_S:
                old.unlink()
        except OSError:
            continue


def apply_prompt(prompt: str, current: frozenset[str]) -> tuple[frozenset[str], str, bool]:
    """Apply one user prompt: returns (prohibitions, trigger phrase, released)."""
    released = bool(RELEASE.search(prompt))
    prohibitions = frozenset() if released else frozenset(current)
    trigger = ""
    if PLAN_SKILL.search(prompt):
        prohibitions |= ALL
        trigger = "/netsf-ai-software-engineering:plan"
    # A release phrase ("exit dry-run") must not count as a new activation.
    remaining = RELEASE.sub(" ", prompt)
    for pattern, adds in ACTIVATIONS:
        match = pattern.search(remaining)
        if match:
            prohibitions |= adds
            trigger = trigger or match.group(0)
    return prohibitions, trigger, released


def prompt_hook(event: dict[str, Any]) -> str:
    """UserPromptSubmit: update the session state; returns additional-context JSON or ''."""
    prompt = event.get("prompt")
    if not isinstance(prompt, str):
        return ""
    session = event.get("session_id")
    try:
        current, old_trigger = load_state(session)
    except ValueError:
        current, old_trigger = ALL, "unreadable state"
    prohibitions, trigger, released = apply_prompt(prompt, current)
    if prohibitions == current and not released and not trigger:
        return ""
    save_state(session, prohibitions, trigger or old_trigger)
    if prohibitions:
        text = (
            f"NETSF execution restriction ON ({', '.join(sorted(prohibitions))}), requested by "
            f"the user ('{(trigger or old_trigger)[:60]}'). Inspect, analyse and plan only for "
            "the restricted actions; they will be denied. The user can lift it by saying "
            "'exit dry-run' (or 'ya puedes modificar')."
        )
    else:
        text = "NETSF execution restriction OFF: the user authorised changes again."
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}
    )


def restriction(event: dict[str, Any]) -> tuple[str, str] | None:
    """PreToolUse: return ("deny" | "ask", reason) when a restriction forbids the call."""
    tool = event.get("tool_name")
    try:
        prohibitions, trigger = load_state(event.get("session_id"))
    except ValueError:
        if tool in EDIT_TOOLS or tool in SHELL_TOOLS:
            return "ask", "read-only state could not be read; please confirm this change"
        return None
    if event.get("permission_mode") == "plan":
        prohibitions, trigger = ALL, "plan mode"
    if not prohibitions:
        return None
    if trigger == "plan mode":
        hint = " (Claude Code plan mode: leave plan mode to allow changes)"
    else:
        hint = f" (requested: '{trigger[:60]}'; say 'exit dry-run' to allow changes)"
    raw_input = event.get("tool_input")
    tool_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
    if tool in EDIT_TOOLS and MODIFY in prohibitions:
        return "deny", "read-only mode: files must not be created or edited" + hint
    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return "deny", "read-only mode: unreadable command" + hint
        for name, rx in (
            (INSTALL, _INSTALL),
            (GIT_INIT, _GIT_INIT),
            (COMMIT, _COMMIT),
            (PUSH, _PUSH),
            (DEPLOY, _DEPLOY),
        ):
            if name in prohibitions and rx.search(command):
                return "deny", f"the user asked not to {name.replace('-', ' ')}" + hint
        if MODIFY in prohibitions and not is_read_only_command(command):
            return "deny", (
                "read-only mode: only read-only commands are allowed "
                "(listing, reading, searching, git status/log/diff)" + hint
            )
    return None


def is_read_only_command(command: str) -> bool:
    """True when every segment of the command is on the read-only allowlist."""
    if _SUBSHELL.search(command) or ">" in _HARMLESS_REDIRECT.sub("", command):
        return False
    segments = [s.strip() for s in _SEGMENT_SPLIT.split(command) if s.strip()]
    return bool(segments) and all(_safe_segment(s) for s in segments)


def _safe_segment(segment: str) -> bool:
    tokens = segment.split()
    head = tokens[0].strip("\"'").lower()
    name = re.split(r"[\\/]", head)[-1].removesuffix(".exe")
    args = [t.strip("\"'") for t in tokens[1:]]
    if name in SAFE_COMMANDS:
        if name == "find":
            return not any(a.lower() in FIND_WRITING_ACTIONS for a in args)
        return True
    if name == "git" and args:
        sub, rest = args[0].lower(), [a.lower() for a in args[1:]]
        if sub in SAFE_GIT:
            return True
        if sub == "branch":
            return all(a in ("-a", "-r", "--list", "-v", "-vv", "--show-current") for a in rest)
        if sub in ("remote", "tag"):
            return all(a in ("-v", "--verbose", "-l", "--list", "show") for a in rest)
        if sub == "config":
            return bool(rest) and rest[0] in ("--get", "--get-all", "--list", "-l")
        if sub == "stash":
            return rest[:1] == ["list"]
        return False
    if name in ("python", "python3", "py"):
        script = next((a for a in args if a.endswith(".py")), "")
        if script.replace("\\", "/").endswith("netsf_bridge.py"):
            after = args[args.index(script) + 1 :] if script in args else []
            return bool(after) and after[0] in BRIDGE_READ
        return False
    if name == "ai-project" and args:
        if args[0] == "context":
            return "--rebuild-graph" not in args
        if args[0] == "update":
            return "--dry-run" in args or "--check" in args
        return args[0] in CORE_READ
    return False
