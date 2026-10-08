"""``ai-project doctor``: validate a project against the kit standards.

Each check returns PASS / WARN / FAIL / INFO. Exit code: 0 when there is no FAIL
(1 with ``--strict`` when there are warnings), so CI pipelines can gate on it.
"""

from __future__ import annotations

import configparser
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ai_project import __version__
from ai_project.catalog import deployment_in_scope
from ai_project.code_hygiene import scan_comments
from ai_project.console import FAIL, INFO, PASS, WARN, Console
from ai_project.context_graph import GRAPH_PATH, check_project_graph
from ai_project.context_index import BUDGET_PATH, INDEX_PATH, read_index
from ai_project.context_router import parse_budget
from ai_project.errors import EXIT_FAILURE, EXIT_OK, KitError
from ai_project.lockfile import LOCK_PATH, file_hash, parse_version, read_lock
from ai_project.paths import safe_join
from ai_project.secrets_scan import Finding, is_env_file, iter_files, scan

CATEGORIES = (
    "Configuration",
    "Knowledge Graph",
    "Kit integrity",
    "Git",
    "Quality",
    "Security",
    "Documentation",
    "Environment",
)


@dataclass(frozen=True)
class Check:
    category: str
    name: str
    status: str
    detail: str = ""
    hint: str = ""


@dataclass
class Report:
    root: str
    checks: list[Check]
    env_secrets: list[Finding]

    @property
    def result(self) -> str:
        statuses = {c.status for c in self.checks}
        return FAIL if FAIL in statuses else (WARN if WARN in statuses else PASS)

    def exit_code(self, strict: bool) -> int:
        if self.result == FAIL or (strict and self.result == WARN):
            return EXIT_FAILURE
        return EXIT_OK

    def to_json(self) -> str:
        return json.dumps(
            {
                "root": self.root,
                "kit_version": __version__,
                "result": self.result,
                "checks": [asdict(c) for c in self.checks],
            },
            indent=2,
        )


