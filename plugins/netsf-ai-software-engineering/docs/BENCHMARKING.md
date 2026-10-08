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
| kit-project | Create a FastAPI endpoint to retrieve cells | OPTIMIZED | 38262 | 13269 | 9569 | 75.0% | 13/11 | 45.7 | 67.0 |
| clickhouse | Fix ClickHouse query | DEGRADED | 37006 | 10579 | 8175 | 77.9% | 10/9 | 28.5 | 40.3 |
| docker | Add a health check to the Docker image | DEGRADED | 43874 | 6884 | 4480 | 89.8% | 5/4 | 20.6 | 18.6 |
| fastapi | Create a FastAPI endpoint to retrieve cells | DEGRADED | 36916 | 11421 | 9017 | 75.6% | 11/10 | 24.9 | 38.5 |
| frontend | Improve React dashboard performance | DEGRADED | 34125 | 11298 | 8894 | 73.9% | 12/11 | 23.8 | 41.2 |
| kubernetes | Deploy service to Kubernetes | DEGRADED | 43119 | 9678 | 7274 | 83.1% | 8/7 | 21.2 | 31.9 |
| microservice | Review the authentication implementation | DEGRADED | 43110 | 8226 | 5822 | 86.5% | 8/7 | 23.3 | 22.3 |
| python_automation | Refactor a Python service that reads the Excel report | DEGRADED | 34523 | 9929 | 7525 | 78.2% | 9/8 | 21.9 | 37.5 |
| python_backend | Add an endpoint to list invoices | DEGRADED | 39092 | 11224 | 8820 | 77.4% | 11/10 | 29.4 | 60.0 |

Total over 9 tasks: direct 350,027 tokens, lean 69,576 tokens (**80.1% less**). A second run
gave identical states, specialists, token counts and file counts; times varied between runs
(routing 19–54 ms).

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
| `netsf-ai-engineer` skill | ~90 | ~2.5k |
| Each agent | — | ~380 |
| Hook | 0 (harness only) | 0 |

These are Claude Code's own estimates.

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
