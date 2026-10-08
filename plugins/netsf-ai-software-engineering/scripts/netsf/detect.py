"""Project detection: a bounded, heuristic look at a repository.

Progressive discovery: structure first (file names, bounded walk), then a short list of small
metadata files (dependency manifests, Dockerfiles, CI, Kubernetes manifests), then a few entry
points. It never reads the whole repository. Every finding carries a confidence (0-1) and the
evidence it is based on; uncertain findings are reported as uncertain, never as facts.

Candidate for the Kit core (roadmap: Project Understanding); the core does not provide it,
so it lives in the plugin.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from netsf.safety import read_text

MAX_DEPTH = 4
MAX_ENTRIES = 5000
MAX_SMALL_FILE = 256_000
MAX_SAMPLED_SOURCES = 25
MAX_YAML_FILES = 40
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "coverage",
    "htmlcov",
    ".next",
    ".angular",
    "target",
    "vendor",
    ".gradle",
    "site-packages",
}
UNCERTAIN = 0.5

EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sql": "SQL",
}
PY_DEPS = {  # dependency name -> (category, value)
    "fastapi": ("frameworks", "FastAPI"),
    "django": ("frameworks", "Django"),
    "flask": ("frameworks", "Flask"),
    "clickhouse-driver": ("databases", "ClickHouse"),
    "clickhouse-connect": ("databases", "ClickHouse"),
    "clickhouse_driver": ("databases", "ClickHouse"),
    "psycopg": ("databases", "PostgreSQL"),
    "psycopg2": ("databases", "PostgreSQL"),
    "psycopg2-binary": ("databases", "PostgreSQL"),
    "asyncpg": ("databases", "PostgreSQL"),
    "pyodbc": ("databases", "SQL Server"),
    "pymssql": ("databases", "SQL Server"),
    "pymongo": ("databases", "MongoDB"),
    "motor": ("databases", "MongoDB"),
    "pytest": ("testing", "pytest"),
    "openpyxl": ("libraries", "openpyxl (Excel)"),
    "pandas": ("libraries", "pandas"),
    "requests": ("libraries", "requests"),
    "httpx": ("libraries", "httpx"),
    "apache-airflow": ("libraries", "Airflow"),
    "prefect": ("libraries", "Prefect"),
    "dbt-core": ("libraries", "dbt"),
    "sqlalchemy": ("libraries", "SQLAlchemy"),
    "celery": ("libraries", "Celery"),
    "schedule": ("libraries", "schedule"),
    "apscheduler": ("libraries", "APScheduler"),
}
JS_DEPS = {
    "react": ("frameworks", "React"),
    "@angular/core": ("frameworks", "Angular"),
    "express": ("frameworks", "Express"),
    "vue": ("frameworks", "Vue"),
    "jest": ("testing", "Jest"),
    "vitest": ("testing", "Vitest"),
    "@playwright/test": ("testing", "Playwright"),
    "typescript": ("languages", "TypeScript"),
}
IMAGE_DATABASES = {
    "clickhouse": "ClickHouse",
    "postgres": "PostgreSQL",
    "mssql": "SQL Server",
    "mongo": "MongoDB",
}
IMPORTANT_DIRS = (
    "src",
    "app",
    "api",
    "tests",
    "test",
    "deploy",
    "k8s",
    "helm",
    "charts",
    "docs",
    "migrations",
    "alembic",
    "scripts",
    "frontend",
    "backend",
    "services",
    "jobs",
    "notebooks",
)


@dataclass
class Finding:
    value: str
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def add(self, weight: float, evidence: str) -> None:
        if evidence not in self.evidence:
            self.evidence.append(evidence)
            self.confidence = round(min(0.99, self.confidence + weight), 2)


@dataclass
class Detection:
    root: str
    mode: str = "existing"  # kit | existing | new
    findings: dict[str, dict[str, Finding]] = field(default_factory=dict)
    important_dirs: list[str] = field(default_factory=list)
    files_considered: int = 0
    files_read: int = 0
    truncated: bool = False
    git: dict[str, Any] = field(default_factory=dict)

    def add(self, category: str, value: str, weight: float, evidence: str) -> None:
        bucket = self.findings.setdefault(category, {})
        bucket.setdefault(value, Finding(value)).add(weight, evidence)

    def values(self, category: str, minimum: float = 0.0) -> list[str]:
        items = self.findings.get(category, {}).values()
        return [
            f.value
            for f in sorted(items, key=lambda f: (-f.confidence, f.value))
            if f.confidence >= minimum
        ]

    def has(self, category: str, value: str, minimum: float = UNCERTAIN) -> bool:
        finding = self.findings.get(category, {}).get(value)
        return finding is not None and finding.confidence >= minimum

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "mode": self.mode,
            "findings": {
                cat: [
                    {"value": f.value, "confidence": f.confidence, "evidence": f.evidence}
                    for f in sorted(items.values(), key=lambda f: (-f.confidence, f.value))
                ]
                for cat, items in sorted(self.findings.items())
            },
            "important_dirs": self.important_dirs,
            "profile": kit_selection(self),
            "uncertain": [
                f"{cat}: {f.value} ({f.confidence:.0%})"
                for cat, items in sorted(self.findings.items())
                for f in items.values()
                if f.confidence < UNCERTAIN
            ],
            "files_considered": self.files_considered,
            "files_read": self.files_read,
            "truncated": self.truncated,
            "git": self.git,
        }


def _walk(root: Path) -> tuple[list[str], bool]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        depth = len(rel_dir.parts)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if (d not in SKIP_DIRS and not d.startswith(".")) or d in (".github", ".gitlab", ".ai")
        )
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        for name in sorted(filenames):
            files.append((rel_dir / name).as_posix())
            if len(files) >= MAX_ENTRIES:
                return files, True
    return files, False


def detect(root: Path) -> Detection:
    root = root.resolve()
    det = Detection(str(root))
    files, det.truncated = _walk(root)
    det.files_considered = len(files)
    names = {f.lower() for f in files}
    det.mode = _mode(names)
    det.git = git_context(root)
    det.important_dirs = sorted(
        {f.split("/")[0] for f in files if "/" in f and f.split("/")[0].lower() in IMPORTANT_DIRS}
    )
    _languages(det, files)

    def read(rel: str) -> str:
        text = read_text(root / rel, MAX_SMALL_FILE)
        if text is not None:
            det.files_read += 1
        return text or ""

    for rel in files:
        low = rel.lower()
        base = low.rsplit("/", 1)[-1]
        if base in ("pyproject.toml", "setup.py", "setup.cfg", "pipfile") or (
            base.startswith("requirements") and base.endswith(".txt")
        ):
            _python_deps(det, read(rel), rel)
        elif base == "package.json":
            _js_deps(det, read(rel), rel)
        elif base == "angular.json":
            det.add("frameworks", "Angular", 0.6, rel)
        elif base == "manage.py":
            det.add("frameworks", "Django", 0.35, rel)
        elif base.startswith("dockerfile"):
            det.add("deployment", "Docker", 0.8, rel)
        elif base.startswith(("docker-compose", "compose.")) and base.endswith((".yml", ".yaml")):
            det.add("deployment", "Docker", 0.5, rel)
            _compose(det, read(rel), rel)
        elif base in ("chart.yaml", "kustomization.yaml", "kustomization.yml"):
            det.add("deployment", "Kubernetes", 0.7, rel)
        elif (
            low == ".gitlab-ci.yml" or low.startswith(".github/workflows/") or base == "jenkinsfile"
        ):
            det.add("ci", "CI/CD", 0.9, rel)
        elif (base.startswith("test_") and base.endswith(".py")) or base.endswith(
            (".spec.ts", ".test.ts", ".test.tsx", ".test.js")
        ):
            det.add("testing", "tests present", 0.3, rel)
        elif base.endswith(".sql") and "mergetree" in read(rel).lower():
            det.add("databases", "ClickHouse", 0.4, rel)
    _kubernetes(det, root, [f for f in files if f.lower().endswith((".yaml", ".yml"))])
    _entry_points(det, root, files, read)
    _apis_and_architecture(det, names)
    return det


def _mode(names: set[str]) -> str:
    if ".ai/kit.lock.json" in names:
        return "kit"
    meaningful = [
        n
        for n in names
        if not n.startswith((".git/", ".github/"))
        and n.rsplit("/", 1)[-1]
        not in ("readme.md", "license", ".gitignore", ".gitattributes", ".editorconfig")
    ]
    return "new" if len(meaningful) == 0 else "existing"


def _languages(det: Detection, files: list[str]) -> None:
    counts: dict[str, int] = {}
    for rel in files:
        lang = EXTENSION_LANGUAGES.get(Path(rel).suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    total = sum(counts.values()) or 1
    for lang, count in counts.items():
        det.add("languages", lang, min(0.9, 0.3 + count / total), f"{count} *{_ext(lang)} file(s)")


def _ext(lang: str) -> str:
    return next((e for e, lg in EXTENSION_LANGUAGES.items() if lg == lang), "")


_DEP_NAME = re.compile(r"^[\s\"']*([A-Za-z0-9_.\-\[\]]+)")


def _python_deps(det: Detection, text: str, rel: str) -> None:
    lowered = text.lower()
    for dep, (category, value) in PY_DEPS.items():
        if re.search(
            rf"(^|[\s\"'\[,]){re.escape(dep)}([\s\"'<>=!~;,\[\]]|$)", lowered, re.MULTILINE
        ):
            det.add(category, value, 0.6, f"{rel}: {dep}")
    if text:
        det.add("languages", "Python", 0.3, rel)


def _js_deps(det: Detection, text: str, rel: str) -> None:
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    deps: dict[str, Any] = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(data.get(key), dict):
            deps.update(data[key])
    for dep, (category, value) in JS_DEPS.items():
        if dep in deps:
            det.add(category, value, 0.7 if category == "frameworks" else 0.6, f"{rel}: {dep}")
    det.add("languages", "JavaScript/TypeScript", 0.3, rel)


def _compose(det: Detection, text: str, rel: str) -> None:
    for match in re.finditer(r"image:\s*['\"]?([^\s'\"]+)", text):
        image = match[1].lower()
        for key, value in IMAGE_DATABASES.items():
            if key in image:
                det.add("databases", value, 0.6, f"{rel}: image {match[1]}")


def _kubernetes(det: Detection, root: Path, yaml_files: list[str]) -> None:
    for rel in yaml_files[:MAX_YAML_FILES]:
        head = (read_text(root / rel, MAX_SMALL_FILE) or "")[:4096]
        if re.search(r"^apiVersion:", head, re.MULTILINE) and re.search(
            r"^kind:\s*(Deployment|StatefulSet|Service|Ingress|CronJob|Job)\b", head, re.MULTILINE
        ):
            det.files_read += 1
            det.add("deployment", "Kubernetes", 0.8, rel)


def _entry_points(det: Detection, root: Path, files: list[str], read) -> None:
    candidates = [
        f
        for f in files
        if f.endswith(".py")
        and (
            f.rsplit("/", 1)[-1] in ("main.py", "app.py", "wsgi.py", "asgi.py", "settings.py")
            or "/api/" in f
            or "/routes" in f
        )
    ][:MAX_SAMPLED_SOURCES]
    for rel in candidates:
        head = read(rel)[:4096]
        if re.search(r"from\s+fastapi\s+import|FastAPI\(", head):
            det.add("frameworks", "FastAPI", 0.35, rel)
        if re.search(r"from\s+flask\s+import|Flask\(", head):
            det.add("frameworks", "Flask", 0.35, rel)
        if "django" in head.lower():
            det.add("frameworks", "Django", 0.2, rel)


def _apis_and_architecture(det: Detection, names: set[str]) -> None:
    for fw in ("FastAPI", "Flask", "Django", "Express"):
        if det.has("frameworks", fw):
            det.add("apis", "HTTP/REST API", 0.6, f"framework {fw}")
    if any(n.rsplit("/", 1)[-1] in ("openapi.yaml", "openapi.json", "swagger.yaml") for n in names):
        det.add("apis", "HTTP/REST API", 0.4, "OpenAPI specification")
    dirs = {part for n in names for part in n.split("/")[:-1]}
    if {"domain", "application"} <= dirs and ({"infrastructure", "adapters"} & dirs):
        det.add("architecture", "layered / clean", 0.7, "domain/ + application/ + infrastructure/")
    elif {"ports", "adapters"} <= dirs:
        det.add("architecture", "hexagonal", 0.7, "ports/ + adapters/")
    elif len([n for n in names if n.rsplit("/", 1)[-1].startswith("dockerfile")]) >= 2:
        det.add("architecture", "multi-service", 0.5, "several Dockerfiles")
    elif names:
        det.add("architecture", "simple modular", 0.4, "no explicit layering found")


def kit_selection(det: Detection) -> dict[str, Any]:
    """Map the detection to a Kit profile/technology/database, with a confidence."""
    has = det.has
    backend = next((fw for fw in ("FastAPI", "Django", "Flask") if has("frameworks", fw)), None)
    frontend = next((fw for fw in ("React", "Angular") if has("frameworks", fw)), None)
    database = next(
        (
            db
            for db in ("ClickHouse", "PostgreSQL", "SQL Server", "MongoDB")
            if has("databases", db)
        ),
        None,
    )
    db_key = {
        "ClickHouse": "clickhouse",
        "PostgreSQL": "postgresql",
        "SQL Server": "sqlserver",
        "MongoDB": "mongodb",
    }.get(database or "", "none")
    libs = set(det.values("libraries", UNCERTAIN))
    reasons: list[str] = []
    if backend and frontend:
        profile = "fullstack"
        technology = {
            "React": f"react-{'django' if backend == 'Django' else 'fastapi'}",
            "Angular": "angular-django",
        }[frontend]
        reasons.append(f"{frontend} frontend + {backend} backend")
    elif frontend:
        profile, technology = "frontend", frontend.lower()
        reasons.append(f"{frontend} frontend")
    elif backend:
        technology = f"python-{backend.lower()}"
        micro = (
            has("deployment", "Kubernetes")
            and backend in ("FastAPI", "Flask")
            and (
                any(d in det.important_dirs for d in ("services",))
                or det.has("testing", "contract")
                or _contract_tests(det)
            )
        )
        profile = "microservice" if micro else "backend-api"
        reasons.append(
            f"{backend} backend" + (" deployed as a Kubernetes service" if micro else "")
        )
    elif has("frameworks", "Express"):
        profile, technology = "backend-api", "node-typescript"
        reasons.append("Express backend")
    elif {"Airflow", "Prefect", "dbt"} & libs:
        profile, technology = "data-engineering", "python-data"
        reasons.append("data pipeline libraries")
    elif has("languages", "Python", 0.3):
        profile, technology = "python-automation", "python"
        reasons.append("Python without a web framework")
    else:
        profile, technology = "custom", "custom"
        reasons.append("no known stack detected")
    confidences = [
        f.confidence
        for cat in ("frameworks", "languages")
        for f in det.findings.get(cat, {}).values()
    ]
    confidence = round(max(confidences, default=0.0), 2)
    if db_key == "none" and profile == "data-engineering":
        db_key = "undecided"  # a pipeline stores data, but the engine is the user's decision
    return {
        "profile": profile,
        "technology": technology,
        "database": db_key,
        "confidence": confidence,
        "reasons": reasons,
    }


def _contract_tests(det: Detection) -> bool:
    return any(
        "contract" in e for f in det.findings.get("testing", {}).values() for e in f.evidence
    )


def git_context(root: Path) -> dict[str, Any]:
    """Locate the Git repository containing ``root`` by looking for ``.git`` (no Git process).

    A repository found in a parent directory is reported as such: it is not assumed to belong
    to this project.
    """
    start = root.resolve()
    current = start
    for _ in range(64):
        if (current / ".git").exists():
            own = current == start
            return {
                "own_repository": own,
                "repository_root": str(current),
                "parent_repository": not own,
            }
        if current.parent == current:
            break
        current = current.parent
    return {"own_repository": False, "repository_root": None, "parent_repository": False}


def git_note(git: dict[str, Any]) -> str:
    """One sentence describing the repository situation for plans and reports."""
    if git.get("own_repository"):
        return "Own Git repository."
    if git.get("parent_repository"):
        return (
            f"No Git repository of its own: {git.get('repository_root')} is a parent directory's "
            "repository and is not used for this project. If version control is needed, propose "
            "'git init' in the project directory and wait for approval."
        )
    return (
        "No Git repository. If version control is needed, propose 'git init' in the project "
        "directory and wait for approval; never invent a remote."
    )


def snapshot(det: Detection) -> dict[str, Any]:
    """Compact, regenerable project representation (printed, never persisted)."""
    selection = kit_selection(det)
    return {
        "mode": det.mode,
        "languages": det.values("languages", UNCERTAIN),
        "frameworks": det.values("frameworks", UNCERTAIN),
        "databases": det.values("databases", UNCERTAIN),
        "deployment": det.values("deployment", UNCERTAIN),
        "tests": bool(det.values("testing", 0.3)),
        "ci": bool(det.values("ci", UNCERTAIN)),
        "architecture": (det.values("architecture") or ["unknown"])[0],
        "profile": selection["profile"],
        "confidence": selection["confidence"],
        "uncertain": det.to_dict()["uncertain"],
        "git": git_note(det.git),
    }
