"""Deterministic safety guardrail for the PreToolUse hook.

Prompts do the reasoning; this hook enforces a few non-negotiable rules regardless of what the
model decides. It returns, per the Claude Code hook protocol, one of:

* ``deny`` - never allowed (secret exfiltration), or forbidden by an execution restriction the
  user requested (dry run, "do not modify"; see ``readonly.py``);
* ``ask``  - the human must confirm (destructive / irreversible / production / secrets);
* nothing  - normal permission flow continues.

Fail-safe: any internal error or unreadable input yields ``ask``, never a crash (a crashing
hook would let the tool run through the normal flow without this check).
"""

from __future__ import annotations

import json
import re
from typing import Any

from netsf.readonly import restriction

ASK, DENY = "ask", "deny"
SHELL_TOOLS = {"Bash", "PowerShell"}
FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
_SENSITIVE_FILE = (
    r"(\.env(?!\.(example|sample|template)\b)(\.[\w-]+)?\b|id_rsa|id_ed25519|"
    r"\.pem\b|\.p12\b|\.pfx\b|\.key\b|credentials(\.json)?\b|\.netrc\b|kubeconfig)"
)

_COMMAND_RULES: list[tuple[str, str, str]] = [
    # Exfiltration of secrets: denied.
    (
        DENY,
        rf"(curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|scp|rsync|ftp|nc|netcat)\b"
        rf"[^\n]*{_SENSITIVE_FILE}",
        "uploading a secret file is never allowed",
    ),
    (
        DENY,
        rf"{_SENSITIVE_FILE}[^\n]*\|\s*(curl|wget|nc|netcat|invoke-webrequest|iwr)\b",
        "piping a secret file to a network tool is never allowed",
    ),
    # Destructive Git.
    (
        ASK,
        r"\bgit\s+push\b[^\n]*(\s--force\b|\s-f\b|\s--force-with-lease\b|\s\+\S)",
        "force push rewrites remote history",
    ),
    (ASK, r"\bgit\s+reset\b[^\n]*--hard\b", "git reset --hard discards local work"),
    (ASK, r"\bgit\s+clean\b[^\n]*\s-\w*[fdx]", "git clean deletes untracked files"),
    (ASK, r"\bgit\s+(checkout|restore)\b[^\n]*\s(--\s+)?\.(\s|$)", "discards uncommitted changes"),
    (ASK, r"\bgit\s+branch\b[^\n]*\s-D\b", "force-deletes a branch"),
    (ASK, r"\bgit\s+remote\s+(add|set-url|remove|rm|rename)\b", "modifies a Git remote"),
    (
        ASK,
        r"\bgit\s+config\b[^\n]*(--global|--system|user\.name|user\.email)",
        "modifies Git identity or global configuration",
    ),
    (
        ASK,
        r"\bgit\s+(filter-branch|filter-repo)\b|\bgit\s+push\b[^\n]*--delete\b",
        "rewrites or deletes Git history",
    ),
    # Destructive file operations.
    (
        ASK,
        r"\brm\s+(-\w*\s+)*-\w*r\w*\b|\brm\s+(-\w*\s+)*-\w*f\w*r\w*\b|\brm\s+-[a-z]*r",
        "recursive delete",
    ),
    (
        ASK,
        r"remove-item\b[^\n]*-recurse|\b(rmdir|rd)\s+/s\b|\bdel\s+/[sq]\b|\bdel\s+/s",
        "recursive delete",
    ),
    (ASK, r"\b(mkfs|format\s+[a-z]:|diskpart|dd\s+if=)", "disk-level destructive operation"),
    # Databases.
    (
        ASK,
        r"\b(drop\s+(database|schema|table|view)|truncate\s+(table\s+)?\w)",
        "destructive database command",
    ),
    (ASK, r"\bdelete\s+from\s+[\w.\"`]+\s*(;|$|\")", "DELETE without a WHERE clause"),
    # Infrastructure / production.
    (ASK, r"\bkubectl\b[^\n]*\b(delete|drain|cordon)\b", "deletes or drains Kubernetes resources"),
    (
        ASK,
        r"\b(kubectl|helm|terraform|ansible-playbook|az|aws|gcloud)\b[^\n]*"
        r"(\bprod\b|production|--context[ =]\S*prod)",
        "targets production",
    ),
    (
        ASK,
        r"\bhelm\s+(uninstall|delete|rollback)\b|\bterraform\s+(apply|destroy)\b",
        "changes or destroys infrastructure",
    ),
    (ASK, r"\bdocker\s+(system\s+prune|volume\s+(rm|prune))\b", "deletes container data"),
    # Permissions.
    (
        ASK,
        r"\bchmod\b[^\n]*\b777\b|\bicacls\b[^\n]*/grant\b|\bchown\s+-R\b",
        "changes file permissions",
    ),
    (
        ASK,
        r"\b(aws\s+iam|gcloud\s+(projects\s+)?add-iam|az\s+role\s+assignment|"
        r"kubectl\s+(create|apply)[^\n]*(rolebinding|clusterrole))",
        "changes access permissions",
    ),
    # Git history and remotes: commits, pushes, tags and new repositories need authorisation.
    (ASK, r"\bgit\s+init\b", "initialises a Git repository (check it is not a parent's)"),
    (ASK, r"\bgit\s+commit\b", "creates a commit (requires the user's authorisation)"),
    (ASK, r"\bgit\s+push\b", "pushes to a remote (requires the user's authorisation)"),
    (ASK, r"\bgit\s+tag\s+(?!-l\b|--list\b)[\w.-]", "creates a tag (requires authorisation)"),
    # Secrets access through the shell.
    (
        ASK,
        rf"\b(cat|type|get-content|gc|more|less|head|tail|printenv|env)\b[^\n]*{_SENSITIVE_FILE}",
        "reads a secret file",
    ),
]
_COMPILED = [(d, re.compile(rx, re.IGNORECASE), why) for d, rx, why in _COMMAND_RULES]
_SENSITIVE_FILE_RX = re.compile(_SENSITIVE_FILE + r"$", re.IGNORECASE)


def evaluate(event: dict[str, Any]) -> tuple[str, str] | None:
    """Return (decision, reason) or None when this guard has no objection."""
    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return ASK, "NETSF guard could not read the tool request; please confirm"
    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return ASK, "NETSF guard could not read the command; please confirm"
        verdicts = [(d, why) for d, rx, why in _COMPILED if rx.search(command)]
        if any(d == DENY for d, _ in verdicts):
            return DENY, next(why for d, why in verdicts if d == DENY)
        if verdicts:
            return ASK, verdicts[0][1]
        return None
    if tool in FILE_TOOLS:
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        if name and _SENSITIVE_FILE_RX.search(name):
            return ASK, f"access to a secret file ({name})"
    return None


def hook_output(raw: str) -> str:
    """Full hook behaviour: stdin text -> stdout JSON ('' = no decision). Never raises."""
    try:
        event = json.loads(raw) if raw.strip() else None
        if isinstance(event, dict):
            verdict = restriction(event) or evaluate(event)
        else:
            verdict = (ASK, "NETSF guard received no readable input; please confirm")
    except Exception:  # fail-safe: never let a guard error silently allow
        verdict = (ASK, "NETSF guard error; please confirm this action")
    if verdict is None:
        return ""
    decision, reason = verdict
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": f"NETSF safety guard: {reason}.",
            }
        }
    )
