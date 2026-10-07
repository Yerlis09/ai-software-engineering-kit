"""Command implementations behind ``netsf_bridge.py`` (one function per sub-command)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from netsf import CORE_RANGE, PLUGIN_VERSION
from netsf.core import (
    BLOCKED,
    DEGRADED,
    DIRECT,
    OPTIMIZED,
    CoreInfo,
    core_info,
    load_lock_hashes,
    materialize,
    render_markdown,
    run_core,
)
from netsf.detect import detect, kit_selection, snapshot
from netsf.plan import build_plan, render_plan, specialists
from netsf.risk import assess
from netsf.safety import clean_task

DIRECT_GUIDANCE = (
    "DIRECT MODE: the Kit core is not available, so no curated context was loaded. Work with "
    "progressive discovery (structure, metadata, README, dependencies, then only relevant "
    "files) and the essential rules in the NETSF AI Engineer skill. Tell the user optimisation "
    "is off and how to enable it (/netsf-ai-software-engineering:setup)."
)
LOW_CONFIDENCE = 0.5


def _root(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"error: {root} is not a directory")
    return root


def _print(data: Any, as_json: bool, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if as_json else text)


def cmd_check(args: argparse.Namespace) -> int:
    info = core_info()
    data = {"plugin_version": PLUGIN_VERSION, "core": info.to_dict()}
    text = (
        f"NETSF AI Software Engineering {PLUGIN_VERSION}\n"
        f"Core: {info.status} ({info.version or 'not found'}; required {CORE_RANGE})\n"
        f"{info.message}"
    )
    _print(data, args.json, text)
    return 0 if info.status == "OK" else 1


def cmd_detect(args: argparse.Namespace) -> int:
    det = detect(_root(args.path))
    data = snapshot(det) if args.snapshot else det.to_dict()
    if args.json:
        _print(data, True, "")
        return 0
    lines = [
        f"PROJECT DETECTION ({det.mode}) - heuristic, check uncertain items",
        f"root: {det.root}  (files considered {det.files_considered}, read {det.files_read})",
    ]
    for category, findings in det.to_dict()["findings"].items():
        for f in findings:
            lines.append(
                f"  {category:<12} {f['value']:<24} {f['confidence']:.0%}  "
                f"evidence: {', '.join(f['evidence'][:3])}"
            )
    sel = kit_selection(det)
    lines.append(
        f"  likely profile: {sel['profile']} / {sel['technology']} / {sel['database']} "
        f"({sel['confidence']:.0%}; {', '.join(sel['reasons'])})"
    )
    print("\n".join(lines))
    return 0


def route(
    task: str, root: Path, info: CoreInfo
) -> tuple[str, dict[str, Any] | None, list[str], bool]:
    """Ask the core for the context package. Returns (state, package, notes, project_mode)."""
    if info.status != "OK":
        return DIRECT, None, [info.message], False
    project_mode = (root / ".ai" / "kit.lock.json").is_file()
    notes: list[str] = []
    if project_mode:
        argv = ["context", "--path", str(root), "--task", task, "--json"]
    else:
        det = detect(root)
        sel = kit_selection(det)
        argv = [
            "context",
            "--profile",
            sel["profile"],
            "--technology",
            sel["technology"],
            "--database",
            sel["database"],
            "--task",
            task,
            "--json",
        ]
        notes.append(
            f"Project not initialised with the Kit: routing simulated as "
            f"{sel['profile']}/{sel['technology']}/{sel['database']} "
            f"(detection confidence {sel['confidence']:.0%})."
        )
        if sel["confidence"] < LOW_CONFIDENCE:
            notes.append("Low detection confidence: confirm the technology before large changes.")
    try:
        result = run_core(info.command, argv)
        package = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return DIRECT, None, [f"Core context call failed ({exc})."], project_mode
    if result.returncode != 0 or not isinstance(package, dict):
        return DIRECT, None, [f"Core context call failed (exit {result.returncode})."], project_mode
    state = OPTIMIZED
    if package.get("mode") != "graph" or not project_mode:
        state = DEGRADED
    notes += [str(w) for w in package.get("warnings", [])]
    return state, package, notes, project_mode


def cmd_context(args: argparse.Namespace) -> int:
    task = clean_task(args.task)
    root = _root(args.path)
    info = core_info()
    state, package, notes, project_mode = route(task, root, info)
    risk = assess(task)
    if risk.blocked:
        state, package = BLOCKED, None
        notes.insert(0, "Task refused: " + "; ".join(risk.reasons))
    mat = None
    if package is not None:
        mat = materialize(
            package,
            project_mode=project_mode,
            root=root,
            kit_root=info.kit_root,
            managed_hashes=load_lock_hashes(root) if project_mode else {},
            focus=args.focus,
            lean=args.lean,
        )
        if mat.state == BLOCKED:
            state = BLOCKED
        notes += mat.notes
    data = _context_data(task, state, package, mat, notes, risk.to_dict(), args.focus)
    if args.json:
        _print(data, True, "")
    else:
        print(_context_text(data, mat))
    return 1 if state == BLOCKED else 0


def _context_data(task, state, package, mat, notes, risk, focus) -> dict[str, Any]:
    metrics = dict((package or {}).get("metrics", {}))
    if mat is not None:
        metrics.update(
            files_loaded=len({b.path for b in mat.blocks}),
            emitted_characters=mat.characters,
            emitted_estimated_tokens=mat.estimated_tokens,
            materialization_ms=mat.materialization_ms,
            untrusted_blocks=sum(1 for b in mat.blocks if not b.trusted),
            injection_warnings=sum(len(b.injection) for b in mat.blocks),
        )
    return {
        "plugin_version": PLUGIN_VERSION,
        "state": state,
        "task": task,
        "focus": focus,
        "classification": (package or {}).get("classification", []),
        "specialists": specialists(package),
        "risk": risk,
        "budget": (package or {}).get("budget", {}),
        "selected": (package or {}).get("selected", []),
        "skipped": (package or {}).get("skipped", []),
        "metrics": metrics,
        "notes": notes,
        "guidance": DIRECT_GUIDANCE if state == DIRECT else None,
    }


def _context_text(data: dict[str, Any], mat) -> str:
    m = data["metrics"]
    head = [
        f"NETSF CONTEXT PACKAGE  state={data['state']}  risk={data['risk']['level']}"
        + ("  APPROVAL REQUIRED" if data["risk"]["approval_required"] else ""),
        f"classification: {', '.join(data['classification']) or '-'}",
        f"specialists: {', '.join(data['specialists']) or '-'}",
    ]
    if m.get("emitted_estimated_tokens") is not None:
        head.append(
            f"emitted ~{m['emitted_estimated_tokens']:,} tokens (estimate) from "
            f"{m.get('files_loaded', 0)} files; full kit context "
            f"~{m.get('full_context_tokens', 0):,}; routing {m.get('routing_time_ms')} ms, "
            f"materialization {m.get('materialization_ms')} ms"
        )
    head += [f"note: {n}" for n in data["notes"]]
    if data["guidance"]:
        head.append(data["guidance"])
    body = render_markdown(mat) if mat is not None and data["state"] != BLOCKED else ""
    return "\n".join(head) + ("\n\n" + body if body else "")


def cmd_risk(args: argparse.Namespace) -> int:
    risk = assess(clean_task(args.task), args.files or [])
    data = risk.to_dict()
    _print(
        data,
        args.json,
        f"RISK {data['level']}{' BLOCKED' if data['blocked'] else ''} - "
        f"approval required: {'yes' if data['approval_required'] else 'no'}\n"
        + "\n".join(f"  - {r}" for r in data["reasons"]),
    )
    return 1 if risk.blocked else 0


def cmd_plan(args: argparse.Namespace) -> int:
    task = clean_task(args.task)
    root = _root(args.path)
    det = detect(root)
    risk = assess(task, args.change or [])
    info = core_info()
    state, package, notes, _ = (
        route(task, root, info) if not risk.blocked else (BLOCKED, None, [], False)
    )
    plan = build_plan(task, root, det, risk, package, state, args.change or [])
    plan["notes"] = notes
    _print(plan, args.json, render_plan(plan) + "".join(f"\nnote: {n}" for n in notes))
    return 1 if risk.blocked else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netsf_bridge", description="NETSF Kit adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="core availability and compatibility")
    check.add_argument("--json", action="store_true")
    det = sub.add_parser("detect", help="heuristic project detection")
    det.add_argument("--path", default=".")
    det.add_argument("--snapshot", action="store_true", help="compact project snapshot")
    det.add_argument("--json", action="store_true")
    ctx = sub.add_parser("context", help="materialised minimal context package")
    ctx.add_argument("--task", required=True)
    ctx.add_argument("--path", default=".")
    ctx.add_argument("--focus", help="Kit agent id, e.g. 02-backend (specialist view)")
    ctx.add_argument(
        "--lean",
        action="store_true",
        help="omit AGENTS.md and the Kit master agent (the NETSF skill orchestrates)",
    )
    ctx.add_argument("--json", action="store_true")
    rsk = sub.add_parser("risk", help="risk level and approval requirement")
    rsk.add_argument("--task", required=True)
    rsk.add_argument("--files", nargs="*")
    rsk.add_argument("--json", action="store_true")
    pln = sub.add_parser("plan", help="dry-run plan (never modifies files)")
    pln.add_argument("--task", required=True)
    pln.add_argument("--path", default=".")
    pln.add_argument("--change", nargs="*", help="files expected to change (impact analysis)")
    pln.add_argument("--json", action="store_true")
    return parser


COMMANDS = {
    "check": cmd_check,
    "detect": cmd_detect,
    "context": cmd_context,
    "risk": cmd_risk,
    "plan": cmd_plan,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)
