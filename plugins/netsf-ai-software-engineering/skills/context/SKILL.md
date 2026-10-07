---
name: context
description: Show which engineering context NETSF would load for a task, why, and its estimated size versus loading everything.
disable-model-invocation: true
---

# NETSF context (advanced)

Use the text the user typed after the command as the task; if it is empty, ask for it.

Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/netsf_bridge.py" context --task "<task>" --json`
(Windows: `py -3` if `python` is not found) and summarise for the user, without pasting the
whole package:

- state (OPTIMIZED / DEGRADED / DIRECT / BLOCKED) and what it means;
- classification, specialists, risk;
- selected items with relevance and score, and the main skipped items with their reason;
- metrics: files loaded, emitted estimated tokens, full Kit context, reduction, routing and
  materialization time. Say that token figures are estimates (characters / 4), not billed tokens.

Experts can also run the core directly: `ai-project context --task "<task>"` and
`ai-project context --rebuild-graph`.
