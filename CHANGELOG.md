# Changelog

All notable changes to the kit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/) (see `docs/VERSIONING.md`).

## [Unreleased]

## [1.3.0] - 2026-10-07

MINOR release: scope and decision policies (1A pre-production hardening). The context engine,
lock schema (1) and the JSON keys of `ai-project context` are unchanged; `init` defaults change.

### Changed

- **Database and deployment are decisions, not defaults.** `init` (and the `context --profile`
  simulation) record `undecided` when they are not chosen (frontend: database `none`). New
  catalog values `undecided` for databases and deployments. With deployment `undecided` or
  `none`, no Docker/Kubernetes/CI guides, no NGINX serving guide and no `deploy/` folder are
  added. Previously the defaults were `postgresql` and `kubernetes`; pass them explicitly to
  keep that setup (`--database postgresql --deployment kubernetes`).
- Technologies list NGINX as a `serving_stacks` entry, installed only when deployment is in
  scope.
- **Knowledge:** new always-routable policy sections `rules/architecture.md` "Scope and
  decisions" (ARCH-42..47: requirements first, technical autonomy, ask only what cannot be
  inferred, database question with ClickHouse as recommendation, deployment as a separate
  scope, never invent infrastructure values) and `rules/coding.md` "Language, docstrings and
  comments" (CODE-45..47: English, functional docstrings, no change history in code).
  DOC-30..32 (current-state English docs, documentation review before done, no unverified
  claims). Deployment rules (ARCH-31..35, ARCH-14, TEST-29, DOC-07) apply when deployment or CI
  exist. CODE-39: no `git init`, remote, commit, push or tag without authorisation; never use a
  parent directory's repository.
- `agents/00-master.md`: requirements labelling, decision and execution-authority section; the
  "stop and ask" list no longer asks the human to approve frameworks or libraries.
  `agents/03-database.md` and `agents/12-devops.md` state their scope.
- `workflows/new-project.md`: requirements first, autonomous stack choice, database only when
  confirmed, repository initialised only with approval, deployment steps only when in scope.
- `templates/base/AGENTS.md`: decision, scope, dry-run, Git and language rules; condensed
  context-routing section (details in the master agent). Architecture templates mark NGINX and
  deployment content "(if deployed)"; `docs/deployment.md` states it applies once deployment is
  in scope.
- `doctor`: a project that only sits inside a parent directory's Git repository is a WARN (it
  was a PASS); repository and remote hints never suggest invented URLs; a missing CI pipeline is
  INFO when deployment is not in scope.
- Code comments that recorded version history were rewritten to describe current behaviour;
  the `context` text output says "direct (fallback)".

### Added

- `ai-project context --deployment` for simulated projects.
- Task classification: `json`, `404` and `status code` signal API work (a user story that
  returns JSON and 404 now routes to the backend specialist).
- `agents/00-master.md`: at LOW/MEDIUM risk with nothing blocking, all lifecycle steps run
  without waiting for new prompts; otherwise the agent asks once and continues (the
  single-assistant paragraph was condensed to keep the L0 budget).
- `doctor` check "Code comments (English, current behaviour)": heuristic WARN for
  change-history and non-English comments/docstrings (`cli/ai_project/code_hygiene.py`;
  `ai-kit: allow-comment` marks an exception).
