---
name: setup
description: Check that NETSF AI Software Engineering is ready - Python, the AI Software Engineering Kit core and its version - and guide the one-time setup.
disable-model-invocation: true
---

# NETSF setup

Explain each step in plain language. Never install anything without the user's explicit "yes".

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/netsf_bridge.py" check` (if `python` is not found,
   try `py -3`; if neither exists, tell the user to install Python 3.9+ from python.org and stop).
2. If the core status is **OK**, say everything is ready and suggest describing a task.
3. If it is **MISSING** or **INCOMPATIBLE**, show the exact command printed by `check` (it pins a
   compatible version from the team's Git server). Ask the user for the repository URL if it is
   still a placeholder. Run it only after explicit approval; never download or run other code.
   Then re-run `check`.
4. Optional, only if the user wants the full standards in this project: run
   `ai-project init .` (it never overwrites existing files), then `ai-project doctor`, and
   explain the result simply.

Never print or upload credentials. Do not change Git settings.
