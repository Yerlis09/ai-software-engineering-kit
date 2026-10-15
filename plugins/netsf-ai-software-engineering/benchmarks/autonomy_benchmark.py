"""Autonomy benchmark: how much user interaction and context one request needs.

Usage (from the repository root, with the Kit core installed):

    python plugins/netsf-ai-software-engineering/benchmarks/autonomy_benchmark.py [--json out.json]

For each scenario (one request on a temporary project) it runs the bridge's ``start`` command and
reports the decision and the autonomy metrics: user prompts required, approval requests,
blocking questions, specialists, context tokens, files inspected, relevant files found and test
commands detected. It measures the deterministic workflow layer; what the model then does
(files changed, tests executed, repair attempts) needs a real model run (``evals/``).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "scripts"), str(HERE.parent / "tests")]

from scenarios import build  # noqa: E402
from test_plugin_autonomy import STORY, flask_project  # noqa: E402

from netsf import bridge  # noqa: E402

SCENARIOS: list[tuple[str, str, str]] = [
    ("existing-flask", "flask", STORY),
    ("existing-flask-route-exists", "flask-with-route", STORY),
    (
        "existing-flask-migration",
        "flask",
        "Add a region column to the cells table with a database migration",
    ),
    ("existing-flask-dry-run", "flask", "Dry run: " + STORY),
    ("existing-fastapi", "scenario:fastapi", "Add validation to the cells endpoint"),
    ("existing-react", "scenario:frontend", "Improve React dashboard performance"),
    ("new-api-with-persistence", "empty", "I need an API to manage cells and equipment"),
    (
        "new-file-processing",
        "empty",
        "An API that receives an Excel file, processes it and returns a generated output file",
    ),
]


def _project(base: Path, kind: str) -> Path:
    root = base / kind.replace(":", "-")
    root.mkdir(parents=True)
    if kind == "flask":
        return flask_project(root)
    if kind == "flask-with-route":
        return flask_project(root, with_get_by_id=True)
    if kind.startswith("scenario:"):
        return build(root, kind.split(":", 1)[1])
    return root


def _brief(project: Path, task: str) -> dict[str, Any]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bridge.main(["start", "--path", str(project), "--task", task, "--json"])
    return json.loads(out.getvalue())


def run() -> list[dict[str, Any]]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, kind, task in SCENARIOS:
            data = _brief(_project(Path(tmp) / name, kind), task)
            autonomy = data["metrics"]["autonomy"]
            rows.append(
                {
                    "scenario": name,
                    "decision": data["decision"]["action"],
                    "execution": data["decision"]["execution"]["mode"],
                    **autonomy,
                }
            )
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    head = (
        "| Scenario | Decision | Execution | Prompts | Approvals | Questions | Specialists | "
        "Context tok | Files inspected | Relevant files | Test cmds |"
    )
    lines = [head, "|" + "---|" * 11]
    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['decision']} | {r['execution']} | "
            f"{r['user_prompts_required']} | {r['approval_requests']} | {r['questions']} | "
            f"{r['specialists']} | {r['context_tokens']} | {r['files_inspected']} | "
            f"{r['relevant_files']} | {r['test_commands']} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="also write the raw rows as JSON here")
    args = parser.parse_args(argv)
    rows = run()
    print(render(rows))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