- Tests: `tests/test_policies.py` (defaults, scope routing, knowledge policies, rule metadata,
  comment hygiene of the kit's own code, doctor checks).

### Tests changed intentionally

- `tests/test_context.py`: the `package()` helper now states the scenario explicitly
  (PostgreSQL + Kubernetes, as the former defaults) because routing tests describe a deployed
  project with a database.
- `tests/test_init.py::test_interactive_wizard`: the default deployment is now `undecided`;
  the test also asserts that no deployment guide or `deploy/` folder is created.
- Version-history comments in tests were rewritten (the history of those test changes is in
  the 1.2.0 entry below).

### Claude Code plugin `netsf-ai-software-engineering` 1.1.0

Separate deliverable in `plugins/netsf-ai-software-engineering/` with the marketplace manifest
`.claude-plugin/marketplace.json` (marketplace `netsf`); requires core `>=1.3.0,<1.4.0`.

- Master skill, 3 user commands (plan, context, setup), 13 thin specialist agents; project
  detection, risk assessment with approval gates, dry-run plans with impact analysis; trust
  labelling of context; deterministic safety hook; reproducible context benchmark.
- **Scope signals** (`scripts/netsf/scope.py`): database (named / ask the user / none for
  file-only workflows) and deployment (requested or not, target or question) for plans and
  routing; the core simulation receives `--database`/`--deployment` accordingly.
- **Project type from the request**: an empty or unrecognised project is classified from the
  core's task classification (no manual profile choice); `--profile/--technology` remain as an
  advanced override.
- **Git context**: own repository, parent directory's repository (reported, never used) or
  none; shown in plans with the `git init`-with-approval question.
- **Deterministic execution restrictions** (`scripts/netsf/readonly.py`): a `UserPromptSubmit`
  hook records "dry run", "analysis only", "do not modify / install / commit / push / deploy"
  (English and Spanish) per session until the user says "exit dry-run"; the `PreToolUse` hook
  denies the restricted actions (full read-only: edits denied, only allow-listed read-only shell
  commands). Claude Code plan mode counts as read-only.
- Guard: `git init`, `git commit`, `git push` and tag creation ask for confirmation; risk
  assessment rates Git history/remote changes HIGH (approval required).
- **Autonomous workflow** from one request: `bridge start` returns the engineering brief in one
  call (risk, detection, scope, routing, lean context, task-focused understanding in
  `understand.py`: relevant files, existing routes, test/lint commands, docs to review) and a
  deterministic decision in `autonomy.py` (`PROCEED`, `ASK_APPROVAL`, `ASK_QUESTIONS`,
  `READ_ONLY`, `BLOCKED`), inline-or-delegate execution, phases, repair policy, report
  sections (VERIFIED / INFERRED / NOT VERIFIED) and autonomy metrics. The master skill is
  rewritten around it (~1.6k tokens on invoke, down from ~2.5k).
- Plans no longer list the parent-repository note as a question unless the task involves Git;
  it is informational and never stops the workflow.
- Bounded repair enforced by the hook: test-runner commands are counted between user prompts;
  after a baseline, a validation and 5 repair runs the next run asks for confirmation.
- Autonomy benchmark (`benchmarks/autonomy_benchmark.py`) and 12 prepared (not executed)
  `claude plugin eval` cases, including database clarification, file-only workflow, dry run
  and a single-prompt user story.
- Plugin tests changed intentionally: core compatibility range 1.3; `git commit`/`git push`
  moved from "normal" to "require confirmation"; hooks now include `UserPromptSubmit`; the
  master-skill content test expects `start --task` instead of `risk --task`; the
  parent-repository plan test asserts the note is not a question for unrelated tasks (and is
  one for Git tasks).
- `pyproject.toml`: plugin tests in `testpaths`/`pythonpath`, ruff `src`/per-file-ignores.

## [1.2.0] - 2026-10-06

MINOR release: Knowledge Graph and intelligent context selection, built on the 1.1 router
(extended, not replaced). Commands, lock schema (1) and the v1.1 JSON keys are unchanged.

### Added

- **Knowledge Graph** `.ai/context/graph.json`: 13 node types, 12 weighted edge types, derived
  from `catalog/`, `profiles/` and the installed knowledge files (rule H2 sections become CONCEPT
  nodes with line ranges). Deterministic JSON with `source_fingerprint`, validation (types,
  duplicates, references, paths, cycles), iterative depth-bounded traversal, dependency
  expansion (`context_graph.py`).
- **Task classification** into 14 categories plus technology detection (`context_rank.py`).
- **Ranking**: explainable scores in [0, 1] from task match, graph weight, profile, technology,
  dependency, token cost and redundancy; weights in `catalog/context.json` (`ranking`).
- **Relevance tiers** REQUIRED / RECOMMENDED / OPTIONAL and a **budget slicer** with tiers
  simple / normal / complex / security (`context_budget.py`). Required items are never dropped;
  over-budget is reported.
- Targeted rule sections for agents recommended by a task category (for example, security task
  → architecture sections).
- `ai-project context --rebuild-graph`; output adds routing mode, classification, budget tier,
  relevance and score with reasons, and metrics (`routing_time_ms`, selected and skipped nodes,
  files, characters, reduction). JSON adds `classification`, `classification_details`,
  `selected`, `skipped`, `metrics`, `mode`, `graph`, `estimation_method`, `budget.tier/limit`.
- `doctor`: **Knowledge Graph** section (WARN with recovery instructions, never FAIL).
- Metadata: `tasks`, `tools`, `ranking` blocks and stack relations (`depends_on`,
  `specializes`, `related`, `conflicts`) in `catalog/context.json`.
- `.ai/context/README.md` (kit-managed); `budgets` tiers in the `budget.json` template;
  index entries for technologies, databases, integrations, profiles and tools.
- Tests: `tests/test_graph.py`, `tests/test_ranking_budget.py`.

### Changed (intentional, documented)

- **Derived artefacts:** `graph.json` and `index.json` are listed in the lock's new optional
  `derived_files` and are regenerated by `update` and `--rebuild-graph`. A manual edit is
  replaced, never turned into a `.kit-new` conflict (in 1.1, `index.json` was a CORE file).
  `update` migrates 1.1 projects automatically.
- **Agent 15** is loaded for context-optimisation tasks only (it was never loaded in 1.1); normal
  tasks still never load it.
- **Graph mode** is the default when a graph is available. Weak single-word matches become
  RECOMMENDED and are ranked. For example, "Deploy service to Kubernetes" drops from 19,943 to
  11,033 estimated tokens. API tasks add targeted security rule sections.
- **Direct mode** (exact 1.1 behaviour) remains as the mandatory fallback when no graph can be
  loaded or rebuilt.
- A v1.1 `budget.json` without `budgets` keeps a single budget for every task.
- Master agent: receives the context package from the programmatic layer instead of deciding
  what to read; never reads `graph.json` to decide.
- Graph path validation resolves each parent directory once (measured: ~30 ms → ~8 ms per run on
  Windows) with the same containment guarantee.

### Tests changed (intentional behaviour changes)

- `test_router_is_never_auto_loaded` → `test_router_agent_is_loaded_only_for_context_optimisation_tasks`
  (decision D; the protection for normal tasks is kept and asserted in both modes).
- `test_customised_index_follows_kit_new_conflict_rules` →
  `test_customised_index_is_regenerated_as_a_derived_artefact` (decision C).
- `test_rule_selection_and_targeted_security_review`: asserts the v1.1 set in direct mode and
  the added targeted security sections in graph mode.
- `test_v100_project_works_and_updates`: the simulation of a 1.0 project also removes the
  derived files; it now expects `index.json` in `derived_files`.

## [1.1.0] - 2026-10-05

MINOR release: new, backward-compatible capability. Existing commands, agents, rules and
workflows are unchanged in behaviour; projects generated with 1.0.0 keep working and pick up
the new files with `ai-project update`.

### Added

- **Context & Token Optimization**: load the smallest sufficient context per task.
  - `ai-project context [--task TEXT] [--json] [--profile P] [--path DIR] [--strict]`:
    classification, selected agents, rule sections, workflow and stacks, with a reason for
    every item, estimated size, budget status and reduction against the full context.
  - Context Router: deterministic keyword classification (HIGH/MEDIUM/LOW/NONE), dependency
    levels (`requires`, `recommended`, `optional`) with cycle detection, lazy loading by layer
    (L0 core, L1 specialist, L2 technology, L3 deep review with targeted rule sections),
    rule slicing by section, deduplication.
  - Routing metadata `catalog/context.json` (data only, validated, never executed).
  - Generated `.ai/context/index.json` (CORE, tracked in `kit.lock.json`) and
    `.ai/context/budget.json` (project-owned, configurable).
  - Token estimation: characters / 4, labelled as an estimate (not provider token counts).
  - Agent `15-context-token-optimizer.md` (routing helper, never auto-loaded) in all profiles.
- `doctor`: "Context index" and "Context budget" checks (WARN only).
- `catalog/technologies.json`: `language` and `framework` fields (`TODO` when unknown).
- `docs/CONTEXT_OPTIMIZATION.md`; tests in `tests/test_context.py`.

### Changed

- Master agent: lifecycle now Understand → Classify → Select Context → Analyze → Plan → ...;
  new "Select context" section.
- `AGENTS.md` template: short "Context routing" section (lazy loading, levels, slices,
  deduplication, budget).
- `.ai/context/project.md` template: compact summary table (purpose, language, framework,
  architecture, database, deployment, testing, commands, integrations). Seed file: existing
  projects keep theirs.
- Secret scanner skips the kit-generated `.ai/kit.lock.json` and `.ai/context/index.json`
  (hashes and metadata only; a SHA-256 next to a `*token*` file name was a false positive).
- `examples/fastapi-demo` updated to 1.1.0 with `ai-project update`.

## [1.0.0] - 2026-10-05

### Added

- `ai-project` CLI (Python 3.9+, standard library only): `init`, `doctor`, `update`,
  `list`, `version`, `help`; interactive wizard and fully flag-driven mode.
- 15 agents: master orchestrator, frontend, backend, database, architecture, code quality,
  SOLID & patterns, OOP, performance, security, testing, documentation, DevOps,
  observability, code review.
- 6 rule sets with citable IDs: coding, architecture, security, testing, performance,
  documentation.
- 6 workflows: new project, new feature, bug fix, refactoring, security audit, release.
- 18 stack guides: Python, FastAPI, Django, Flask, Node.js, TypeScript, React, Angular,
  PostgreSQL, SQL Server, ClickHouse, MongoDB, Docker, Kubernetes, NGINX + uWSGI, Linux,
  CI/CD, data pipelines.
- 7 profiles: backend-api, frontend, fullstack, python-automation, data-engineering,
  microservice, custom.
- Templates: `AGENTS.md`, project context, docs skeleton with ADRs and Mermaid diagrams.
- Assistant integrations (thin pointers to `AGENTS.md`): Claude Code, GitHub Copilot, Cursor;
  Codex reads `AGENTS.md` natively.
- Lock file (`.ai/kit.lock.json`) with hashes for safe three-way updates (`.kit-new` on conflict).
- `doctor` checks: configuration, kit integrity, Git (team server), quality tooling,
  dependency locks, non-root containers, secret detection with `.env` credential alert,
  documentation.
- Example project `examples/fastapi-demo`.