class _Project:
    """Read-only helpers over the project directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._files: list[str] | None = None

    def files(self) -> list[str]:
        """Relative POSIX paths of project files, skipping vendored dirs (.venv, node_modules)
        and never following symlinks. Computed once."""
        if self._files is None:
            self._files = [rel for _, rel in iter_files(self.root)]
        return self._files

    def path(self, rel: str) -> Path:
        return safe_join(self.root, rel)

    def exists(self, *rels: str) -> bool:
        return any(self.path(r).exists() for r in rels)

    def text(self, rel: str) -> str:
        try:
            return self.path(rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def glob(self, pattern: str) -> list[Path]:
        regex = _glob_regex(pattern)
        return [self.root / rel for rel in self.files() if regex.fullmatch(rel)]

    def package_json(self) -> dict:
        try:
            data = json.loads(self.text("package.json") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def npm_dependencies(self) -> set[str]:
        pkg = self.package_json()
        names: set[str] = set()
        for key in ("dependencies", "devDependencies"):
            section = pkg.get(key)
            if isinstance(section, dict):
                names.update(str(name) for name in section)
        return names


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Glob -> regex on POSIX relative paths: ``**/`` = any directories, ``*`` = within one."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out)


def run_doctor(
    root: Path,
    organization: dict[str, str] | None = None,
    routing: Mapping[str, Any] | None = None,
) -> Report:
    project = _Project(root)
    org = organization or {}
    checks: list[Check] = []
    for group in (
        _configuration,
        _context_routing,
        lambda p: _knowledge_graph(p, routing),
        _kit_integrity,
        lambda p: _git(p, org.get("git_server", "")),
        _quality,
        _code_comments,
        _security_config,
        _documentation,
        _environment,
    ):
        checks.extend(group(project))
    findings = scan(root)
    checks.extend(_secret_checks(findings, org.get("security_contact", "")))
    order = {c: i for i, c in enumerate(CATEGORIES)}
    checks.sort(key=lambda c: order.get(c.category, 99))
    return Report(str(root), checks, [f for f in findings if f.in_env_file])


def _exists_check(
    project: _Project, category: str, name: str, rels: tuple[str, ...], missing: str, hint: str
) -> Check:
    if project.exists(*rels):
        return Check(category, name, PASS)
    return Check(category, name, missing, "not found", hint)


# --- Configuration -----------------------------------------------------------------------
def _configuration(project: _Project) -> list[Check]:
    cat = "Configuration"
    checks = [
        _exists_check(
            project,
            cat,
            "AGENTS.md",
            ("AGENTS.md",),
            FAIL,
            "Run 'ai-project init .' to add the AI configuration.",
        ),
    ]
    for label, folder, required in (
        ("Agents", ".ai/agents", ".ai/agents/00-master.md"),
        ("Rules", ".ai/rules", None),
        ("Workflows", ".ai/workflows", None),
    ):
        files = list(project.path(folder).glob("*.md")) if project.exists(folder) else []
        if not files or (required and not project.exists(required)):
            checks.append(
                Check(
                    cat,
                    label,
                    FAIL,
                    f"{folder}/ missing or incomplete",
                    "Run 'ai-project update' to restore kit files.",
                )
            )
        else:
            checks.append(Check(cat, label, PASS, f"{len(files)} file(s)"))
    context = ".ai/context/project.md"
    if not project.exists(context):
        checks.append(
            Check(
                cat,
                "Project context",
                FAIL,
                f"{context} missing",
                "Describe the project there: AI assistants read it first.",
            )
        )
    else:
        todos = project.text(context).count("TODO")
        if todos:
            checks.append(
                Check(
                    cat,
                    "Project context",
                    WARN,
                    f"{todos} TODO(s) left",
                    f"Complete {context} so the AI understands the project.",
                )
            )
        else:
            checks.append(Check(cat, "Project context", PASS))
    return checks


# --- Context routing -------------------------------------------------------------------------
def _context_routing(project: _Project) -> list[Check]:
    cat = "Configuration"
    checks = []
    if not project.exists(INDEX_PATH):
        checks.append(
            Check(
                cat,
                "Context index",
                WARN,
                f"{INDEX_PATH} missing",
                "Run 'ai-project update' to enable context routing.",
            )
        )
    elif read_index(project.text(INDEX_PATH)) is None:
        checks.append(
            Check(
                cat,
                "Context index",
                WARN,
                "invalid JSON or unknown schema",
                "Run 'ai-project update' to regenerate it.",
            )
        )
    else:
        checks.append(Check(cat, "Context index", PASS))
    if project.exists(BUDGET_PATH):
        try:
            parse_budget(project.text(BUDGET_PATH))
            checks.append(Check(cat, "Context budget", PASS))
        except KitError as exc:
            checks.append(
                Check(
                    cat,
                    "Context budget",
                    WARN,
                    str(exc),
                    "Fix the values (positive integers) or delete the file.",
                )
            )
    return checks


# --- Knowledge graph ---------------------------------------------------------------------------
GRAPH_RECOVERY = "Run 'ai-project context --rebuild-graph' (or 'ai-project update')."


def _knowledge_graph(project: _Project, routing: Mapping[str, Any] | None) -> list[Check]:
    """Never FAIL: a missing or bad graph only disables graph routing (direct fallback)."""
    cat = "Knowledge Graph"
    if routing is None:
        return []
    try:
        lock = read_lock(project.root)
    except KitError:
        lock = None
    result = check_project_graph(project.root, routing, __version__, lock)
    if result.state == "missing":
        return [Check(cat, "Graph exists", WARN, f"{GRAPH_PATH} not found", GRAPH_RECOVERY)]
    if result.state == "invalid":
        return [
            Check(cat, "Graph exists", PASS),
            Check(
                cat,
                "Graph validation",
                WARN,
                "; ".join(result.issues[:3]),
                f"Corrupt or invalid graph (direct routing is used). {GRAPH_RECOVERY}",
            ),
        ]
    stats = result.graph.stats() if result.graph else {"nodes": 0, "edges": 0}
    checks = [
        Check(cat, "Graph exists", PASS, f"{stats['nodes']} nodes, {stats['edges']} edges"),
        Check(cat, "Graph structure", PASS),
        Check(cat, "Node and edge types", PASS),
        Check(cat, "References", PASS),
        Check(cat, "Project paths", PASS),
        Check(cat, "No cycles", PASS),
    ]
    if result.state == "stale":
        checks.append(Check(cat, "Source fingerprint", WARN, "graph is stale", GRAPH_RECOVERY))
    elif lock is None:
        checks.append(Check(cat, "Source fingerprint", INFO, "no lock file: not verifiable"))
    else:
        checks.append(Check(cat, "Source fingerprint", PASS, "up to date"))
    return checks


# --- Kit integrity ------------------------------------------------------------------------
def _kit_integrity(project: _Project) -> list[Check]:
    cat = "Kit integrity"
    lock = read_lock(project.root)
    if lock is None:
        return [
            Check(
                cat,
                "Lock file",
                WARN,
                f"{LOCK_PATH} not found",
                "Project not generated by the kit: 'ai-project update' cannot run.",
            )
        ]
    checks = [Check(cat, "Lock file", PASS, f"kit {lock.kit_version}")]
    missing, modified = [], []
    for rel, expected in lock.managed.items():
        actual = file_hash(project.path(rel))
        if actual is None:
            missing.append(rel)
        elif actual != expected:
            modified.append(rel)
    if missing:
        checks.append(
            Check(
                cat,
                "Core files present",
                WARN,
                f"{len(missing)} missing: " + ", ".join(missing[:3]),
                "Run 'ai-project update' to restore them.",
            )
        )
    else:
        checks.append(Check(cat, "Core files present", PASS, f"{len(lock.managed)} file(s)"))
    if modified:
        checks.append(
            Check(
                cat,
                "Core files customised",
                INFO,
                f"{len(modified)} modified: " + ", ".join(modified[:3]),
                "Prefer .ai/custom/ for overrides; update will report conflicts.",
            )
        )
    if parse_version(lock.kit_version) < parse_version(__version__):
        checks.append(
            Check(
                cat,
                "Kit version",
                INFO,
                f"project {lock.kit_version}, kit {__version__} available",
                "Run 'ai-project update'.",
            )
        )
    return checks


# --- Git ------------------------------------------------------------------------------------
def _git(project: _Project, git_server: str) -> list[Check]:
    cat = "Git"
    checks = []
    git_dir = _find_git_dir(project.root)
    if git_dir is None:
        checks.append(
            Check(
                cat,
                "Repository",
                WARN,
                "not a Git repository",
                "Propose 'git init' in this directory and run it only with approval; the team "
                f"provides the repository URL on {git_server or 'the Git server'} "
                "(never invent it).",
            )
        )
    else:
        if git_dir.parent == project.root:
            checks.append(Check(cat, "Repository", PASS))
        else:
            checks.append(
                Check(
                    cat,
                    "Repository",
                    WARN,
                    f"no repository of its own: inside the parent repository {git_dir.parent}",
                    "Confirm the parent repository is this project's (monorepo); otherwise "
                    "propose 'git init' here and wait for approval. Never commit to it by default.",
                )
            )
        remotes = _git_remotes(git_dir / "config") if git_dir.is_dir() else []
        if not remotes:
            checks.append(
                Check(
                    cat,
                    "Remote",
                    WARN,
                    "no remote configured",
                    f"Ask the team for the repository URL on {git_server or 'the Git server'} and "
                    "add it with approval; never invent a remote.",
                )
            )
        elif git_server and not any(git_server in url for url in remotes):
            checks.append(
                Check(
                    cat,
                    "Remote",
                    WARN,
                    "not hosted on " + git_server,
                    f"Team standard: host the repository on {git_server}.",
                )
            )
        else:
            checks.append(Check(cat, "Remote", PASS))
    gitignore = project.text(".gitignore")
    if not gitignore:
        checks.append(
            Check(cat, ".gitignore", WARN, "missing", "Add one; it must exclude .env files.")
        )
    elif not _ignores_env(gitignore):
        checks.append(
            Check(
                cat,
                ".gitignore",
                WARN,
                ".env is not ignored",
                "Add '.env' and '.env.*' (with '!.env.example').",
            )
        )
    else:
        checks.append(Check(cat, ".gitignore", PASS, "excludes .env"))
    return checks


def _find_git_dir(root: Path) -> Path | None:
    """The project's own ``.git`` or, for monorepos, the closest parent's."""
    for directory in (root, *root.parents):
        if (directory / ".git").exists():
            return directory / ".git"
    return None


def _git_remotes(config_path: Path) -> list[str]:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        parser.read(config_path, encoding="utf-8")
    except (configparser.Error, OSError):
        return []
    return [parser[s].get("url", "") for s in parser.sections() if s.startswith("remote ")]


def _ignores_env(gitignore: str) -> bool:
    patterns = {line.strip() for line in gitignore.splitlines()}
    return bool(patterns & {".env", "/.env", ".env*", "*.env", "**/.env", ".env.*"})


# --- Quality --------------------------------------------------------------------------------
def _quality(project: _Project) -> list[Check]:
    cat = "Quality"
    pyproject = project.text("pyproject.toml")
    deps = project.npm_dependencies()

    def has(*rels: str) -> bool:
        return any(project.glob(r) for r in rels)

    detections: list[tuple[str, Callable[[], bool], str]] = [
        (
            "Formatter",
            lambda: (
                "[tool.ruff" in pyproject
                or "[tool.black" in pyproject
                or has("ruff.toml", ".ruff.toml", ".prettierrc*", "prettier.config.*")
                or "prettier" in deps
            ),
            "Python: ruff format. JS/TS: prettier.",
        ),
        (
            "Linter",
            lambda: (
                "[tool.ruff" in pyproject
                or "[tool.pylint" in pyproject
                or has(
                    "ruff.toml",
                    ".ruff.toml",
                    ".flake8",
                    ".pylintrc",
                    "eslint.config.*",
                    ".eslintrc*",
                )
                or "eslint" in deps
            ),
            "Python: ruff check. JS/TS: eslint.",
        ),
        (
            "Type checker",
            lambda: (
                "[tool.mypy" in pyproject
                or "[tool.pyright" in pyproject
                or has("mypy.ini", "pyrightconfig.json", "tsconfig.json")
            ),
            "Python: mypy or pyright. JS: TypeScript (tsconfig.json).",
        ),
        (
            "Tests",
            lambda: has(
                "**/test_*.py",
                "**/*_test.py",
                "**/*.spec.ts",
                "**/*.test.ts",
                "**/*.test.tsx",
                "**/*.test.js",
                "**/*.spec.js",
            ),
            "Add a tests/ folder; see .ai/agents/10-testing.md.",
        ),
        (
            "CI pipeline",
            lambda: has(
                ".gitlab-ci.yml",
                ".github/workflows/*.yml",
                ".gitea/workflows/*.yml",
                "Jenkinsfile",
                ".woodpecker.yml",
                ".drone.yml",
            ),
            "Add a pipeline that runs lint, tests and 'ai-project doctor'.",
        ),
    ]
    checks = []
    deployed = _deployment_in_scope(project)
    for name, detect, hint in detections:
        if detect():
            checks.append(Check(cat, name, PASS))
        elif name == "CI pipeline" and not deployed:
            checks.append(Check(cat, name, INFO, "not configured (deployment not in scope)"))
        else:
            checks.append(Check(cat, name, WARN, "not configured", hint))
    return checks


def _deployment_in_scope(project: _Project) -> bool:
    """Deployment scope from the lock file; projects without one are treated as deployed."""
    try:
        lock = read_lock(project.root)
    except KitError:
        return True
    if lock is None:
        return True
    return deployment_in_scope(str(lock.selection.get("deployment", "")))


def _code_comments(project: _Project) -> list[Check]:
    """CODE-45 to CODE-47: comments in English that describe current behaviour (heuristic)."""
    cat = "Quality"
    name = "Code comments (English, current behaviour)"
    findings, files = scan_comments(project.root)
    if files == 0:
        return [Check(cat, name, INFO, "no source files")]
    if not findings:
        return [Check(cat, name, PASS, f"{files} file(s)")]
    sample = ", ".join(f"{f.path}:{f.line} ({f.kind})" for f in findings[:5])
    more = f" and {len(findings) - 5} more" if len(findings) > 5 else ""
    return [
        Check(
            cat,
            name,
            WARN,
            f"{len(findings)} comment(s) to review: {sample}{more}",
            "Write comments in English describing current behaviour; change history belongs in "
            "CHANGELOG.md or an ADR (CODE-45-47). Mark a deliberate exception with "
            "'ai-kit: allow-comment'.",
        )
    ]


# --- Security configuration (secrets handled separately) ------------------------------------
def _security_config(project: _Project) -> list[Check]:
    cat = "Security"
    checks = []
    manifests = {
        "pyproject.toml": (
            "uv.lock",
            "poetry.lock",
            "pdm.lock",
            "requirements.txt",
            "requirements.lock",
        ),
        "requirements.in": ("requirements.txt",),
        "package.json": ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"),
    }
    for manifest, locks in manifests.items():
        if project.exists(manifest):
            if project.exists(*locks):
                checks.append(Check(cat, f"Dependency lock ({manifest})", PASS))
            else:
                checks.append(
                    Check(
                        cat,
                        f"Dependency lock ({manifest})",
                        WARN,
                        "no lock file",
                        "Pin dependencies with a lock file for reproducible builds.",
                    )
                )
    for dockerfile in project.glob("**/Dockerfile"):
        rel = dockerfile.relative_to(project.root).as_posix()
        content = dockerfile.read_text(encoding="utf-8", errors="replace")
        users = re.findall(r"(?im)^\s*USER\s+(\S+)", content)
        if not users or users[-1] in ("root", "0"):
            checks.append(
                Check(
                    cat,
                    f"Non-root container ({rel})",
                    WARN,
                    "runs as root",
                    "Add a non-root USER (see .ai/stacks/docker/README.md).",
                )
            )
        else:
            checks.append(Check(cat, f"Non-root container ({rel})", PASS))
    return checks


def _secret_checks(findings: list[Finding], contact: str) -> list[Check]:
    cat = "Security"
    code = [f for f in findings if not f.in_env_file]
    env = [f for f in findings if f.in_env_file]
    checks = []
    if code:
        where = ", ".join(f"{f.path}:{f.line} ({f.kind})" for f in code[:5])
        checks.append(
            Check(
                cat,
                "No secrets in source",
                FAIL,
                f"{len(code)} finding(s): {where}",
                "Remove, ROTATE the credential and purge it from Git history.",
            )
        )
    else:
        checks.append(Check(cat, "No obvious exposed secrets in source", PASS))
    if env:
        files = sorted({f.path for f in env})
        checks.append(
            Check(
                cat,
                "Credentials in .env files",
                WARN,
                f"{len(env)} credential(s) in {', '.join(files)}",
                "Move them to Kubernetes Secrets / a vault / CI masked variables"
                + (f" and report to {contact}." if contact else "."),
            )
        )
    return checks


# --- Documentation ----------------------------------------------------------------------
def _documentation(project: _Project) -> list[Check]:
    cat = "Documentation"
    checks = []
    readme = project.text("README.md")
    if len([line for line in readme.splitlines() if line.strip()]) >= 5:
        checks.append(Check(cat, "README", PASS))
    else:
        checks.append(
            Check(
                cat,
                "README",
                FAIL if not readme else WARN,
                "missing" if not readme else "too short",
                "Explain purpose, setup, usage, tests and deployment.",
            )
        )
    arch = project.glob("docs/architecture/*.md")
    checks.append(
        Check(cat, "Architecture", PASS)
        if arch
        else Check(
            cat,
            "Architecture",
            WARN,
            "docs/architecture/ empty",
            "Describe the architecture (see .ai/agents/11-documentation.md).",
        )
    )
    docs = [*project.glob("docs/**/*.md"), project.path("README.md")]
    mermaid = any(
        "```mermaid" in p.read_text("utf-8", errors="replace") for p in docs if p.is_file()
    )
    checks.append(
        Check(cat, "Diagrams (Mermaid)", PASS)
        if mermaid
        else Check(cat, "Diagrams (Mermaid)", WARN, "none found", "Add at least a system diagram.")
    )
    adrs = [p for p in project.glob("docs/adr/*.md") if re.match(r"^\d{4}-", p.name)]
    checks.append(
        Check(cat, "ADRs", PASS, f"{len(adrs)} decision(s)")
        if adrs
        else Check(
            cat, "ADRs", WARN, "no docs/adr/NNNN-*.md", "Record architecture decisions as ADRs."
        )
    )
    return checks


# --- Environment ------------------------------------------------------------------------
def _environment(project: _Project) -> list[Check]:
    cat = "Environment"
    env_files = [rel for rel in project.files() if is_env_file(rel.split("/")[-1])]
    checks = [
        _exists_check(
            project,
            cat,
            ".env.example",
            (".env.example",),
            WARN,
            "Document every setting with placeholder values only.",
        ),
    ]
    if env_files:
        checks.append(
            Check(
                cat,
                "Local .env files",
                INFO,
                ", ".join(env_files[:5]),
                "Never commit them; prefer injected secrets.",
            )
        )
    checks.append(
        _exists_check(
            project,
            cat,
            ".editorconfig",
            (".editorconfig",),
            INFO,
            "Optional: consistent whitespace across editors.",
        )
    )
    return checks


# --- Output ---------------------------------------------------------------------------------
def print_report(report: Report, console: Console, contact: str = "") -> None:
    console.title("AI SOFTWARE ENGINEERING CHECK")
    console.print(f"Project: {report.root}")
    current = None
    for check in report.checks:
        if check.category != current:
            current = check.category
            console.section(current)
        console.status(check.status, check.name, check.detail)
        if check.hint and check.status in (WARN, FAIL):
            console.print(console.style(f"    -> {check.hint}", "dim"))
    if report.env_secrets:
        console.print()
        print_env_alert(console, sorted({f.path for f in report.env_secrets}), contact)
    console.print()
    counts = {s: sum(c.status == s for c in report.checks) for s in (PASS, WARN, FAIL)}
    console.print(f"{counts[PASS]} passed, {counts[WARN]} warning(s), {counts[FAIL]} failure(s)")
    console.print(console.style(f"Result: {report.result}", report.result))


def print_env_alert(console: Console, files: list[str], contact: str) -> None:
    """The team policy requires a clear, dissuasive warning - without blocking."""
    lines = [
        "SECURITY WARNING - REAL CREDENTIALS FOUND IN .env FILES",
        "",
        "Files: " + ", ".join(files),
        "",
        "Plain-text credentials in .env files leak through backups, shared folders,",
        "Docker build contexts, screenshots, logs and accidental commits.",
        "Treat every credential stored this way as ALREADY COMPROMISED.",
        "",
        "Do this now:",
        "  1. Move secrets to Kubernetes Secrets (Sealed Secrets / External Secrets),",
        "     a vault (e.g. HashiCorp Vault) or CI/CD masked + protected variables.",
        "  2. Rotate the exposed credentials.",
        "  3. Keep only placeholders in .env.example; keep .env in .gitignore.",
    ]
    if contact:
        lines.append(f"  4. Report the exposure to the security contact: {contact}")
    lines += ["", "See .ai/rules/security.md and .ai/agents/09-security.md."]
    console.banner(lines, WARN)
