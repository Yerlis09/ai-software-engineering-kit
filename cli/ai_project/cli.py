"""Command-line entry point: argument parsing and dispatch only."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Callable, Sequence

from ai_project import __version__
from ai_project.catalog import Catalog
from ai_project.console import Console, Prompter
from ai_project.context_cmd import ContextOptions, run_context
from ai_project.doctor import print_report, run_doctor
from ai_project.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, KitError
from ai_project.init_cmd import InitOptions, run_init
from ai_project.lockfile import read_lock
from ai_project.paths import kit_root
from ai_project.updater import run_update

DESCRIPTION = """\
AI Software Engineering Kit: start projects that AI assistants develop
following the team's engineering standards (agents, rules, workflows).
"""

EPILOG = """\
examples:
  ai-project init                       interactive wizard, creates ./<name>/
  ai-project init .                     add the kit to the current (existing) project
  ai-project init --non-interactive --name billing-api --profile backend-api \\
      --technology python-fastapi --database postgresql
  ai-project doctor                     check the current project (CI-friendly)
  ai-project update --dry-run           preview kit updates
  ai-project list profiles              show available profiles
  ai-project context --task "add customer endpoint"   minimum context for a task

exit codes: 0 success, 1 failure (doctor FAIL, update pending with --check), 2 usage error
"""


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-project",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"ai-project {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    init = sub.add_parser(
        "init",
        help="create a project or add the kit to an existing one",
        description="Initialise a project with the AI engineering kit.",
    )
    init.add_argument(
        "directory", nargs="?", help="target directory (default: ./<project-name>; '.' = current)"
    )
    init.add_argument("--name", help="project name (letters, digits, - _ .)")
    init.add_argument("--profile", help="project profile (see 'ai-project list profiles')")
    init.add_argument("--technology", help="technology preset (see 'list technologies')")
    init.add_argument("--database", help="database (see 'list databases')")
    init.add_argument("--deployment", help="deployment target (see 'list deployments')")
    init.add_argument("--assistants", type=_csv, help="comma-separated, e.g. claude-code,copilot")
    init.add_argument(
        "--stacks",
        type=_csv,
        default=[],
        help="extra stack guides, comma-separated (see 'list stacks')",
    )
    init.add_argument("--description", help="business objective, one sentence")
    init.add_argument(
        "--non-interactive", "-y", action="store_true", help="never prompt; use flags and defaults"
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="re-initialise; replace differing kit files (backups are kept)",
    )

    doctor = sub.add_parser("doctor", help="validate the project against the kit standards")
    doctor.add_argument("--path", default=".", help="project directory (default: current)")
    doctor.add_argument("--strict", action="store_true", help="treat warnings as failures")
    doctor.add_argument("--format", choices=("text", "json"), default="text")

    update = sub.add_parser("update", help="update kit files without losing customisations")
    update.add_argument("--path", default=".", help="project directory (default: current)")
    mode = update.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    mode.add_argument(
        "--check", action="store_true", help="exit 1 if updates are pending (for CI), write nothing"
    )
    update.add_argument(
        "--force",
        action="store_true",
        help="resolve conflicts with the kit version (backups are kept)",
    )

    ctx = sub.add_parser(
        "context",
        help="show the minimum context (agents, rules, stacks) a task needs",
        description="Select the minimum context for a task and estimate its size "
        "(characters / 4: an estimate, not the provider's token count).",
    )
    ctx.add_argument("--task", help='task description, e.g. "add GET /health endpoint"')
    ctx.add_argument("--path", default=".", help="project directory (default: current)")
    ctx.add_argument("--profile", help="simulate a project of this profile instead of --path")
    ctx.add_argument("--technology", help="with --profile: technology preset")
    ctx.add_argument("--database", help="with --profile: database")
    ctx.add_argument("--json", action="store_true", help="machine-readable context package")
    ctx.add_argument("--strict", action="store_true", help="exit 1 when over budget")
    ctx.add_argument(
        "--rebuild-graph",
        action="store_true",
        help="regenerate and validate .ai/context/graph.json from the kit sources",
    )

    lst = sub.add_parser("list", help="list profiles, technologies, stacks, agents...")
    lst.add_argument(
        "what",
        nargs="?",
        default="profiles",
        choices=(
            "profiles",
            "technologies",
            "databases",
            "deployments",
            "assistants",
            "stacks",
            "agents",
        ),
    )

    sub.add_parser("version", help="show CLI, kit and project versions")
    help_cmd = sub.add_parser("help", help="show help for a command")
    help_cmd.add_argument("topic", nargs="?", help="command name")
    return parser


def main(
    argv: Sequence[str] | None = None,
    console: Console | None = None,
    input_fn: Callable[[str], str] = input,
) -> int:
    console = console or Console()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed the message
        return int(exc.code or 0)
    if args.command in (None, "help"):
        topic = getattr(args, "topic", None)
        if topic:
            return main([topic, "--help"], console, input_fn)
        console.print(parser.format_help())
        return EXIT_OK
    try:
        return _dispatch(args, console, input_fn)
    except KitError as exc:
        console.error(str(exc))
        return exc.exit_code
    except KeyboardInterrupt:
        console.error("Interrupted.")
        return EXIT_USAGE
    except OSError as exc:
        console.error(f"File system error: {exc}")
        return EXIT_FAILURE


def _dispatch(args: argparse.Namespace, console: Console, input_fn) -> int:
    if args.command == "version":
        return _version(console)
    catalog = Catalog(kit_root())
    if args.command == "init":
        options = InitOptions(
            directory=args.directory,
            name=args.name,
            profile=args.profile,
            technology=args.technology,
            database=args.database,
            deployment=args.deployment,
            assistants=args.assistants,
            stacks=args.stacks,
            description=args.description,
            non_interactive=args.non_interactive,
            force=args.force,
        )
        return run_init(options, catalog, console, Prompter(console, input_fn))
    if args.command == "doctor":
        root = _project_dir(args.path)
        report = run_doctor(root, catalog.organization, catalog.routing)
        if args.format == "json":
            console.print(report.to_json())
        else:
            print_report(report, console, catalog.organization.get("security_contact", ""))
        return report.exit_code(args.strict)
    if args.command == "update":
        return run_update(
            _project_dir(args.path),
            catalog,
            console,
            dry_run=args.dry_run,
            check=args.check,
            force=args.force,
        )
    if args.command == "context":
        context_options = ContextOptions(
            task=args.task,
            path=args.path,
            profile=args.profile,
            technology=args.technology,
            database=args.database,
            as_json=args.json,
            strict=args.strict,
            rebuild_graph=args.rebuild_graph,
        )
        return run_context(context_options, catalog, console)
    if args.command == "list":
        return _list(catalog, console, args.what)
    raise KitError(f"Unknown command {args.command}", EXIT_USAGE)


def _project_dir(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise KitError(f"{root} is not a directory.", EXIT_USAGE)
    return root


def _version(console: Console) -> int:
    console.print(f"ai-project {__version__}")
    try:
        console.print(f"Kit:     {kit_root()}")
    except KitError as exc:
        console.print(f"Kit:     NOT FOUND ({exc})")
    console.print(f"Python:  {platform.python_version()} ({sys.platform})")
    try:
        lock = read_lock(Path.cwd())
    except KitError:
        lock = None
    if lock:
        console.print(f"Project: generated with kit {lock.kit_version}")
    return EXIT_OK


def _list(catalog: Catalog, console: Console, what: str) -> int:
    if what == "profiles":
        rows = [(k, f"{p.title} - {p.description}") for k, p in catalog.profiles.items()]
    elif what == "stacks":
        rows = [(s, f"stacks/{s}/README.md") for s in catalog.available_stacks()]
    elif what == "agents":
        rows = [(a, catalog.agent_title(a)) for a in catalog.available_agents()]
    else:
        rows = [(k, o.title) for k, o in getattr(catalog, what).items()]
    width = max(len(k) for k, _ in rows)
    console.title(what.capitalize())
    for key, title in rows:
        console.print(f"  {key:<{width}}  {title}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
