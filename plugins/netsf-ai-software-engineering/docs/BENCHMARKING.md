# Benchmarking

## Context benchmark (measured)

```
python plugins/netsf-ai-software-engineering/benchmarks/context_benchmark.py --repeat 5 [--json out.json]
```

For each task it compares the **direct** baseline (all Kit knowledge, `full_context_tokens` from
the core) with the **routed** package emitted by the bridge, and the `--lean` variant used by the
master skill. Tokens are estimates (characters / 4), not billed tokens. Times are medians of 5
runs and depend on the machine.

Results on 2026-10-07 (Windows 11, Python 3.12, core 1.3.0, plugin 1.1.0; the core of this
repository, with no other `ai-project` on `PATH`):

| Scenario | Task | State | Direct tok | Routed tok | Lean tok | Lean saving | Files (routed/lean) | Routing ms | Materialize ms |
|---|---|---|---|---|---|---|---|---|---|
| kit-project | Create a FastAPI endpoint to retrieve cells | OPTIMIZED | 38262 | 13268 | 9569 | 75.0% | 13/11 | 56.5 | 61.4 |
| clickhouse | Fix ClickHouse query | DEGRADED | 37006 | 10578 | 8175 | 77.9% | 10/9 | 25.3 | 15.1 |
| docker | Add a health check to the Docker image | DEGRADED | 43874 | 6884 | 4480 | 89.8% | 5/4 | 22.6 | 7.8 |
| fastapi | Create a FastAPI endpoint to retrieve cells | DEGRADED | 36916 | 11421 | 9017 | 75.6% | 11/10 | 22.4 | 14.7 |
| frontend | Improve React dashboard performance | DEGRADED | 34125 | 11297 | 8894 | 73.9% | 12/11 | 23.2 | 14.7 |
| kubernetes | Deploy service to Kubernetes | DEGRADED | 43119 | 9677 | 7274 | 83.1% | 8/7 | 19.0 | 9.9 |
| microservice | Review the authentication implementation | DEGRADED | 43110 | 8226 | 5822 | 86.5% | 8/7 | 21.5 | 10.0 |
| python_automation | Refactor a Python service that reads the Excel report | DEGRADED | 34523 | 9928 | 7525 | 78.2% | 9/8 | 23.0 | 11.2 |
| python_backend | Add an endpoint to list invoices | DEGRADED | 39092 | 11224 | 8820 | 77.4% | 11/10 | 22.6 | 14.1 |

Total over 9 tasks: direct 350,027 tokens, lean 69,576 tokens (**80.1% less**). A second run
gave identical states, specialists, token counts and file counts; times varied between runs
(routing 19–57 ms).

Compared with core 1.2.0 / plugin 1.0.0 (lean 67,774 vs direct 376,255, 82.0% less): the policy
rules of core 1.3 add about 2.7% to the routed packages, and the direct baseline is smaller
because projects without deployment in scope no longer install the Docker, Kubernetes, NGINX and
CI guides.

Scenario projects are the small synthetic ones in `tests/scenarios.py`; `DEGRADED` means the core
simulated the detected profile because the project was not initialised with the Kit.

### Plugin overhead (Claude Code `plugin details`)

| Component | Always loaded | On invoke |
|---|---|---|
| Whole plugin (skill/agent descriptions) | ~910 tokens | — |
| `netsf-ai-engineer` skill | ~90 | ~1.6k |
| Each agent | — | ~380 |
| Hook | 0 (harness only) | 0 |

These are Claude Code's own estimates.

## Autonomy benchmark (measured)

```
python plugins/netsf-ai-software-engineering/benchmarks/autonomy_benchmark.py [--json out.json]
```

One request per scenario, measured on the deterministic workflow layer (`bridge start`): how
many user prompts the workflow needs, approvals, blocking questions, specialists, context
tokens, files inspected, relevant files found and test commands detected. Results on 2026-10-07
(core 1.3.0, plugin 1.1.0):

| Scenario | Decision | Execution | Prompts | Approvals | Questions | Specialists | Context tok | Files inspected | Relevant files | Test cmds |
|---|---|---|---|---|---|---|---|---|---|---|
| existing-flask | PROCEED | inline | 1 | 0 | 0 | 4 | 8394 | 8 | 4 | 1 |
| existing-flask-route-exists | PROCEED | inline | 1 | 0 | 0 | 4 | 8394 | 8 | 4 | 1 |
| existing-flask-migration | ASK_APPROVAL | inline | 2 | 1 | 0 | 4 | 7452 | 8 | 4 | 1 |
| existing-flask-dry-run | READ_ONLY | inline | 1 | 0 | 0 | 4 | 8394 | 8 | 4 | 1 |
| existing-fastapi | PROCEED | inline | 1 | 0 | 0 | 4 | 9017 | 6 | 3 | 1 |
| existing-react | PROCEED | delegate | 1 | 0 | 0 | 4 | 8894 | 3 | 0 | 0 |
| new-api-with-persistence | ASK_QUESTIONS | delegate | 2 | 0 | 1 | 4 | 6798 | 0 | 0 | 0 |
| new-file-processing | PROCEED | delegate | 1 | 0 | 0 | 4 | 6942 | 0 | 0 | 0 |

Normal tasks need one prompt; the migration asks one approval; a new project that stores data
asks one question (the database); the dry run stays read-only. What the model does next — files
changed, tests executed, repair attempts — needs a real model run: the
`user-story-single-prompt` eval measures it (NOT VERIFIED until run).

## Quality benchmark (NOT VERIFIED)

Fewer tokens is only useful if answers stay correct. Measuring that needs real model runs:

- `evals/` holds 11 prepared `claude plugin eval` cases (task prompt plus graders for expected
  specialists, safety behaviour, approval gates, no over-engineering, database clarification,
  file-only work and dry runs), run with and without the plugin (ablation).
- **They have not been executed.** Running them calls the model on your credential; it needs
  explicit authorisation: `claude plugin eval plugins/netsf-ai-software-engineering`.

What *is* verified by deterministic tests: routing selects the required specialists and excludes
irrelevant ones for 8 scenarios, risk levels and approval gates, guard decisions, plan never
modifies files, impact analysis, and the no-over-engineering guidance for simple new projects.
