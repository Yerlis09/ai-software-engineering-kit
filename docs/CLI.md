# CLI reference

```text
ai-project <command> [options]
ai-project --version
```

Exit codes (all commands): `0` success, `1` failure, `2` usage error (bad option, invalid
input, aborted prompt). `python -m ai_project` is equivalent to `ai-project`.

## `ai-project init [DIRECTORY]`

Creates a project or adds the kit to an existing one.

- `DIRECTORY` defaults to `./<project-name>`; use `.` for the current directory. The project
  name defaults to the directory name when that name is valid.
- Interactive by default; every question can be answered with a flag.

| Option | Description |
|---|---|
| `--name NAME` | 1-64 chars: letters, digits, `-`, `_`, `.`; starts with a letter; portable on Windows |
| `--profile P` | `backend-api`, `frontend`, `fullstack`, `python-automation`, `data-engineering`, `microservice`, `custom` |
| `--technology T` | Must be offered by the profile (`ai-project list technologies`) |
| `--database D` | `postgresql`, `sqlserver`, `clickhouse`, `mongodb`, `undecided`, `none`, `custom`. Default: `undecided` (the assistant asks before adding persistence; team default ClickHouse is only recommended), `none` for `frontend` |
| `--deployment D` | `kubernetes` (Docker + RKE Staging/Prod, the team standard when deploying), `docker`, `undecided`, `none`. Default: `undecided` — deployment is out of scope: no Docker/Kubernetes/NGINX/CI guides and no `deploy/` folder until it is chosen |
| `--assistants A,B` | `claude-code`, `copilot`, `cursor`, `codex` (default: all) |
| `--stacks S,T` | Extra stack guides (`ai-project list stacks`) |
| `--description TEXT` | Business objective (one sentence) |
| `-y, --non-interactive` | Never prompt: flags + defaults (`--name` or a valid directory name, and `--profile`, are required) |
| `--force` | Re-initialise an initialised project; replaces differing kit files, keeping `*.kit-backup` |

Behaviour on existing files:

| Existing file | Result |
|---|---|
| Project-owned file (README, docs, context...) | Kept untouched |
| Kit file, identical | Nothing to do |
| Kit file, different | Kit version written to `<file>.kit-new` (with `--force`: replaced, old saved as `<file>.kit-backup`) |
| `.ai/kit.lock.json` present | Refused: use `ai-project update` (or `--force`) |

## `ai-project doctor`

Validates a project and prints a report grouped by category: Configuration, Kit integrity,
Git, Quality, Security, Documentation, Environment.

| Option | Description |
|---|---|
| `--path DIR` | Project directory (default: current) |
| `--strict` | Warnings also fail (exit 1) |
| `--format json` | Machine-readable output for CI dashboards |

Statuses: `PASS`, `WARN` (should fix), `FAIL` (must fix, exit 1), `INFO`. On terminals that
cannot display `✓`/`✗`, ASCII markers are used (`OK`, `!!`, `XX`, `--`). Colours follow
`NO_COLOR`.

What is checked:

| Category | Checks |
|---|---|
| Configuration | `AGENTS.md`, agents (incl. master), rules, workflows, `.ai/context/project.md` (warns on remaining TODOs), context index and budget (WARN if missing or invalid) |
| Knowledge Graph | graph exists, structure, node and edge types, references, project paths, no cycles, source fingerprint (WARN with recovery instructions, never FAIL) |
| Kit integrity | Lock file, missing core files, customised core files, newer kit available |
| Git | Repository (WARN when the project only sits inside a parent directory's repository: confirm it is a monorepo or propose `git init` with approval), remote on the team server (git.netsf.fr; never invented), `.gitignore` excludes `.env` |
| Quality | Formatter, linter, type checker, test files, CI pipeline (detected from config files; INFO instead of WARN when deployment is not in scope), code comments in English describing current behaviour (heuristic WARN for change-history or non-English comments and docstrings; `ai-kit: allow-comment` marks a deliberate exception) |
| Security | Secrets in source (**FAIL**), credentials in `.env` files (**WARN + alert banner**), dependency lock files, non-root Dockerfiles |
| Documentation | README, `docs/architecture/`, Mermaid diagrams, ADRs `docs/adr/NNNN-*.md` |
| Environment | `.env.example`, local `.env` files present, `.editorconfig` |

The secret detection is heuristic. Use a dedicated scanner (gitleaks) in CI as well.
A line can be allow-listed with the comment `ai-kit: allow-secret` (for test fixtures;
reviewers should challenge it).

## `ai-project update`

Brings the project's CORE files to the version of the installed CLI.

| Option | Description |
|---|---|
| `--path DIR` | Project directory (default: current) |
| `--dry-run` | Show the changes, write nothing |
| `--check` | Exit 1 if updates are pending (for CI), write nothing |
| `--force` | Resolve conflicts with the kit version (old file saved as `.kit-backup`) |

Output starts with `Current Kit: x.y.z (project)` and `Latest Kit: x.y.z (installed CLI)`.
The algorithm is described in [VERSIONING.md](VERSIONING.md#how-update-decides). The kit
never downloads anything during `update`; upgrading the CLI is an explicit `pip` / `pipx`
step.

## `ai-project context`

Selects the minimum context for a task and explains every choice. Details:
[CONTEXT_OPTIMIZATION.md](CONTEXT_OPTIMIZATION.md).

| Option | Description |
|---|---|
| `--task TEXT` | The task. Without it, only the L0 core context is shown |
| `--path DIR` | Project directory (default: current; must contain `.ai/`) |
| `--profile P` | Simulate a project of this profile instead (nothing written); `--technology`, `--database` refine it |
| `--json` | Context package for tools and assistants: `selected_agents`, `selected_rules` (with sections), `selected_workflows`, `selected_stacks`, `project_context`, `skipped_context`, `reasons`, `estimated_tokens`, `budget`, `full_context_tokens`, `reduction_percentage` |
| `--strict` | Exit 1 when the estimate is over budget |
| `--profile P`, `--technology T`, `--database D`, `--deployment D` | Simulate a project of that profile instead of reading `--path` (nothing is written). `--deployment` defaults to `undecided`, so deployment guides are only considered when a deployment is given |
| `--rebuild-graph` | Regenerate, validate and save `.ai/context/graph.json` from the kit sources, then print a summary (`graph_rebuild` in JSON). Combine with `--task` to analyse right after |

Since 1.2 the router uses the local knowledge graph (`Routing: knowledge graph: loaded`). If the
graph is missing, corrupt or stale it is rebuilt in memory with a warning, and if that fails the
v1.1 direct routing is used. The output adds `Classification`, `Budget` (tier), the relevance and
score of each item, and `Metrics` (selected or skipped nodes, routing time).

Example (abridged, v1.1 format):

```text
AI CONTEXT ANALYSIS
Project: billing-api  (profile backend-api)
Task:
  Add customer creation endpoint
Workflow: .ai/workflows/new-feature.md  (Task mentions: add, creat, endpoint)

Selected agents:
✓ 00-master - L0: orchestrator, classifies and selects context
✓ 02-backend - API design, services, repositories, validation (HIGH). Task mentions: endpoint
✓ 04-architecture - ... (MEDIUM). Required by 02-backend (MEDIUM)
✓ 10-testing - ... (HIGH). Required by 02-backend (HIGH)

Targeted reviews (rule sections instead of the full agent):
i 09-security - Targeted review only (MEDIUM) ... Task mentions: creat

Estimated context:
  ...
  Estimated         13,026 tokens
  Budget            20,000 tokens
✓ Status: OK
```

Token counts are estimates (characters / 4), not the provider's actual token count.

## `ai-project list [WHAT]`

`WHAT` is one of `profiles` (default), `technologies`, `databases`, `deployments`, `assistants`,
`stacks` or `agents`.

## `ai-project version`

Prints the CLI version, the kit location, the Python version and, inside a project, the kit
version that generated it.

## `ai-project help [COMMAND]`

Same as `ai-project --help` or `ai-project COMMAND --help`.

## Environment variables

| Variable | Effect |
|---|---|
| `AI_KIT_HOME` | Use another kit directory (for a team fork or testing kit changes) instead of the bundled one |
| `NO_COLOR` | Disable colours |
