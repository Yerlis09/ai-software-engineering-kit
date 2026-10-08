# .ai/context/ — context selection

Kit-managed overview (AI Software Engineering Kit v1.3.0). AI assistants do not need
to read the JSON files below: they run `ai-project context --task "<task>" --json` and load the
context package it returns.

| File | Owner | Purpose |
|---|---|---|
| `project.md` | **project** | Compact project summary, always loaded (L0) |
| `budget.json` | **project** | Estimated token budgets (characters / 4, not provider tokens) |
| `index.json` | derived | Installed agents, rules, workflows, stacks, sizes, sections |
| `graph.json` | derived | Knowledge graph: nodes and weighted relations used for ranking |

Derived files are **not sources of truth**. The sources are the kit's `agents/`, `rules/`,
`workflows/`, `stacks/`, `profiles/` and `catalog/`. `ai-project update` regenerates derived files
(local edits are overwritten, never turned into `.kit-new` conflicts), and so does
`ai-project context --rebuild-graph`. If `graph.json` is missing, corrupt or stale, the CLI rebuilds
it in memory; if that fails it falls back to direct routing.
