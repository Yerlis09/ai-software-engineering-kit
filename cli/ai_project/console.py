"""Terminal output and interactive prompts.

Both are injectable (streams and input function) so commands are fully testable.
Colours are used only on a TTY and never when ``NO_COLOR`` is set; symbols fall back
to ASCII when the terminal encoding cannot represent them (old Windows code pages).
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Sequence, TextIO

from ai_project.errors import EXIT_USAGE, KitError

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"

_UNICODE_SYMBOLS = {PASS: "✓", WARN: "!", FAIL: "✗", INFO: "i"}
_ASCII_SYMBOLS = {PASS: "OK", WARN: "!!", FAIL: "XX", INFO: "--"}
_COLORS = {PASS: "32", WARN: "33", FAIL: "31", INFO: "36", "bold": "1", "dim": "2"}


def _enable_windows_ansi() -> bool:
    if os.name != "nt":
        return True
    try:  # Enable VT processing on the Windows console; harmless if unsupported.
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


class Console:
    def __init__(self, out: TextIO | None = None, err: TextIO | None = None) -> None:
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        is_tty = hasattr(self.out, "isatty") and self.out.isatty()
        self.color = is_tty and "NO_COLOR" not in os.environ and _enable_windows_ansi()
        encoding = getattr(self.out, "encoding", None) or "ascii"
        try:
            "✓✗".encode(encoding)
            self.symbols = _UNICODE_SYMBOLS
        except (UnicodeEncodeError, LookupError):
            self.symbols = _ASCII_SYMBOLS

    def style(self, text: str, key: str) -> str:
        return f"\033[{_COLORS[key]}m{text}\033[0m" if self.color else text

    def print(self, text: str = "") -> None:
        print(text, file=self.out)

    def title(self, text: str) -> None:
        self.print(self.style(text, "bold"))
        self.print()

    def section(self, text: str) -> None:
        self.print()
        self.print(self.style(text, "bold"))

    def status(self, level: str, text: str, detail: str = "") -> None:
        symbol = self.style(self.symbols[level], level)
        line = f"{symbol} {text}"
        if detail:
            line += self.style(f" - {detail}", "dim")
        self.print(line)

    def error(self, text: str) -> None:
        print(self.style(f"Error: {text}", FAIL), file=self.err)

    def banner(self, lines: Sequence[str], level: str = WARN) -> None:
        width = max(len(line) for line in lines) + 4
        edge = "!" * width
        self.print(self.style(edge, level))
        for line in lines:
            self.print(self.style(f"! {line.ljust(width - 4)} !", level))
        self.print(self.style(edge, level))


class Prompter:
    """Interactive questions with validation. Never loops forever."""

    MAX_ATTEMPTS = 5

    def __init__(self, console: Console, input_fn: Callable[[str], str] = input) -> None:
        self.console = console
        self._input = input_fn

    def _read(self, prompt: str) -> str:
        try:
            return self._input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise KitError("Input aborted.", EXIT_USAGE) from None

    def _too_many(self, label: str) -> KitError:
        return KitError(f"Too many invalid answers for '{label}'.", EXIT_USAGE)

    def text(
        self,
        label: str,
        default: str = "",
        required: bool = False,
        validate: Callable[[str], str] | None = None,
    ) -> str:
        suffix = f" [{default}]" if default else ""
        for _ in range(self.MAX_ATTEMPTS):
            self.console.print(f"{label}{suffix}:")
            value = self._read("> ") or default
            if not value and required:
                self.console.print("  A value is required.")
                continue
            if validate and value:
                try:
                    return validate(value)
                except KitError as exc:
                    self.console.print(f"  {exc}")
                    continue
            return value
        raise self._too_many(label)

    def _list_options(self, options: Sequence[tuple[str, str]], marked: Sequence[str], mark: str):
        self.console.print()
        for index, (key, title) in enumerate(options, start=1):
            self.console.print(f"  {index}. {title}{mark if key in marked else ''}")
        self.console.print()

    def choose(
        self, label: str, options: Sequence[tuple[str, str]], default: str | None = None
    ) -> str:
        keys = [key for key, _ in options]
        self.console.print(f"{label}:")
        self._list_options(options, [default] if default else [], " (default)")
        for _ in range(self.MAX_ATTEMPTS):
            answer = self._read("Select:\n> ")
            if not answer and default:
                return default
            if answer.isdigit() and 1 <= int(answer) <= len(keys):
                return keys[int(answer) - 1]
            if answer in keys:
                return answer
            self.console.print(f"  Please enter a number between 1 and {len(keys)}.")
        raise self._too_many(label)

    def choose_many(
        self, label: str, options: Sequence[tuple[str, str]], defaults: Sequence[str]
    ) -> list[str]:
        keys = [key for key, _ in options]
        self.console.print(f"{label} (comma-separated numbers, Enter keeps the * defaults):")
        self._list_options(options, defaults, " *")
        for _ in range(self.MAX_ATTEMPTS):
            answer = self._read("Select:\n> ")
            if not answer:
                return list(defaults)
            chosen = _parse_multi(answer, keys)
            if chosen:
                return chosen
            self.console.print("  Invalid selection.")
        raise self._too_many(label)

    def confirm(self, label: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        for _ in range(self.MAX_ATTEMPTS):
            answer = self._read(f"{label} [{hint}] ").lower()
            if not answer:
                return default
            if answer in ("y", "yes", "o", "oui"):
                return True
            if answer in ("n", "no", "non"):
                return False
        raise self._too_many(label)


def _parse_multi(answer: str, keys: Sequence[str]) -> list[str]:
    chosen: list[str] = []
    for token in (t.strip() for t in answer.split(",") if t.strip()):
        if token.isdigit() and 1 <= int(token) <= len(keys):
            chosen.append(keys[int(token) - 1])
        elif token in keys:
            chosen.append(token)
        else:
            return []
    return list(dict.fromkeys(chosen))
