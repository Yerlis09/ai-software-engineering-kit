"""Deterministic risk assessment of a task (and optionally of the files it will touch).

LOW < MEDIUM < HIGH < CRITICAL. HIGH and CRITICAL require explicit human approval before any
change. Some intents are BLOCKED outright (secret exfiltration, instruction override): no
approval can unlock them through this plugin. English and Spanish keywords are recognised
because risk detection is a safety control. Unknown tasks default to MEDIUM (conservative).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
APPROVAL_LEVELS = ("HIGH", "CRITICAL")

_PROD = r"(prod\b|production|producci[oó]n|live\b)"
_RULES: list[tuple[str, str, str]] = [
    # (level, regex, reason)
    (
        "BLOCKED",
        r"\b(upload|send|post|exfiltrat\w*|leak|share|sube|subir|env[ií]a\w*)\b.{0,40}"
        r"(\.env\b|secrets?|credentials?|passwords?|api[ _-]?keys?|tokens?|contrase\w*)",
        "sending secrets or credentials outside the project is never allowed",
    ),
    (
        "BLOCKED",
        r"\b(ignore|disregard|forget|ignora\w*)\b.{0,30}\b(previous|prior|all|above|"
        r"anteriores|todas)\b.{0,20}\b(instructions?|rules?|instrucciones|reglas)\b",
        "requests to override safety instructions are refused",
    ),
    (
        "BLOCKED",
        r"\b(read|print|show|dump|reveal|lee\w*|muestra\w*)\b.{0,30}"
        r"(\.env\b|secrets?|credentials?|contrase\w*|private key|id_rsa)",
        "reading or revealing secrets is refused",
    ),
    (
        "CRITICAL",
        rf"\b(deploy\w*|despleg\w*|despliega\w*|release|promote|rollout)\b.{{0,60}}{_PROD}"
        rf"|{_PROD}.{{0,60}}\b(deploy\w*|despleg\w*|despliega\w*)",
        "production deployment",
    ),
    (
        "CRITICAL",
        r"\b(drop|delete|remove|wipe|purge|truncate|borra\w*|elimina\w*|vac[ií]a\w*)\b.{0,40}"
        r"\b(database|databases|db|schema|tables?|base de datos|bases de datos|tablas?)\b",
        "deleting a database, schema or table",
    ),
    (
        "CRITICAL",
        r"\b(delete|remove|borra\w*|elimina\w*)\b.{0,20}\b(all|every|todos?|todas?)\b.{0,20}"
        r"\b(files?|archivos?|ficheros?|data|datos)\b",
        "deleting large sets of files or data",
    ),
    (
        "CRITICAL",
        rf"(credential|secret|password|api[ _-]?key|contrase\w*|token).{{0,40}}{_PROD}"
        rf"|{_PROD}.{{0,40}}(credential|secret|password|api[ _-]?key|contrase\w*)",
        "changing production credentials",
    ),
    (
        "CRITICAL",
        rf"\b(permissions?|access rights|iam|rbac|roles?|permisos?|accesos?)\b.{{0,40}}{_PROD}"
        rf"|{_PROD}.{{0,40}}\b(permissions?|iam|rbac|permisos?)\b",
        "changing production permissions",
    ),
    (
        "CRITICAL",
        rf"\b(infrastructure|infra|cluster|terraform|kubernetes|k8s|network|red)\b.{{0,40}}"
        rf"{_PROD}|{_PROD}.{{0,40}}\b(infrastructure|infra|cluster|terraform)\b",
        "changing production infrastructure",
    ),
    (
        "CRITICAL",
        r"force[ -]?push|push\s+--force|git\s+reset\s+--hard|reescrib\w* historial|"
        r"rewrite (git )?history",
        "destructive Git operation",
    ),
    (
        "HIGH",
        r"\b(migration|migrations|migraci[oó]n|schema|esquema|alter table|database model|"
        r"data model|modelo de datos|columns?|columnas?)\b",
        "database schema or data model change",
    ),
    (
        "HIGH",
        r"\b(auth\w*|login|sso|oauth|jwt|session|autenticaci[oó]n|autorizaci[oó]n|"
        r"permissions?|permisos?)\b",
        "authentication / authorization change",
    ),
    (
        "HIGH",
        r"\b(delete|remove|borra\w*|elimina\w*)\b.{0,30}\b(files?|folders?|directories|"
        r"archivos?|carpetas?|modules?|endpoints?)\b",
        "deleting files or features",
    ),
    (
        "HIGH",
        r"\b(upgrade|migrate|actualiza\w*|migra\w*)\b.{0,30}\b(framework|python|django|"
        r"fastapi|react|angular|node|version|versi[oó]n|dependenc\w*)\b",
        "framework or dependency migration",
    ),
    (
        "HIGH",
        r"\b(kubectl|helm|kubernetes|k8s|terraform)\b.{0,40}\b(apply|delete|upgrade|"
        r"install|destroy|aplica\w*)\b|\bdeploy\w*\b.{0,40}\b(kubernetes|k8s|staging)\b",
        "infrastructure change (non-production)",
    ),
    (
        "HIGH",
        r"\bgit\s+(init|commit|push|tag)\b"
        r"|\b(commit|push)\w*\b.{0,30}\b(changes?|code|branch|remote|origin|repo\w*|main|master"
        r"|cambios|c[oó]digo|rama)\b"
        r"|\b(initiali[sz]e\w*|inicializ\w*)\b.{0,20}\bgit\b"
        r"|\bhaz(er)?\s+(un\s+)?(commit|push)\b"
        r"|\b(create|crea\w*)\s+(a\s+|un\s+)?(release\s+)?tag\b",
        "Git history or remote change (init, commit, push, tag): needs the user's authorisation",
    ),
    ("HIGH", r"(\.env\b|secrets?|credentials?|contrase\w*)", "work involving secrets"),
    (
        "MEDIUM",
        r"\b(add|create|implement|build|new|expose|crea\w*|añad\w*|agreg\w*|implementa\w*|"
        r"construi\w*|nuev[oa]s?)\b",
        "new functionality",
    ),
    (
        "MEDIUM",
        r"\b(fix(?!\s+(an?\s+|the\s+)?(typos?|spelling|wording)\b)|bug|error|repair|arregl\w*|corrig\w*|repara\w*|falla\w*)\b",
        "bug fix",
    ),
    ("MEDIUM", r"\b(refactor\w*|restructur\w*|reorganiz\w*|clean ?up|limpi\w*)\b", "refactoring"),
    (
        "MEDIUM",
        r"\b(config\w*|settings?|environment variables?|variables de entorno)\b",
        "configuration change",
    ),
    (
        "LOW",
        r"\b(readme|docs?|documentation|documentaci[oó]n|typo|comments?|comentarios?|"
        r"spelling|ortograf\w*|wording|texto|text)\b",
        "documentation or text change",
    ),
]
_COMPILED = [(level, re.compile(rx, re.IGNORECASE), reason) for level, rx, reason in _RULES]
_FILE_RULES = [
    ("HIGH", re.compile(r"(^|/)(migrations?|alembic)/", re.I), "touches database migrations"),
    ("HIGH", re.compile(r"(^|/)\.env($|\.)(?!example)", re.I), "touches a .env file"),
    (
        "HIGH",
        re.compile(r"(^|/)(k8s|helm|charts|deploy|terraform|infra)/", re.I),
        "touches deployment configuration",
    ),
    (
        "CRITICAL",
        re.compile(r"(prod|production)[^/]*\.(ya?ml|tf|json)$|/(prod|production)/", re.I),
        "touches production configuration",
    ),
    (
        "MEDIUM",
        re.compile(r"(^|/)(dockerfile|docker-compose[^/]*)$", re.I),
        "touches container build",
    ),
]


@dataclass
class Risk:
    level: str = "LOW"
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def approval_required(self) -> bool:
        return self.blocked or self.level in APPROVAL_LEVELS

    def raise_to(self, level: str, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)
        if LEVELS.index(level) > LEVELS.index(self.level):
            self.level = level

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "reasons": self.reasons,
            "policy": "BLOCKED: refuse. HIGH/CRITICAL: show the plan and impact, then wait for "
            "explicit approval. LOW/MEDIUM: proceed autonomously and report.",
        }


def assess(task: str, files: list[str] | None = None) -> Risk:
    risk = Risk()
    text = task or ""
    matched = False
    for level, pattern, reason in _COMPILED:
        if pattern.search(text):
            matched = True
            if level == "BLOCKED":
                risk.blocked = True
                risk.raise_to("CRITICAL", reason)
            else:
                risk.raise_to(level, reason)
    for rel in files or []:
        for level, pattern, reason in _FILE_RULES:
            if pattern.search(rel.replace("\\", "/")):
                risk.raise_to(level, f"{reason} ({rel})")
    if text.strip() and not matched and not files:
        risk.raise_to("MEDIUM", "task type not recognised: treated as MEDIUM (conservative)")
    return risk
