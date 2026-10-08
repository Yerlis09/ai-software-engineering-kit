"""Deterministic scope signals derived from the user's request.

The signals tell the assistant what the request implies before any design work:

* **database** — a database named in the request is used as is; persistence that is needed
  but unnamed means *ask the user* (the organisation default, ClickHouse, is only a
  recommendation); a file-only workflow or an explicit "no database" means no database.
* **deployment** — deployment content (Docker, Kubernetes, NGINX, CI) is in scope only when
  the request asks for it; a missing target environment is a question, never a guess.
* **project type** — for a new or unrecognised project, the Kit profile and technology are
  inferred from the core's task classification, so the user never has to pick them.

These are keyword heuristics: they inform the plan and the routing, and the assistant still
reasons about the full requirements. Rules: ``rules/architecture.md`` ARCH-42 to ARCH-47.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

ORG_DEFAULT_DATABASE = "ClickHouse"

NAMED_DATABASES = (
    ("clickhouse", re.compile(r"\bclick\s*house\b", re.I)),
    ("postgresql", re.compile(r"\bpostgre(s|sql)?\b", re.I)),
    ("sqlserver", re.compile(r"\b(sql\s*server|mssql)\b", re.I)),
    ("mongodb", re.compile(r"\bmongo(db)?\b", re.I)),
    ("custom", re.compile(r"\b(mysql|mariadb|sqlite|oracle\s*db|oracle database|redis)\b", re.I)),
)
NO_PERSISTENCE = re.compile(
    r"\b(no|without( a)?|sin)\s+(database|db|persistence|storage|base de datos|persistencia)\b"
    r"|\b(only|solo|s[oó]lo)\s+(works?\s+)?(with\s+)?(files|archivos|ficheros)\b"
    r"|\bdoes not (need|require) (a )?(database|persistence)\b",
    re.I,
)
PERSISTENCE = re.compile(
    r"\b(store[sd]?|storing|save[sd]?|saving|persist\w*|database|db|records?|history|historical"
    r"|crud|manage[sd]?|managing|management|inventory|track(s|ing)?|register\w*|catalog(ue)?"
    r"|guardar|almacen\w*|base de datos|gestion\w*|gestionar|registr\w*|historial|inventario)\b",
    re.I,
)
FILE_WORKFLOW = re.compile(
    r"\b(excel|xlsx|xls|csv|spreadsheet|pdf|files?|upload\w*|archivos?|ficheros?"
    r"|hoja de c[aá]lculo)\b",
    re.I,
)
# "production" and "staging" alone are domain words (production lines, staging areas): only
# deployment phrasings count.
DEPLOYMENT = re.compile(
    r"\b(deploy\w*|docker\w*|kubernetes|k8s|rke|helm|nginx|uwsgi|ci/?cd|ci pipeline"
    r"|containeri[sz]\w*|despleg\w*|desplieg\w*)\b"
    r"|\b(to|in|into|on) (production|staging|prod)\b"
    r"|\b(production|staging) (environment|cluster|server|release)\b"
    r"|\ben producci[oó]n\b",
    re.I,
)
KUBERNETES = re.compile(r"\b(kubernetes|k8s|rke|helm)\b", re.I)
DOCKER = re.compile(r"\bdocker\w*|\bcontaineri[sz]\w*", re.I)
AUTOMATION = re.compile(
    r"\b(script|automat\w*|cron|scheduled?|batch|report(s|ing)?|excel|xlsx|csv|job)\b", re.I
)
DATA_PIPELINE = re.compile(r"\b(etl|elt|ingest\w*|warehouse|data pipeline|dbt|airflow)\b", re.I)

# Core technology labels (catalog/context.json stacks) mapped to Kit technologies per profile.
BACKEND_TECH = {
    "fastapi": "python-fastapi",
    "django": "python-django",
    "flask": "python-flask",
    "node": "node-typescript",
}
FRONTEND_TECH = {"react": "react", "angular": "angular"}
FULLSTACK_TECH = {"react-fastapi", "react-django", "angular-django"}


@dataclass
class Scope:
    """What the request implies for persistence and deployment."""

    database: str  # "specified" | "ask" | "none" | "not-applicable"
    database_value: str  # Kit database key: clickhouse, postgresql, ..., undecided, none
    database_reason: str
    deployment_in_scope: bool
    deployment_target: str  # Kit deployment key: kubernetes, docker, undecided
    deployment_reason: str
    questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_scope(
    task: str,
    detected_databases: list[str] | None = None,
    detected_deployment: list[str] | None = None,
) -> Scope:
    """Derive the database and deployment scope of a request (and of an existing project)."""
    questions: list[str] = []
    named = next((key for key, rx in NAMED_DATABASES if rx.search(task)), None)
    detected = [d for d in (detected_databases or []) if d]
    if named:
        database, value = "specified", named
        reason = f"the request names the database ({named})"
    elif detected:
        database, value = "specified", _database_key(detected[0])
        reason = f"the project already uses {detected[0]}"
    elif NO_PERSISTENCE.search(task):
        database, value, reason = "none", "none", "the request excludes persistence"
    elif PERSISTENCE.search(task):
        database, value = "ask", "undecided"
        reason = "the request needs persistent data but does not name a database"
        questions.append(
            "The requirements need persistent storage but do not specify the database. "
            f"The organisation default is {ORG_DEFAULT_DATABASE}: should this project use it?"
        )
    elif FILE_WORKFLOW.search(task):
        database, value = "none", "none"
        reason = "file-processing workflow with no persistence requirement: no database"
    else:
        database, value = "not-applicable", "undecided"
        reason = "no persistence requirement in the request"

    deployed = sorted({d for d in (detected_deployment or []) if d in ("Docker", "Kubernetes")})
    if DEPLOYMENT.search(task):
        in_scope = True
        if KUBERNETES.search(task) or "Kubernetes" in deployed:
            target, why = "kubernetes", "Kubernetes (RKE) requested or already used"
        elif DOCKER.search(task) or "Docker" in deployed:
            target, why = "docker", "Docker requested or already used"
        else:
            target, why = "undecided", "deployment requested without a target environment"
            questions.append(
                "Deployment is requested but the target environment is not specified. "
                "The team standard is Docker on Kubernetes (RKE Staging, then Prod): "
                "which environment should it target?"
            )
        deployment_reason = why
    elif deployed:
        in_scope = False
        target = "kubernetes" if "Kubernetes" in deployed else "docker"
        deployment_reason = (
            f"the project already uses {' and '.join(deployed)}; this request does not change "
            "deployment"
        )
    else:
        in_scope, target = False, "undecided"
        deployment_reason = "deployment not requested: no Docker, Kubernetes, NGINX or CI"
    return Scope(database, value, reason, in_scope, target, deployment_reason, questions)


def _database_key(title: str) -> str:
    return {
        "ClickHouse": "clickhouse",
        "PostgreSQL": "postgresql",
        "SQL Server": "sqlserver",
        "MongoDB": "mongodb",
    }.get(title, "custom")


def infer_project(task: str, classification: dict[str, Any]) -> dict[str, Any]:
    """Infer the Kit profile and technology of a new project from the request.

    ``classification`` is the core's ``classification_details`` (categories and technologies
    detected by ``ai-project context``). A framework named in the request is used; otherwise the
    technology is left to the assistant (``custom``) to decide from the requirements.
    """
    categories = set(classification.get("categories", []))
    technologies = list(classification.get("technologies", []))
    frontend = next((FRONTEND_TECH[t] for t in technologies if t in FRONTEND_TECH), None)
    backend = next((BACKEND_TECH[t] for t in technologies if t in BACKEND_TECH), None)
    wants_frontend = bool(frontend) or "frontend" in categories
    wants_backend = bool(backend) or bool({"api", "backend"} & categories)
    reasons: list[str] = []
    if wants_frontend and wants_backend:
        profile = "fullstack"
        pair = f"{frontend}-{backend.split('-', 1)[1]}" if frontend and backend else ""
        technology = pair if pair in FULLSTACK_TECH else "custom"
        reasons.append("the request describes a user interface and a backend/API")
    elif wants_frontend:
        profile, technology = "frontend", frontend or "custom"
        reasons.append("the request describes a user interface")
    elif DATA_PIPELINE.search(task):
        profile, technology = "data-engineering", "python-data"
        reasons.append("the request describes a data pipeline")
    elif wants_backend:
        profile, technology = "backend-api", backend or "custom"
        reasons.append("the request describes an API or backend service")
    elif AUTOMATION.search(task):
        profile, technology = "python-automation", "python"
        reasons.append("the request describes automation, a script or a report")
    else:
        profile, technology = "custom", "custom"
        reasons.append("no project type recognised in the request")
    if technology == "custom" and profile != "custom":
        reasons.append("framework not fixed by the request: the assistant decides it (ARCH-43)")
    return {"profile": profile, "technology": technology, "source": "request", "reasons": reasons}
