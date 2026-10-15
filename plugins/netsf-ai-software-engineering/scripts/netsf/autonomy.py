"""Deterministic workflow decision: continue autonomously, ask once, or stay read-only.

The engineering workflow (understand → plan → implement → test → repair → document → validate →
report) runs without further user prompts unless one of these holds:

* ``BLOCKED``       — the request is unsafe; nothing is done.
* ``READ_ONLY``     — the user asked for a dry run / analysis only; plan and report, change nothing.
* ``ASK_APPROVAL``  — HIGH or CRITICAL risk; one consolidated approval, then the workflow continues.
* ``ASK_QUESTIONS`` — a decision only the user can make blocks the work (for example the database
  when persistence is needed); all such questions are asked together, once.
* ``PROCEED``       — LOW/MEDIUM risk and nothing blocking: implement, test, repair, document and
  report in one go.

Informational findings (an unrelated parent Git repository, an existing route that may already
cover the task) never stop the workflow; they are carried as notes.
"""

from __future__ import annotations

from typing import Any

from netsf.readonly import MODIFY, apply_prompt
from netsf.risk import Risk
from netsf.scope import Scope
from netsf.understand import Understanding

PROCEED, ASK_APPROVAL, ASK_QUESTIONS, READ_ONLY, BLOCKED = (
    "PROCEED",
    "ASK_APPROVAL",
    "ASK_QUESTIONS",
    "READ_ONLY",
    "BLOCKED",
)
MAX_REPAIR_CYCLES = 5
INLINE_TIERS = ("simple", "normal")
REPORT_SECTIONS = (
    "Summary (plain language)",
    "Changes (files and why)",
    "Traceability: REQ-xxx | implementation | test | PASS / FAIL / NOT VERIFIED",
    "VERIFIED (executed or observed: commands and real results)",
    "INFERRED (from static analysis or project structure)",
    "NOT VERIFIED (not executed or not possible here)",
    "Approvals requested, repair cycles used, remaining risks",
)


def decide(
    task: str,
    risk: Risk,
    scope: Scope | None,
    understanding: Understanding | None,
    package: dict[str, Any] | None,
    specialists: list[str],
    project_mode: str,
    git: dict[str, Any],
) -> dict[str, Any]:
    """Return the workflow decision, execution plan and report contract for one task."""
    prohibitions, trigger, _ = apply_prompt(task, frozenset())
    questions = list(scope.questions) if scope else []
    notes: list[str] = []
    git_task = any("Git history" in r for r in risk.reasons)
    if not git.get("own_repository") and git_task:
        notes.append("The project has no Git repository of its own; 'git init' needs approval.")
    elif git.get("parent_repository"):
        notes.append("A parent directory's Git repository exists; it is not used for this task.")
    if understanding and understanding.possible_existing_implementation:
        routes = ", ".join(
            f"{r['route']} ({r['file']}:{r['line']})" for r in understanding.existing_routes[:3]
        )
        notes.append(
            f"Possible existing implementation: {routes}. Verify it first; extend or fix "
            "it instead of duplicating."
        )

    if risk.blocked:
        action, reasons = BLOCKED, list(risk.reasons)
    elif MODIFY in prohibitions:
        action, reasons = READ_ONLY, [f"the user asked for analysis only ('{trigger[:40]}')"]
    elif risk.approval_required:
        action = ASK_APPROVAL
        reasons = [f"{risk.level} risk: " + "; ".join(risk.reasons)]
    elif questions:
        action, reasons = ASK_QUESTIONS, ["a decision only the user can make blocks the work"]
    else:
        action = PROCEED
        reasons = [f"{risk.level} risk, no blocking question: continue without further prompts"]

    tier = str(((package or {}).get("budget") or {}).get("tier") or "")
    # Simple and normal tasks on an existing project run inline: the specialists' guidance is
    # already in the context package, so spawning sub-agents would only add turns and context.
    inline = tier in INLINE_TIERS and project_mode != "new"
    return {
        "action": action,
        "reasons": reasons,
        "questions": questions if action in (ASK_APPROVAL, ASK_QUESTIONS) else [],
        "restrictions": sorted(prohibitions),
        "notes": notes,
        "execution": {
            "mode": "inline" if inline else "delegate",
            "specialists": specialists,
            "why": (
                f"budget tier {tier or 'unknown'}, {len(specialists)} specialist(s), "
                f"{project_mode} project"
            ),
        },
        "phases": _phases(action, understanding),
        "repair_policy": {
            "max_cycles": MAX_REPAIR_CYCLES,
            "repair_when": "the failure comes from this change, the fix stays in scope, the risk "
            "stays LOW/MEDIUM and the result can be re-validated",
            "stop_when": "the limit is reached, the failure pre-exists or is outside the task, or "
            "the fix needs a HIGH/CRITICAL action: report what failed, what was tried and what "
            "is needed",
        },
        "report_sections": list(REPORT_SECTIONS),
    }


def _phases(action: str, understanding: Understanding | None) -> list[str]:
    tests = ", ".join(understanding.test_commands) if understanding else ""
    lint = ", ".join(understanding.lint_commands) if understanding else ""
    docs = ", ".join(understanding.documentation_targets) if understanding else ""
    if action in (BLOCKED,):
        return ["explain why the request is refused"]
    if action == READ_ONLY:
        return [
            "inspect the relevant files",
            "write requirements and the plan",
            "report (no file, dependency, Git or deployment change)",
        ]
    steps = [
        "requirements: REQ-xxx acceptance criteria from the request",
        "inspect the relevant files; reuse what already exists",
        "implement the minimal change, following the project's conventions",
        "add or update tests for every acceptance criterion",
        f"run tests ({tests or 'detect the project test command'})"
        + (f" and checks ({lint})" if lint else ""),
        f"repair failures caused by this change (max {MAX_REPAIR_CYCLES} cycles)",
        "documentation: English docstrings/comments where behaviour is not obvious; update "
        + (docs or "the docs that describe changed behaviour"),
        "final validation against every REQ, then the report",
    ]
    if action in (ASK_APPROVAL, ASK_QUESTIONS):
        steps.insert(
            0,
            "ask once (approval and questions together), then continue with every "
            "step below without new prompts",
        )
    return steps


def metrics(
    decision: dict[str, Any],
    package_metrics: dict[str, Any],
    files_read: int,
    understanding: Understanding | None,
) -> dict[str, Any]:
    """Autonomy metrics for benchmarks: interaction needed and context used."""
    action = decision["action"]
    stops = 1 if action in (ASK_APPROVAL, ASK_QUESTIONS) else 0
    return {
        "user_prompts_required": 1 + stops,
        "approval_requests": 1 if action == ASK_APPROVAL else 0,
        "questions": len(decision["questions"]),
        "specialists": len(decision["execution"]["specialists"]),
        "context_tokens": package_metrics.get("emitted_estimated_tokens"),
        "files_inspected": files_read + (understanding.files_scanned if understanding else 0),
        "relevant_files": len(understanding.relevant_files) if understanding else 0,
        "test_commands": len(understanding.test_commands) if understanding else 0,
    }
