# Architecture

## Separation of responsibilities

| Layer | Owns | Does not own |
|---|---|---|
| **Core** — AI Software Engineering Kit `ai-project` 1.3.x | Engineering knowledge (agents, rules, workflows, stacks), knowledge graph, task classification, ranking, budget, rule slicing, `init`/`doctor`/`update`, lock file | Claude Code integration |
| **Plugin** — `netsf-ai-software-engineering` 1.1.0 | Claude Code skills and agents, project detection, project type from the request, scope signals (database, deployment), Git context, risk assessment, dry-run plans, impact analysis, materialisation of the core's selection, trust labelling, safety hook, user-requested execution restrictions | Engineering knowledge (never copied), the context algorithms |

The plugin uses only the core's public CLI (`ai-project version`, `ai-project context --json`,
including `--deployment` for simulated projects, available from core 1.3).

## Components

```
.claude-plugin/plugin.json      manifest (metadata.coreCompatibility = ">=1.3.0,<1.4.0")
skills/netsf-ai-engineer/       master orchestrator (model-invoked)
skills/plan|context|setup/      user-invoked commands (disable-model-invocation)
agents/*.md                     13 thin specialist adapters
hooks/hooks.json                PreToolUse safety guard + UserPromptSubmit restrictions
scripts/netsf_bridge.py         bridge CLI entry point
scripts/netsf_guard.py          hook entry point (fail-safe)
scripts/netsf/                  bridge, core, detect, scope, understand, autonomy, risk, plan,
                                guard, readonly, safety (stdlib only)
benchmarks/                     reproducible context benchmark
tests/                          pytest suite
```

## Request flow

```
user request (one message: requirement, user story, bug report or document)
  └─ netsf-ai-engineer skill
       1 bridge start → ENGINEERING BRIEF, one call:
           risk (risk.py) · detection (detect.py) · scope (scope.py) · core routing, ranking,
           budget (ai-project context) · lean materialisation (core.py) · task-focused
           understanding (understand.py: relevant files, existing routes, test/lint commands,
           docs) · decision (autonomy.py)
       2 decision
           PROCEED        → every phase now, no further prompts
           ASK_APPROVAL   → one consolidated approval (HIGH/CRITICAL), then every phase
           ASK_QUESTIONS  → one message with the blocking questions, then every phase
           READ_ONLY      → analyse, plan, report; no change (also enforced by the hook)
           BLOCKED        → refuse
       3 implement → tests → run the brief's commands → repair (≤5, counted by the hook)
         → documentation → validation → report (VERIFIED / INFERRED / NOT VERIFIED)
       execution inline (simple/normal tasks on existing projects) or delegated to
       netsf-ai-software-engineering:<specialist> agents (complex tasks, new projects)
```

Informational findings never stop the workflow: an unrelated parent Git repository, or an
existing route that may already implement the task (reported so the change extends it instead of
duplicating it).

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
(measured: 13,268 → 9,569 estimated tokens on the Kit demo task).

## Why plugin-side detection, risk and plan

They are Claude Code concerns today (the roadmap places project understanding and planning in
later core releases), so they live in the plugin: `detect.py`, `scope.py`, `risk.py`, `plan.py`.
Project-type inference reuses the core's task classification instead of re-implementing it.

## Execution restrictions

`readonly.py` turns the user's own words into per-session prohibitions (`modify`, `install`,
`git-init`, `commit`, `push`, `deploy`), stored in `$CLAUDE_PLUGIN_DATA/readonly/<session>.json`:

```
UserPromptSubmit  "dry run" / "solo análisis" / "do not push"  →  prohibitions saved (sticky)
PreToolUse        Write/Edit or a non-allow-listed command      →  deny + how to lift it
UserPromptSubmit  "exit dry-run" / "ya puedes modificar"        →  prohibitions cleared
```

Claude Code plan mode (`permission_mode: plan`) counts as full read-only.
