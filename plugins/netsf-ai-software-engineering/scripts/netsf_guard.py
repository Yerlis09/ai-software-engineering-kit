"""PreToolUse hook entry point: deterministic safety guardrail (see netsf/guard.py).

Reads the hook event JSON on stdin, prints a permission decision JSON (or nothing), exits 0.
"""

import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

hook_output: Optional[Callable[[str], str]]
try:
    from netsf.guard import hook_output
except Exception:  # fail-safe: if the module cannot load, ask the human
    hook_output = None


def main() -> int:
    raw = sys.stdin.read()
    if hook_output is None:
        print(
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": '
            '"ask", "permissionDecisionReason": "NETSF safety guard unavailable; please confirm."}}'
        )
        return 0
    out = hook_output(raw)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
