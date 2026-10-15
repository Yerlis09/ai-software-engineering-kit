# Usage (advanced)

## Automatic mode

Describe a software task once — a requirement, a user story, a bug report or a document. The
`netsf-ai-engineer` skill calls `bridge start` once and follows its decision: at LOW/MEDIUM risk
with nothing blocking it implements, tests, repairs (max 5 cycles), documents, validates and
reports without further prompts. It stops only to ask for approval (HIGH/CRITICAL risk) or for a
decision only you can make (for example the database), and then asks once.

## Commands

```
/netsf-ai-software-engineering:plan <task>      dry run, no file changes
/netsf-ai-software-engineering:context <task>   explain the selected context and its size
/netsf-ai-software-engineering:setup            check/install the core (with approval)
```

## Bridge CLI

All skills and agents call the bridge; you can run it directly:

```
python scripts/netsf_bridge.py start --task "..." [--path DIR] [--profile P [--technology T]] [--json]
python scripts/netsf_bridge.py check [--json]
python scripts/netsf_bridge.py detect [--path DIR] [--snapshot] [--json]
python scripts/netsf_bridge.py risk --task "..." [--files a b] [--json]
python scripts/netsf_bridge.py plan --task "..." [--path DIR] [--change FILE ...] [--json]
python scripts/netsf_bridge.py context --task "..." [--path DIR] [--focus AGENT_ID] [--lean] [--json]
```

| Exit code | Meaning |
|---|---|
| 0 | OK (including DEGRADED and DIRECT fallbacks) |
| 1 | BLOCKED task or context, or core missing on `check` |
| 2 | Invalid arguments |

### `detect`

Bounded walk (depth 4, 5,000 entries, vendor dirs skipped). Reads only manifests, Dockerfiles,
compose, CI files, up to 40 Kubernetes YAML files and 25 entry points. Each finding has a
confidence (0–1) and evidence (`file: reason`). `--snapshot` prints a compact project snapshot;
it is never written to disk.

### `risk`

Deterministic rules (English and Spanish) on the task text and optional file list:

| Level | Examples |
|---|---|
| BLOCKED | upload/exfiltrate secrets, "ignore previous instructions", reveal passwords |
| CRITICAL | production deploy, drop database, delete all files, force push, production credentials |
| HIGH | migrations, authentication, deleting files, framework upgrades, kubectl/helm/terraform |
| MEDIUM | add, create, fix, refactor, configuration; any unknown non-empty task |
| LOW | documentation, typos, comments |

### `start` (engineering brief)

One read-only call that combines risk, detection, scope, routing, the lean context package,
task-focused understanding and the workflow decision:

| Field | Content |
|---|---|
| `decision.action` | `PROCEED`, `ASK_APPROVAL`, `ASK_QUESTIONS`, `READ_ONLY` or `BLOCKED` |
| `decision.questions` | Only blocking questions (database when persistence is needed, deployment target) |
| `decision.notes` | Informational findings (parent Git repository, possible existing implementation) |
| `decision.execution` | `inline` or `delegate`, with the specialists |
| `decision.phases`, `repair_policy`, `report_sections` | The workflow to run and the report contract |
| `understanding` | Relevant files with matching lines, existing routes, test and lint commands, docs to review (INFERRED) |
| `metrics.autonomy` | Prompts required, approvals, questions, specialists, context tokens, files inspected |

The text output ends with the materialised context package.

### `plan`

Dry run (`modifies_files: false`): project mode, **project type** (from the Kit lock, the
detection, or — for empty or unrecognised projects — the request itself), detected technology,
**database** (`specified`, `ask` with the ClickHouse recommendation, `none` for file-only work,
`not-applicable`), **deployment** (in scope or not, target or question), **Git** (own repository,
parent directory's repository — never used — or none), specialists, files to read, architecture
guidance, risk, approval requirement, **questions for the user**, and with `--change` an impact
analysis (referencing files and affected tests, bounded scan).

`--profile P [--technology T]` (on `plan` and `context`) overrides the inferred project type for
advanced users.

### `context`

Calls `ai-project context --json`, materialises the selection and reports metrics:
`files_loaded`, `emitted_estimated_tokens`, `full_context_tokens`, `routing_time_ms`,
`materialization_ms`, `untrusted_blocks`, `injection_warnings`.
`--focus 02-backend` returns only that specialist's view; `--lean` drops orchestration files.

## New versus existing projects

- **New** (no recognised manifests): simple modular architecture; no microservices, brokers or
  extra infrastructure without a stated requirement. Offer `ai-project init`.
- **Existing**: minimal safe change; keep architecture, APIs, conventions, deployment and tests.
- **Kit** (`.ai/kit.lock.json` present): `OPTIMIZED` routing from the project's own standards.
