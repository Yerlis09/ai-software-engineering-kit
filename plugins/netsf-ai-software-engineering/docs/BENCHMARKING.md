# Benchmarking

## Context benchmark (measured)

```
python plugins/netsf-ai-software-engineering/benchmarks/context_benchmark.py --repeat 5 [--json out.json]
```

For each task it compares the **direct** baseline (all Kit knowledge, `full_context_tokens` from
the core) with the **routed** package emitted by the bridge, and the `--lean` variant used by the
master skill. Tokens are estimates (characters / 4), not billed tokens. Times are medians of 5
runs and depend on the machine.

Results on 2026-10-07 (Windows 11, Python 3.12, core 1.2.0, plugin 1.0.0):

| Scenario | Task | State | Direct tok | Routed tok | Lean tok | Lean saving | Files (routed/lean) | Routing ms | Materialize ms |
|---|---|---|---|---|---|---|---|---|---|
| kit-project | Create a FastAPI endpoint to retrieve cells | OPTIMIZED | 44254 | 13106 | 9420 | 78.7% | 13/11 | 26.2 | 19.1 |
| clickhouse | Fix ClickHouse query | DEGRADED | 40630 | 10378 | 8110 | 80.0% | 10/9 | 12.8 | 16.8 |
| docker | Add a health check to the Docker image | DEGRADED | 44075 | 6319 | 4051 | 90.8% | 5/4 | 11.6 | 7.9 |
| fastapi | Create a FastAPI endpoint to retrieve cells | DEGRADED | 41955 | 11156 | 8889 | 78.8% | 11/10 | 14.2 | 16.7 |
| frontend | Improve React dashboard performance | DEGRADED | 39164 | 11153 | 8886 | 77.3% | 12/11 | 14.2 | 20.6 |
| kubernetes | Deploy service to Kubernetes | DEGRADED | 41955 | 9113 | 6845 | 83.7% | 8/7 | 11.7 | 15.7 |
| microservice | Review the authentication implementation | DEGRADED | 41945 | 8082 | 5814 | 86.1% | 8/7 | 13.0 | 14.0 |
| python_automation | Refactor a Python service that reads the Excel report | DEGRADED | 38202 | 9335 | 7067 | 81.5% | 9/8 | 12.4 | 15.8 |
| python_backend | Add an endpoint to list invoices | DEGRADED | 44075 | 10959 | 8692 | 80.3% | 11/10 | 13.5 | 17.6 |

Total over 9 tasks: direct 376,255 tokens, lean 67,774 tokens (**82.0% less**).

Scenario projects are the small synthetic ones in `tests/scenarios.py`; `DEGRADED` means the core
simulated the detected profile because the project was not initialised with the Kit.

### Plugin overhead (Claude Code `plugin details`)

| Component | Always loaded | On invoke |
|---|---|---|
| Whole plugin (skill/agent descriptions) | ~910 tokens | — |
| `netsf-ai-engineer` skill | ~90 | ~1.8k |
| Each agent | — | ~380 |
| Hook | 0 (harness only) | 0 |

These are Claude Code's own estimates.

## Quality benchmark (NOT VERIFIED)

Fewer tokens is only useful if answers stay correct. Measuring that needs real model runs:

- `evals/` holds prepared `claude plugin eval` cases (task prompt plus graders for expected
  specialists, safety behaviour, approval gates and no over-engineering), run with and without
  the plugin (ablation).
- **They have not been executed.** Running them calls the model on your credential; it needs
  explicit authorisation: `claude plugin eval plugins/netsf-ai-software-engineering`.

What *is* verified by deterministic tests: routing selects the required specialists and excludes
irrelevant ones for 8 scenarios, risk levels and approval gates, guard decisions, plan never
modifies files, impact analysis, and the no-over-engineering guidance for simple new projects.
