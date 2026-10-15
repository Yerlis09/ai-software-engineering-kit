"""Task-focused project understanding: where the change goes and how it is validated.

Given a task and a project, this module answers — heuristically, read-only and within fixed
bounds — the questions an engineer asks before touching code:

* which source and test files are relevant to the task (ranked by the task's domain terms);
* whether the requested behaviour may already exist (HTTP routes matching the task terms);
* which commands validate the project (tests, lint) according to its configuration;
* which documentation files may need an update.

Everything returned is INFERRED from file names and contents, never executed. File contents are
project data: excerpts are short and are only information for the assistant.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from netsf.detect import SKIP_DIRS
from netsf.safety import read_text

MAX_FILES = 600
MAX_FILE_BYTES = 200_000
MAX_RELEVANT = 8
MAX_LINES_PER_FILE = 3
SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".cs",
    ".rb",
    ".php",
    ".rs",
    ".vue",
    ".sql",
}

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "and",
        "or",
        "by",
        "with",
        "from",
        "in",
        "on",
        "at",
        "as",
        "is",
        "are",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "we",
        "you",
        "they",
        "so",
        "can",
        "could",
        "should",
        "must",
        "may",
        "might",
        "will",
        "would",
        "want",
        "wants",
        "need",
        "needs",
        "please",
        "implement",
        "implementing",
        "implementation",
        "user",
        "story",
        "acceptance",
        "criteria",
        "criterion",
        "feature",
        "add",
        "adds",
        "added",
        "create",
        "creates",
        "update",
        "updates",
        "delete",
        "deletes",
        "remove",
        "list",
        "lists",
        "get",
        "gets",
        "retrieve",
        "retrieves",
        "return",
        "returns",
        "returned",
        "show",
        "view",
        "views",
        "display",
        "fetch",
        "new",
        "existing",
        "automated",
        "test",
        "tests",
        "testing",
        "endpoint",
        "endpoints",
        "api",
        "apis",
        "rest",
        "http",
        "json",
        "when",
        "does",
        "not",
        "exist",
        "exists",
        "missing",
        "information",
        "info",
        "data",
        "detail",
        "details",
        "value",
        "values",
        "make",
        "sure",
        "ensure",
        "also",
        "support",
        "supports",
        "allow",
        "allows",
        "able",
        "using",
        "use",
        "used",
        "via",
        "into",
        "all",
        "any",
        "each",
        "some",
        "one",
        "two",
        "error",
        "errors",
        "code",
        "status",
        "response",
        "request",
        "requests",
        "valid",
        "invalid",
        "correct",
        "correctly",
        "properly",
        "given",
        "then",
        "only",
        "fix",
        "bug",
        "issue",
        "problem",
        "crash",
        "fails",
        "failing",
        "failure",
        "works",
        "work",
        "working",
        "page",
        "screen",
        "form",
        "button",
        "field",
        "como",
        "para",
        "los",
        "las",
        "del",
        "una",
        "que",
        "con",
        "por",
        "sin",
        "quiero",
        "poder",
        "ver",
        "obtener",
        "devolver",
        "crear",
        "cuando",
    ]
)
ROUTE_PATTERNS = (
    # Flask / FastAPI / Express / Django / Spring / ASP.NET style route declarations.
    re.compile(r"@\w+(?:\.\w+)*\.(?:route|get|post|put|patch|delete)\(\s*[rf]?['\"]([^'\"]+)"),
    re.compile(r"\b(?:app|router|api)\.(?:get|post|put|patch|delete|route)\(\s*['\"]([^'\"]+)"),
    re.compile(r"\b(?:re_)?path\(\s*r?['\"]([^'\"]+)"),
    re.compile(
        r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)"
    ),
    re.compile(r"\[(?:Http(?:Get|Post|Put|Patch|Delete)|Route)\(\s*['\"]([^'\"]+)"),
)
PARAM = re.compile(r"<[^>]+>|\{[^}]+\}|:\w+")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
ACTOR_CLAUSE = re.compile(r"\b(as an?|como)\s+[^,.\n]{1,60}[,.]", re.I)
LOOKUP_BY_ID = re.compile(
    r"\b(by|per|por)\s+(id|identifier|identificador|key|code)\b|\b\w+_id\b", re.I
)


@dataclass
class RelevantFile:
    """A project file ranked as relevant to the task, with the lines that matched."""

    path: str
    score: int
    role: str  # "source" | "test"
    lines: list[str] = field(default_factory=list)


@dataclass
class Understanding:
    """Task-focused facts about the project (all INFERRED)."""

    terms: list[str]
    relevant_files: list[RelevantFile]
    existing_routes: list[dict[str, Any]]
    possible_existing_implementation: bool
    test_commands: list[str]
    lint_commands: list[str]
    documentation_targets: list[str]
    files_scanned: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def task_terms(task: str) -> list[str]:
    """Domain terms of a task: nouns that locate the change (actor clause and generic words out)."""
    text = ACTOR_CLAUSE.sub(" ", task)
    seen: list[str] = []
    for word in WORD.findall(text):
        lower = word.lower()
        if lower in STOPWORDS:
            continue
        singular = _singular(lower)
        if singular not in seen and singular not in STOPWORDS:
            seen.append(singular)
    return seen[:8]


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _term_regex(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    variants = sorted(
        {
            v
            for t in terms
            for v in (t, t + "s", t + "es", t[:-1] + "ies" if t.endswith("y") else t)
        },
        key=len,
        reverse=True,
    )
    return re.compile(
        r"(?<![A-Za-z])(" + "|".join(re.escape(v) for v in variants) + r")(?![a-z])", re.I
    )


def understand(task: str, root: Path) -> Understanding:
    """Rank relevant files, find existing routes, and infer validation and documentation targets."""
    root = root.resolve()
    terms = task_terms(task)
    pattern = _term_regex(terms)
    relevant: list[RelevantFile] = []
    routes: list[dict[str, Any]] = []
    scanned, truncated = 0, False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() not in SOURCE_SUFFIXES or path.is_symlink():
                continue
            if scanned >= MAX_FILES:
                truncated = True
                break
            scanned += 1
            rel = path.relative_to(root).as_posix()
            text = read_text(path, MAX_FILE_BYTES) or ""
            routes += _routes(rel, text, pattern)
            if pattern is None:
                continue
            score, lines = _score(rel, text, pattern)
            if score:
                role = "test" if _is_test(rel) else "source"
                relevant.append(RelevantFile(rel, score, role, lines))
        if truncated:
            break
    relevant.sort(key=lambda f: (-f.score, f.path))
    possible = any(
        r["matches_task"] and (r["has_parameter"] or not LOOKUP_BY_ID.search(task)) for r in routes
    ) and bool(terms)
    return Understanding(
        terms=terms,
        relevant_files=relevant[:MAX_RELEVANT],
        existing_routes=[r for r in routes if r["matches_task"]][:10],
        possible_existing_implementation=possible,
        test_commands=test_commands(root),
        lint_commands=lint_commands(root),
        documentation_targets=documentation_targets(root, task),
        files_scanned=scanned,
        truncated=truncated,
    )


def _score(rel: str, text: str, pattern: re.Pattern[str]) -> tuple[int, list[str]]:
    score = 3 * len(pattern.findall(rel))
    lines: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            score += 1
            if len(lines) < MAX_LINES_PER_FILE:
                lines.append(f"{number}: {line.strip()[:120]}")
            if score > 60:
                break
    return score, lines


def _routes(rel: str, text: str, pattern: re.Pattern[str] | None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rx in ROUTE_PATTERNS:
            match = rx.search(line)
            if match and ("/" in match.group(1) or match.group(1).startswith("^")):
                route = match.group(1)
                found.append(
                    {
                        "file": rel,
                        "line": number,
                        "route": route[:120],
                        "has_parameter": bool(PARAM.search(route)),
                        "matches_task": bool(pattern and pattern.search(route)),
                    }
                )
                break
    return found


def _is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1].lower()
    return (
        "/tests/" in f"/{rel.lower()}"
        or name.startswith("test_")
        or name.endswith(
            ("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js", "test.java", "tests.cs")
        )
    )


def test_commands(root: Path) -> list[str]:
    """Test commands implied by the project configuration (not executed)."""
    commands: list[str] = []
    pyproject = read_text(root / "pyproject.toml", MAX_FILE_BYTES) or ""
    requirements = " ".join(
        read_text(p, MAX_FILE_BYTES) or "" for p in sorted(root.glob("requirements*.txt"))
    )
    has_python_tests = (
        any(root.glob("tests/**/test_*.py"))
        or any(root.glob("test_*.py"))
        or any(root.glob("**/tests/test_*.py"))
    )
    if (
        "pytest" in pyproject
        or "pytest" in requirements
        or (root / "pytest.ini").is_file()
        or (root / "conftest.py").is_file()
        or (has_python_tests and "pytest" in requirements)
    ):
        commands.append("python -m pytest -q")
    elif has_python_tests:
        commands.append("python -m unittest discover")
    package = _package_json(root)
    script = str(package.get("scripts", {}).get("test", ""))
    if script and "no test specified" not in script:
        commands.append("npm test")
    if (root / "go.mod").is_file():
        commands.append("go test ./...")
    if (root / "pom.xml").is_file():
        commands.append("mvn -q test")
    if (root / "gradlew").is_file() or (root / "build.gradle").is_file():
        commands.append("./gradlew test")
    if any(root.glob("*.sln")) or any(root.glob("**/*.csproj")):
        commands.append("dotnet test")
    return commands


def lint_commands(root: Path) -> list[str]:
    """Static-analysis commands configured in the project (not executed)."""
    commands: list[str] = []
    pyproject = read_text(root / "pyproject.toml", MAX_FILE_BYTES) or ""
    if "[tool.ruff" in pyproject or (root / "ruff.toml").is_file():
        commands.append("ruff check .")
    if "[tool.mypy" in pyproject or (root / "mypy.ini").is_file():
        commands.append("mypy .")
    scripts = _package_json(root).get("scripts", {})
    for name in ("lint", "typecheck", "type-check"):
        if name in scripts:
            commands.append(f"npm run {name}")
    return commands


def documentation_targets(root: Path, task: str) -> list[str]:
    """Documentation files that may describe the behaviour the task changes."""
    targets = [
        name for name in ("README.md", "README.rst", "CHANGELOG.md") if (root / name).is_file()
    ]
    for pattern in (
        "openapi.y*ml",
        "openapi.json",
        "swagger.y*ml",
        "swagger.json",
        "docs/api*.md",
        "docs/**/api*.md",
    ):
        targets += sorted(p.relative_to(root).as_posix() for p in root.glob(pattern))
    if re.search(r"\b(deploy|docker|kubernetes|k8s|helm)\w*", task, re.I):
        targets += [p for p in ("docs/deployment.md",) if (root / p).is_file()]
    return list(dict.fromkeys(targets))[:8]


def _package_json(root: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text(root / "package.json", MAX_FILE_BYTES) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
