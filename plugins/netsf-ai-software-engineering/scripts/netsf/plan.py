"""Plan / dry run: what the system would do, without modifying anything.

Combines the core's routing (classification, selected agents), project detection, risk
assessment and a bounded impact analysis. Requirement details and the exact files to change
need reasoning, so the plan marks them for the engineer (the model) to complete.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from netsf.detect import SKIP_DIRS, Detection, kit_selection
from netsf.risk import Risk
from netsf.safety import read_text

# Kit agent id -> plugin specialist (thin adapter in agents/)
SPECIALISTS = {
    "01-frontend": "frontend",
    "02-backend": "backend",
    "03-database": "database",
    "04-architecture": "architect",
    "05-quality": "refactoring",
    "06-solid-patterns": "refactoring",
    "07-oop": "refactoring",
    "08-performance": "performance",
    "09-security": "security",
    "10-testing": "testing",
    "11-documentation": "documentation",
    "12-devops": "devops",
    "13-observability": "devops",
    "15-context-token-optimizer": "context-optimizer",
}
CATEGORY_SPECIALISTS = {"api": "api", "bug_fix": "debugging", "refactoring": "refactoring"}
DISCOVERY_ORDER = (
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "setup.cfg",
    "docker-compose.yml",
    "Dockerfile",
    ".gitlab-ci.yml",
)
MAX_IMPACT_FILES = 400
MAX_REFERENCES = 20


def specialists(package: dict[str, Any] | None) -> list[str]:
    if not package:
        return []
    found: list[str] = []
    for agent in package.get("selected_agents", []):
        name = SPECIALISTS.get(str(agent.get("id")))
        if name and name not in found:
            found.append(name)
    for category in package.get("classification_details", {}).get("categories", []):
        name = CATEGORY_SPECIALISTS.get(category)
        if name and name not in found:
            found.append(name)
    for entry in package.get("skipped_context", {}).get("agents", {}):
        if (
            entry.startswith("09-")
            and "Targeted review" in str(package["skipped_context"]["agents"][entry])
            and "security" not in found
        ):
            found.append("security")  # targeted review: security rule sections
    return found


def architecture_guidance(det: Detection, task: str) -> str:
    """Proportional architecture. Never proposes microservices unless the task asks for them."""
    if det.mode in ("existing", "kit"):
        arch = (det.values("architecture") or ["its current structure"])[0]
        return (
            f"Keep the existing architecture ({arch}). Make the minimal change in the "
            "existing modules; no unrelated refactoring or technology migration."
        )
    if re.search(r"micro-?services?", task, re.IGNORECASE):
        return (
            "Microservices were requested: confirm the reason (independent deployment or "
            "scaling); otherwise start with one modular service."
        )
    return (
        "New project: start with a simple modular structure (one package, a few focused "
        "modules, tests alongside). Add layers only when the code grows; no microservices, "
        "message brokers or extra infrastructure unless a requirement needs them."
    )


def files_to_read(root: Path, det: Detection) -> list[str]:
    """Progressive discovery order: metadata first, entry points next, then tests."""
    picks = [name for name in DISCOVERY_ORDER if (root / name).is_file()]
    for finding_list in det.findings.values():
        for finding in finding_list.values():
            for evidence in finding.evidence:
                rel = evidence.split(":", 1)[0]
                if ("/" in rel or "." in rel) and rel not in picks and (root / rel).is_file():
                    picks.append(rel)
    return picks[:15]


def impact(root: Path, changed: list[str]) -> dict[str, Any]:
    """Bounded impact analysis: which files reference the files to change (by module name)."""
    targets = {}
    for rel in changed:
        stem = Path(rel).stem
        if stem and stem != "__init__":
            targets[rel] = re.compile(rf"\b{re.escape(stem)}\b")
    references: dict[str, list[str]] = {rel: [] for rel in targets}
    tests: set[str] = set()
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sql", ".yaml", ".yml")):
                continue
            scanned += 1
            if scanned > MAX_IMPACT_FILES:
                break
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            text = read_text(path, 200_000) or ""
            for target, pattern in targets.items():
                if rel != target and pattern.search(text):
                    if len(references[target]) < MAX_REFERENCES:
                        references[target].append(rel)
                    if "test" in rel.lower():
                        tests.add(rel)
    return {
        "references": references,
        "affected_tests": sorted(tests),
        "files_scanned": min(scanned, MAX_IMPACT_FILES),
        "truncated": scanned > MAX_IMPACT_FILES,
    }


def build_plan(
    task: str,
    root: Path,
    det: Detection,
    risk: Risk,
    package: dict[str, Any] | None,
    state: str,
    changed: list[str],
) -> dict[str, Any]:
    selection = kit_selection(det)
    test_fw = det.values("testing", 0.3)
    return {
        "dry_run": True,
        "modifies_files": False,
        "project": {"path": str(root), "mode": det.mode},
        "task": task,
        "routing_state": state,
        "classification": (package or {}).get("classification", []),
        "detected_technology": {
            "languages": det.values("languages", 0.5),
            "frameworks": det.values("frameworks", 0.5),
            "databases": det.values("databases", 0.5),
            "deployment": det.values("deployment", 0.5),
            "profile": selection,
        },
        "specialists": specialists(package),
        "architecture": architecture_guidance(det, task),
        "files_to_read": files_to_read(root, det),
        "files_to_change": changed or ["TO BE DETERMINED after reading the files above"],
        "impact": impact(root, changed) if changed else None,
        "risk": risk.to_dict(),
        "approval_required": risk.approval_required,
        "test_plan": (
            f"Extend the existing tests ({', '.join(test_fw)}); add a regression test "
            "for every behaviour change; run the full suite before and after."
            if test_fw
            else "No tests detected: create a test suite (pytest for Python, the framework's "
            "standard runner otherwise) covering the acceptance criteria."
        ),
        "security_impact": [
            r
            for r in risk.reasons
            if any(k in r for k in ("secret", "auth", "credential", "permission", "production"))
        ]
        or ["No specific security impact detected; apply the security rules in the package."],
        "acceptance_criteria": [
            f"REQ-001: {task}" if task else "REQ-001: TO BE DEFINED",
            "TO BE CONFIRMED with the user for non-trivial tasks",
        ],
    }


def render_plan(plan: dict[str, Any]) -> str:
    risk = plan["risk"]
    tech = plan["detected_technology"]
    detected = tech["languages"] + tech["frameworks"] + tech["databases"] + tech["deployment"]
    approval = "YES - wait for explicit approval" if plan["approval_required"] else "no"
    lines = [
        "NETSF PLAN (dry run - no files were modified)",
        "",
        f"PROJECT            {plan['project']['path']}",
        f"PROJECT MODE       {plan['project']['mode']}",
        f"TASK               {plan['task']}",
        f"CLASSIFICATION     {', '.join(plan['classification']) or '-'}",
        f"DETECTED TECH      {', '.join(detected) or 'none detected'}",
        f"SPECIALISTS        {', '.join(plan['specialists']) or 'master only'}",
        f"ARCHITECTURE       {plan['architecture']}",
        f"RISK               {risk['level']}{' (BLOCKED)' if risk['blocked'] else ''}: "
        f"{'; '.join(risk['reasons']) or '-'}",
        f"APPROVAL REQUIRED  {approval}",
        f"ROUTING STATE      {plan['routing_state']}",
        "",
        "FILES TO READ",
        *[f"  - {f}" for f in plan["files_to_read"]],
        "FILES TO CHANGE",
        *[f"  - {f}" for f in plan["files_to_change"]],
    ]
    if plan["impact"]:
        lines.append("IMPACT")
        for target, refs in plan["impact"]["references"].items():
            lines.append(f"  - {target}: referenced by {', '.join(refs) or 'nothing found'}")
        lines.append(
            f"  affected tests: {', '.join(plan['impact']['affected_tests']) or 'none found'}"
        )
    lines += [
        "TEST PLAN",
        f"  {plan['test_plan']}",
        "SECURITY IMPACT",
        *[f"  - {s}" for s in plan["security_impact"]],
        "ACCEPTANCE CRITERIA",
        *[f"  - {a}" for a in plan["acceptance_criteria"]],
    ]
    return "\n".join(lines)
