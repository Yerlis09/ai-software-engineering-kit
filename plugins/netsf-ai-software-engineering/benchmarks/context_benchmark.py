"""Context benchmark: direct (whole Kit knowledge) versus routed context, per scenario task.

Usage (from the repository root, with the Kit core installed):

    python plugins/netsf-ai-software-engineering/benchmarks/context_benchmark.py [--repeat 5]
        [--json out.json]

Every number is measured by running the bridge in-process on temporary copies of the test
scenarios; nothing is estimated by hand. Tokens use the core's estimator (characters / 4), so
they are approximations of real model tokens. Times are medians over ``--repeat`` runs on the
current machine and vary between machines and runs.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "scripts"), str(HERE.parent / "tests")]

from scenarios import SCENARIOS, build  # noqa: E402

from netsf import bridge  # noqa: E402


def _context(project: Path, task: str, *extra: str) -> dict[str, Any]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bridge.main(["context", "--path", str(project), "--task", task, "--json", *extra])
    return json.loads(out.getvalue())


def _kit_project(base: Path) -> Path:
    from ai_project import cli as kit_cli

    root = base / "kit-app"
    with contextlib.redirect_stdout(io.StringIO()):
        kit_cli.main(
            [
                "init",
                str(root),
                "-y",
                "--name",
                "kit-app",
                "--profile",
                "backend-api",
                "--technology",
                "python-fastapi",
            ]
        )
    return root


def measure(project: Path, scenario: str, task: str, repeat: int) -> dict[str, Any]:
    runs = [_context(project, task) for _ in range(repeat)]
    lean = _context(project, task, "--lean")["metrics"]
    first = runs[0]
    metrics = first["metrics"]
    return {
        "scenario": scenario,
        "task": task,
        "state": first["state"],
        "specialists": first["specialists"],
        "direct_tokens": metrics.get("full_context_tokens"),
        "routed_tokens": metrics.get("emitted_estimated_tokens"),
        "lean_tokens": lean.get("emitted_estimated_tokens"),
        "routed_files": metrics.get("files_loaded"),
        "lean_files": lean.get("files_loaded"),
        "routing_ms": statistics.median(r["metrics"].get("routing_time_ms", 0) for r in runs),
        "materialization_ms": statistics.median(
            r["metrics"].get("materialization_ms", 0) for r in runs
        ),
    }


def run(repeat: int = 5, scenarios: list[str] | None = None) -> list[dict[str, Any]]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        kit = _kit_project(base)
        rows.append(
            measure(kit, "kit-project", "Create a FastAPI endpoint to retrieve cells", repeat)
        )
        for name in scenarios or sorted(SCENARIOS):
            project = build(base / name, name)
            for task, _must, _must_not in SCENARIOS[name]["tasks"]:
                rows.append(measure(project, name, task, repeat))
    return rows


def _pct(part: float | None, whole: float | None) -> str:
    return f"{100 * (1 - part / whole):.1f}%" if part and whole else "n/a"


def render(rows: list[dict[str, Any]]) -> str:
    head = (
        "| Scenario | Task | State | Direct tok | Routed tok | Lean tok | Lean saving | "
        "Files (routed/lean) | Routing ms | Materialize ms |"
    )
    lines = [head, "|" + "---|" * 10]
    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['task']} | {r['state']} | {r['direct_tokens']} | "
            f"{r['routed_tokens']} | {r['lean_tokens']} | "
            f"{_pct(r['lean_tokens'], r['direct_tokens'])} | "
            f"{r['routed_files']}/{r['lean_files']} | "
            f"{r['routing_ms']:.1f} | {r['materialization_ms']:.1f} |"
        )
    direct = sum(r["direct_tokens"] or 0 for r in rows)
    lean = sum(r["lean_tokens"] or 0 for r in rows)
    lines.append(
        f"\nTotal over {len(rows)} tasks: direct {direct} tokens, lean {lean} tokens "
        f"({_pct(lean, direct)} less)."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--json", type=Path, help="also write the raw rows as JSON here")
    args = parser.parse_args(argv)
    rows = run(max(1, args.repeat))
    print(render(rows))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
