"""``ai-project init``: interactive (or flag-driven) project initialisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ai_project import __version__
from ai_project.catalog import Catalog, Selection
from ai_project.console import INFO, PASS, WARN, Console, Prompter
from ai_project.errors import EXIT_OK, EXIT_USAGE, KitError
from ai_project.generator import apply_plan, build_plan
from ai_project.lockfile import LOCK_PATH, Lock, content_hash, write_lock
from ai_project.paths import clean_text, safe_join, validate_project_name

DEFAULT_DEPLOYMENT = "kubernetes"

QUESTIONS = {
    "problem": "Problem solved (for whom, why now)",
    "users": "Users (roles, internal/external, how many)",
    "owner": "Owner (team or person accountable)",
    "functional_requirements": "Main functional requirements",
    "non_functional_requirements": "Non-functional requirements (availability, scalability...)",
    "external_services": "External services / integrations",
    "security_requirements": "Security requirements (data sensitivity, auth, compliance)",
    "performance_requirements": "Performance requirements (latency, volume)",
    "constraints": "Constraints (deadlines, mandated tech, hosting)",
    "risks": "Main risks",
}


@dataclass
class InitOptions:
    directory: str | None = None
    name: str | None = None
    profile: str | None = None
    technology: str | None = None
    database: str | None = None
    deployment: str | None = None
    assistants: list[str] | None = None
    stacks: list[str] = field(default_factory=list)
    description: str | None = None
    non_interactive: bool = False
    force: bool = False


def default_database(profile: str) -> str:
    return "none" if profile in ("frontend", "python-automation") else "postgresql"


def run_init(opts: InitOptions, catalog: Catalog, console: Console, prompter: Prompter) -> int:
    interactive = not opts.non_interactive
    console.title(f"AI SOFTWARE ENGINEERING KIT  (v{__version__})")

    name = _ask_name(opts, prompter, interactive)
    target = Path(opts.directory).expanduser() if opts.directory else Path.cwd() / name
    target = target.resolve()
    _check_target(target, opts.force)

    selection = _ask_selection(opts, catalog, prompter, interactive)
    resolved = catalog.resolve(selection)  # validates every choice

    answers = {"project_name": name, "created_date": date.today().isoformat()}
    answers["description"] = clean_text(
        opts.description
        if opts.description is not None or not interactive
        else prompter.text("Business objective (one sentence)")
    )
    if interactive and prompter.confirm(
        "\nDescribe the project in more detail now? (can be done later in .ai/context/project.md)",
        default=False,
    ):
        for key, label in QUESTIONS.items():
            answers[key] = clean_text(prompter.text(f"{label} (Enter to skip)"))
    answers = {k: v for k, v in answers.items() if v}

    _print_summary(console, catalog, name, target, selection, resolved)
    if interactive and not prompter.confirm("Generate the project?", default=True):
        console.print("Aborted, nothing was written.")
        return EXIT_OK

    plan = build_plan(catalog, resolved, selection, answers)
    target.mkdir(parents=True, exist_ok=True)
    report = apply_plan(target, plan, force=opts.force)
    write_lock(
        target,
        Lock(
            kit_version=__version__,
            selection=selection.to_dict(),
            answers=answers,
            managed={p.path: content_hash(p.content) for p in plan if p.managed},
            seeds=[p.path for p in plan if not p.managed],
        ),
    )
    _print_result(console, target, report)
    return EXIT_OK


def _ask_name(opts: InitOptions, prompter: Prompter, interactive: bool) -> str:
    if opts.name:
        return validate_project_name(opts.name)
    default = ""
    if opts.directory:
        candidate = Path(opts.directory).expanduser().resolve().name
        try:
            default = validate_project_name(candidate)
        except KitError:
            default = ""
    if not interactive:
        if default:
            return default
        raise KitError("--name is required with --non-interactive.", EXIT_USAGE)
    return prompter.text(
        "Project name", default=default, required=True, validate=validate_project_name
    )


def _check_target(target: Path, force: bool) -> None:
    if target.exists() and not target.is_dir():
        raise KitError(f"{target} exists and is not a directory.", EXIT_USAGE)
    if safe_join(target, LOCK_PATH).exists() and not force:
        raise KitError(
            f"{target} is already initialised ({LOCK_PATH} exists). "
            "Use 'ai-project update' to refresh it, or --force to re-initialise.",
            EXIT_USAGE,
        )


def _ask_selection(
    opts: InitOptions, catalog: Catalog, prompter: Prompter, interactive: bool
) -> Selection:
    def pick(value, label, options, default):
        if value or not interactive:
            return value or default
        prompter.console.print()
        return prompter.choose(label, options, default)

    profile_key = pick(
        opts.profile,
        "Project type",
        [(k, f"{p.title} - {p.description}") for k, p in catalog.profiles.items()],
        None,
    )
    if not profile_key:
        raise KitError("--profile is required with --non-interactive.", EXIT_USAGE)
    profile = catalog.profiles.get(profile_key)
    if profile is None:
        raise KitError(
            f"Unknown profile '{profile_key}'. Choose one of: {', '.join(catalog.profiles)}",
            EXIT_USAGE,
        )
    technology = pick(
        opts.technology,
        "Technology",
        [
            (k, catalog.technologies[k].title)
            for k in profile.technologies
            if k in catalog.technologies
        ],
        profile.technologies[0],
    )
    extra_stacks = list(opts.stacks)
    if technology == "custom" and interactive and not extra_stacks:
        prompter.console.print()
        extra_stacks = prompter.choose_many(
            "Stack guides to include", [(s, s) for s in catalog.available_stacks()], []
        )
    database = pick(
        opts.database,
        "Database",
        [(k, o.title) for k, o in catalog.databases.items()],
        default_database(profile.name),
    )
    deployment = pick(
        opts.deployment,
        "Deployment",
        [(k, o.title) for k, o in catalog.deployments.items()],
        DEFAULT_DEPLOYMENT,
    )
    if opts.assistants is not None:
        assistants = opts.assistants
    elif interactive:
        prompter.console.print()
        assistants = prompter.choose_many(
            "AI assistants used by the team",
            [(k, o.title) for k, o in catalog.assistants.items()],
            list(catalog.assistants),
        )
    else:
        assistants = list(catalog.assistants)
    return Selection(
        profile.name, technology, database, deployment, tuple(assistants), tuple(extra_stacks)
    )


def _print_summary(console, catalog, name, target, selection, resolved) -> None:
    console.section("Summary")
    rows = [
        ("Project", name),
        ("Directory", str(target)),
        ("Profile", catalog.profiles[selection.profile].title),
        ("Technology", catalog.technologies[selection.technology].title),
        ("Database", catalog.databases[selection.database].title),
        ("Deployment", catalog.deployments[selection.deployment].title),
        ("Agents", str(len(resolved.agents))),
        ("Stack guides", ", ".join(resolved.stacks) or "-"),
        ("Assistants", ", ".join(resolved.assistants) or "-"),
    ]
    for label, value in rows:
        console.print(f"  {label:<13} {value}")
    console.print()


def _print_result(console: Console, target: Path, report) -> None:
    console.section("Result")
    console.status(PASS, f"{len(report.created)} file(s) created")
    if report.unchanged:
        console.status(PASS, f"{len(report.unchanged)} kit file(s) already up to date")
    if report.skipped:
        console.status(INFO, f"{len(report.skipped)} existing project file(s) kept untouched")
    for path in report.overwritten:
        console.status(WARN, f"{path} replaced (previous version in {path}.kit-backup)")
    for path in report.conflicts:
        console.status(WARN, f"{path} differs from the kit version", f"see {path}.kit-new")
    if report.conflicts:
        console.print("    -> Merge each .kit-new file by hand, then delete it.")
    console.section("Next steps")
    for step in (
        f"cd {target}",
        "Complete .ai/context/project.md (the AI reads it first)",
        "Open the project with your AI assistant: it starts from AGENTS.md",
        "Ask it to follow .ai/workflows/new-project.md",
        "Run 'ai-project doctor' to check the setup",
    ):
        console.print(f"  - {step}")
