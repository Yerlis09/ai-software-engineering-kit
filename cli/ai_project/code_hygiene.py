"""Heuristic review of code comments and docstrings (rules CODE-45 to CODE-47).

Two problems are reported, never fixed:

* **history** — comments that record how or why the code changed over time (meetings,
  requests, earlier behaviour, version tags) instead of what it does now;
* **non-english** — comments that look written in another language (accented letters or
  several Spanish/French function words).

Only comments and docstrings are read, never string literals, so keyword lists used as data
(for example multilingual matching patterns) are not reported. The checks are heuristics:
``doctor`` reports them as warnings. A line containing ``ai-kit: allow-comment`` is skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ai_project.secrets_scan import iter_files

SOURCE_SUFFIXES = {
    ".py": "#",
    ".sh": "#",
    ".ps1": "#",
    ".rb": "#",
    ".js": "//",
    ".jsx": "//",
    ".ts": "//",
    ".tsx": "//",
    ".java": "//",
    ".kt": "//",
    ".go": "//",
    ".cs": "//",
    ".c": "//",
    ".cpp": "//",
    ".h": "//",
    ".php": "//",
    ".rs": "//",
    ".scala": "//",
    ".swift": "//",
    ".sql": "--",
}
ALLOW_PRAGMA = "ai-kit: allow-comment"
MAX_FILES = 2000
MAX_FILE_BYTES = 512_000

HISTORY = re.compile(
    r"\b(updated|changed|modified|rewritten|replaced|added|fixed)\s+"
    r"(after|because|per|following|as (requested|asked)|on \d|in v?\d+\.\d+)\b"
    r"|\b(client|customer|manager)\s+(requested|asked for)\b"
    r"|\bas (requested|asked) by\b"
    r"|\bafter the (meeting|call|review)\b"
    r"|\bpreviously\b"
    r"|\b(old|new) implementation\b"
    r"|\bthis (replaces|replaced)\b"
    r"|\b(changed|added|new|removed) in (version |v)?\d+\.\d+"
    r"|\b(since|until|as of|before) v?\d+\.\d+"
    r"|\(v\d+\.\d+"
    r"|^v\d+\.\d+\b"
    r"|\bv\d+\.\d+ (additions?|behaviou?r|compatib\w*|api|keys?|files?|format)\b"
    r"|\b(actualizad|modificad|cambiad|añadid)[oa]s?\s+(por|tras|despu[eé]s|seg[uú]n)\b"
    r"|\ba petici[oó]n del cliente\b",
    re.IGNORECASE,
)
ACCENTED = re.compile(r"[áéíóúñ¿¡àèùçâêîôûœ]", re.IGNORECASE)
FOREIGN_WORDS = frozenset(
    {
        # Spanish
        "que",
        "para",
        "los",
        "las",
        "del",
        "una",
        "esta",
        "este",
        "cuando",
        "porque",
        "pero",
        "muy",
        "sobre",
        "entre",
        "hasta",
        "donde",
        "como",
        "siempre",
        "nunca",
        "tambien",
        "si",
        "el",
        "la",
        "se",
        "es",
        "por",
        "con",
        "sin",
        "lo",
        "al",
        "su",
        "sus",
        "y",
        "de",
        "en",
        "un",
        # French
        "les",
        "des",
        "pour",
        "avec",
        "dans",
        "une",
        "sur",
        "pas",
        "est",
        "et",
        "le",
        "du",
    }
)
# Words that are also common in English comments; they only count next to clear foreign words.
AMBIGUOUS = frozenset(
    {
        "si",
        "el",
        "la",
        "se",
        "es",
        "con",
        "lo",
        "al",
        "su",
        "y",
        "et",
        "le",
        "est",
        "pas",
        "sus",
        "como",
        "de",
        "en",
        "un",
        "por",
        "sin",
    }
)
WORD = re.compile(r"[a-zA-Z]+")


@dataclass(frozen=True)
class CommentFinding:
    """One comment line that looks like change history or non-English text."""

    path: str
    line: int
    kind: str  # "history" | "non-english"
    excerpt: str


def comment_lines(text: str, marker: str, python: bool) -> list[tuple[int, str]]:
    """Return ``(line number, comment text)`` for line comments, block comments and docstrings."""
    found: list[tuple[int, str]] = []
    in_block = False
    in_docstring: str | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if python:
            if in_docstring:
                found.append((number, line.replace(in_docstring, "")))
                if in_docstring in line:
                    in_docstring = None
                continue
            for quote in ('"""', "'''"):
                if line.startswith(quote) or re.match(r"^[rRbBuU]?" + quote, line):
                    body = line.split(quote, 1)[1]
                    found.append((number, body.replace(quote, "")))
                    if quote not in body:
                        in_docstring = quote
                    break
            else:
                if line.startswith("#"):
                    found.append((number, line.lstrip("#").strip()))
                elif " # " in raw and not _inside_string(raw, raw.index(" # ")):
                    found.append((number, raw.split(" # ", 1)[1].strip()))
            continue
        if in_block:
            found.append((number, line.lstrip("*").replace("*/", "").strip()))
            in_block = "*/" not in line
            continue
        if line.startswith("/*"):
            found.append((number, line[2:].replace("*/", "").strip()))
            in_block = "*/" not in line
        elif line.startswith(marker):
            found.append((number, line[len(marker) :].strip()))
        elif f" {marker} " in raw and not _inside_string(raw, raw.index(f" {marker} ")):
            found.append((number, raw.split(f" {marker} ", 1)[1].strip()))
    return found


def _inside_string(raw: str, index: int) -> bool:
    """Rough check: an odd number of quotes before ``index`` means we are inside a string."""
    before = raw[:index]
    return before.count('"') % 2 == 1 or before.count("'") % 2 == 1


def classify(comment: str) -> str | None:
    """Return ``"history"``, ``"non-english"`` or ``None`` for one comment text."""
    if not comment or ALLOW_PRAGMA in comment:
        return None
    if HISTORY.search(comment):
        return "history"
    if ACCENTED.search(comment):
        return "non-english"
    words = [w.lower() for w in WORD.findall(comment)]
    clear = {w for w in words if w in FOREIGN_WORDS and w not in AMBIGUOUS}
    ambiguous = [w for w in words if w in AMBIGUOUS]
    if len(clear) >= 2 or (clear and len(ambiguous) >= 2):
        return "non-english"
    return None


def scan_comments(root: Path) -> tuple[list[CommentFinding], int]:
    """Scan the project's source files; return the findings and the number of files read."""
    findings: list[CommentFinding] = []
    files = 0
    for path, rel in iter_files(root):
        marker = SOURCE_SUFFIXES.get(path.suffix.lower())
        if marker is None:
            continue
        if files >= MAX_FILES:
            break
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files += 1
        lines = text.splitlines()
        for number, comment in comment_lines(text, marker, path.suffix.lower() == ".py"):
            if ALLOW_PRAGMA in lines[number - 1]:
                continue
            kind = classify(comment)
            if kind:
                findings.append(CommentFinding(rel, number, kind, comment[:80]))
    return findings, files
