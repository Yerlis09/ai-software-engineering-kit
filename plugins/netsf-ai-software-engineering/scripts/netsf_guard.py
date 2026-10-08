"""Hook entry point: safety guardrail and user-requested execution restrictions.

* ``PreToolUse`` events: prints a permission decision JSON (or nothing); see ``netsf/guard.py``
  and ``netsf/readonly.py``.
* ``UserPromptSubmit`` events: records dry-run / "do not modify" requests from the user's
  prompt and prints additional context (or nothing); never blocks the prompt.

Always exits 0.
"""

import json
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

hook_output: Optional[Callable[[str], str]]
prompt_hook: Optional[Callable[[dict], str]]
try:
    from netsf.guard import hook_output
    from netsf.readonly import prompt_hook
except Exception:  # fail-safe: if the modules cannot load, ask the human
    hook_output = None
    prompt_hook = None

UNAVAILABLE = (
    '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": '
    '"ask", "permissionDecisionReason": "NETSF safety guard unavailable; please confirm."}}'
)


def _event_name(raw: str) -> str:
    try:
        event = json.loads(raw)
    except ValueError:
        return ""
    return str(event.get("hook_event_name", "")) if isinstance(event, dict) else ""


def main() -> int:
    raw = sys.stdin.read()
    if _event_name(raw) == "UserPromptSubmit":
        if prompt_hook is not None:
            try:
                out = prompt_hook(json.loads(raw))
            except Exception:  # a prompt must never be blocked by a guard error
                out = ""
            if out:
                print(out)
        return 0
    if hook_output is None:
        print(UNAVAILABLE)
        return 0
    out = hook_output(raw)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
