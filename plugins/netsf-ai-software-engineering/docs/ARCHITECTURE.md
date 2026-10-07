# Architecture

## Separation of responsibilities

| Layer | Owns | Does not own |
|---|---|---|
| **Core** — AI Software Engineering Kit `ai-project` 1.2.x | Engineering knowledge (agents, rules, workflows, stacks), knowledge graph, task classification, ranking, budget, rule slicing, `init`/`doctor`/`update`, lock file | Claude Code integration |
| **Plugin** — `netsf-ai-software-engineering` 1.0.0 | Claude Code skills and agents, project detection, risk assessment, dry-run plans, impact analysis, materialisation of the core's selection, trust labelling, safety hook | Engineering knowledge (never copied), the context algorithms |

The plugin uses only the core's public CLI (`ai-project version`, `ai-project context --json`).
No core API change was required, so the core stays at 1.2.0.

## Components

```
.claude-plugin/plugin.json      manifest (metadata.coreCompatibility = ">=1.2.0,<1.3.0")
skills/netsf-ai-engineer/       master orchestrator (model-invoked)
skills/plan|context|setup/      user-invoked commands (disable-model-invocation)
agents/*.md                     13 thin specialist adapters
hooks/hooks.json                PreToolUse safety guard
scripts/netsf_bridge.py         bridge CLI entry point
scripts/netsf_guard.py          hook entry point (fail-safe)
scripts/netsf/                  bridge, core, detect, risk, plan, guard, safety (stdlib only)
benchmarks/                     reproducible context benchmark
tests/                          pytest suite
```

## Request flow

```
user request
  └─ netsf-ai-engineer skill
       1 risk      bridge risk      → LOW/MEDIUM/HIGH/CRITICAL, BLOCKED
       2 detect    bridge detect    → mode kit/existing/new, technologies with confidence+evidence
       3 plan      bridge plan      → specialists, files, impact, approval gate (dry run)
       4 context   bridge context   → core selects; bridge materialises and labels trust
       5 delegate  netsf-ai-software-engineering:<specialist> (each loads --focus <role> --lean)
       6 implement → test → repair (≤5) → validate → report with REQ traceability
```

## Routing states

| State | When | Behaviour |
|---|---|---|
| `OPTIMIZED` | Kit project, core OK, graph routing | Full selection from the project's `.ai/` |
| `DEGRADED` | Core OK but project not initialised with the Kit, or core reported a fallback | Core simulates the detected profile/technology; content served from the installed Kit |
| `DIRECT` | Core missing, incompatible or failed | Progressive discovery plus the skill's essential rules; suggests setup |
| `BLOCKED` | Unsafe path from the core output, invalid line range, or a blocked task | Nothing is emitted; exit code 1 |

## Materialisation and trust

The core returns paths and H2 line ranges. The bridge reads them (bounded, path-checked with
`safe_child`) and labels each block:

- **Trusted:** a knowledge file byte-identical (LF-normalised SHA-256) to the installed Kit copy;
  `AGENTS.md` only if it matches the lock file hash.
- **Untrusted:** anything else (modified Kit files, `.ai/context/project.md`, project files).
  Wrapped in `UNTRUSTED PROJECT DATA` markers and scanned for prompt-injection patterns.

`--lean` omits `AGENTS.md` and `00-master.md` because the master skill already plays that role
(measured: 13,106 → 9,420 estimated tokens on the Kit demo task).

## Why plugin-side detection, risk and plan

They are Claude Code concerns today and adding them to the core would have required a minor core
release (1.3.0), which was out of scope. They are candidates for a future core release.
