# Context & Token Optimization

> Principle: **load the minimum context required to complete the task correctly.**
> Priority order: correctness > security > architecture > testing > maintainability >
> context efficiency > token optimization. Optimisation never removes security or tests.

All token figures in this document are **estimates** (`characters / 4`, method
`characters_div_4`), not the token count of any AI provider. The kit does not measure or
control the tokens billed by Claude, OpenAI, Codex, Cursor, Copilot or anyone else.

## 1. Why context optimization

A generated backend-API project ships up to 16 agents, 6 rule sets, 6 workflows and several stack
guides, which comes to about 44,000 estimated tokens. An assistant that reads everything for
every task spends most of its context window on documents unrelated to the task. Large contexts
cost more, are slower, and dilute attention. The kit therefore selects context **before** the
assistant starts working.

## 2. Existing v1.1 architecture (kept)

Version 1.1 introduced a deterministic **context router**:

- keyword triggers per agent and agent levels (HIGH / MEDIUM / LOW / NONE);
- dependency propagation (`requires`, `recommended`, `optional`) with cycle detection;
- context levels L0–L3 and lazy loading;
- rule slicing by H2 section and deduplication;
- a budget per phase, an explanation for every decision, and the `index.json` index.

v1.2 keeps all of it. The v1.1 logic is now the router's **direct mode**, which is the
mandatory fallback.

## 3. Knowledge Graph

`.ai/context/graph.json` is a local, weighted graph of the kit's knowledge. It is a **map**, the
router is the **navigator**, the budgeter decides **how much** context fits, and the slicer
picks **only the relevant parts**.

- **Derived and regenerable.** The sources of truth remain `agents/`, `rules/`, `workflows/`,
  `stacks/`, `profiles/`, `catalog/` and `templates/`. Delete the graph and it is rebuilt.
- **Data only.** It is parsed and validated, never executed.
- **Deterministic.** Nodes and edges are sorted, there are no timestamps, and each node or edge
  takes one line. The result is stable in Git.
- **Fingerprinted.** `source_fingerprint` hashes the routing metadata, the kit version, the
  project selection and the hashes of the knowledge files in the lock file. A different value
  means *stale*.
- **No database.** It is plain JSON read by the standard library, with no Neo4j, Redis or vector
  store.

A typical backend-API project graph has **157 nodes and 483–484 edges** (measured).

## 4. Nodes

| Type | Example id | Built from |
|---|---|---|
| TASK | `task.api` | `catalog/context.json` → `tasks` (14 categories) |
| AGENT | `agent.02-backend` | `catalog/context.json` → `agents`, file `.ai/agents/*.md` |
| RULE | `rule.security` | `rules`, file `.ai/rules/*.md` |
| CONCEPT | `concept.security.secrets-management` | each H2 section of an installed rule, with its line range |
| WORKFLOW | `workflow.bug-fix` | `workflows` |
| STACK | `stack.fastapi` | `stacks` |
| TECHNOLOGY | `technology.python-fastapi`, `technology.deploy-kubernetes` | `catalog/technologies.json`, `catalog/deployments.json` |
| DATABASE | `database.clickhouse` | `catalog/databases.json` |
| TOOL | `tool.pytest` | `catalog/context.json` → `tools` |
| PROFILE | `profile.backend-api` | `profiles/*.json` |
| PROJECT | `project.billing-api` | the project's lock file |
| FILE | `file.agents-md` | `AGENTS.md`, `.ai/context/project.md` |
| INTEGRATION | `integration.claude-code` | `catalog/assistants.json` |

## 5. Edges

All edges have a `weight` between 0 and 1, which the ranking uses.

| Type | Example | Weight |
|---|---|---|
| requires | `agent.02-backend → agent.04-architecture` | 1.0 (HIGH), 0.7 (MEDIUM), 0.4 (LOW) |
| recommends | `task.api → agent.09-security` | from metadata |
| optional | `agent.02-backend → agent.08-performance` | 0.2 |
| depends_on | `stack.kubernetes → stack.docker` | 0.9 |
| specializes | `stack.fastapi → stack.python` | 1.0 |
| related_to | `stack.kubernetes → stack.ci-cd` (0.5), `rule.security → concept.*` | from metadata |
| conflicts_with | `stack.fastapi → stack.django` | 0.2 (used as a redundancy penalty) |
| implemented_by | `stack.fastapi → agent.02-backend` | 0.6 |
| validated_by | `agent.10-testing → tool.pytest` | 0.5 |
| uses | `technology.python-fastapi → stack.fastapi` | 0.9 |
| belongs_to | `rule.coding → agent.02-backend`, `tool.pytest → stack.python` | 0.8–1.0 |
| extends | (supported for future use) | |

Cycles among dependency edges (`requires`, `depends_on`, `specializes`) are errors.
`related_to` cycles are allowed: traversal is depth-bounded and stops re-expanding a node unless
it finds a strictly better weight.

## 6. Graph generation

The graph is generated, never hand-maintained, by a hybrid of static metadata
(`catalog/context.json`), profiles, catalogs, rule sections and agent metadata. It is built:

- by `ai-project init` (written with the other files);
- by `ai-project update` (regenerated, never a `.kit-new` conflict);
- by `ai-project context --rebuild-graph` (regenerated, validated, saved);
- in memory, automatically, when the saved graph is missing, corrupt or stale.

## 7. Task classification

Each category has weighted triggers. A category is detected at a score of 2 or more, so weak
words alone do not classify a task. Technologies are detected from strong stack triggers. The
classification is deterministic, uses no LLM, and is testable.

Categories: `new_project`, `new_feature`, `bug_fix`, `refactoring`, `security`, `testing`,
`performance`, `database`, `api`, `frontend`, `backend`, `deployment`, `documentation`,
`release`.

| Task | Classification (measured) |
|---|---|
| Create a FastAPI endpoint for equipment | new_feature, api, backend, fastapi |
| Fix ClickHouse query | database, bug_fix, clickhouse |
| Audit authentication security | security |
| Refactor a Python service | refactoring, backend, python |
| Deploy service to Kubernetes | deployment, kubernetes ("service" alone does not mean backend) |

Each category `requires` agents (making them REQUIRED), `recommends` agents (graph weight), and
points to a related workflow.

## 8. Context Router

There is one router (`context_router.py`) with two modes:

- **graph mode (v1.2)**: classify the task, raise the agents its categories require,
  propagate dependencies, traverse the graph, rank, apply the budget, slice;
- **direct mode (v1.1)**: metadata only. It is used whenever the graph cannot be loaded or
  rebuilt.

Each candidate gets a **relevance**:

- **REQUIRED**: a strong task match (score of 2 or more), required by a task category, required
  (`requires` at MEDIUM or higher) by a REQUIRED agent, named in the task, a dependency of a named
  stack, or a **protected** agent (security, testing) at MEDIUM or higher. Always loaded.
- **RECOMMENDED**: a weak match, a `recommends` edge, or a stack of an active domain that the
  task does not name. Loaded if its score is at least `min_recommended_score` (0.30) and the
  budget allows.
- **OPTIONAL**: LOW level or `optional` edges. Listed, never loaded.

A task category that recommends an agent with weight 0.5 or more, when that agent is not loaded,
brings in that agent's **rule sections** (a targeted review). For example, a security task adds
the architecture rule sections, and an API task adds the security rule sections.

## 9. Ranking

```text
score = 0.35·task_match + 0.30·graph_weight + 0.05·profile_match + 0.20·technology_match
      + 0.15·dependency_bonus − 0.05·token_cost − redundancy_penalty      (clamped to [0, 1])
```

| Component | Meaning (each in [0, 1]) |
|---|---|
| task_match | trigger score / 3, or 1.0 if a task category requires it |
| graph_weight | best product of edge weights from the seeds (task categories, REQUIRED agents, named stacks), depth ≤ 3 |
| profile_match | the project's profile includes the agent (or installed the stack) |
| technology_match | the project's technology or database uses the stack (infrastructure guides excluded: their relevance comes from the task) |
| dependency_bonus | required by a REQUIRED agent (1.0), recommended by one (0.5); stacks of a required domain (0.5) |
| token_cost | estimated tokens / `max_agent_context` (or `max_stack_context`) |
| redundancy_penalty | 0.2 when the stack conflicts with a REQUIRED stack |

The weights, threshold, protected agents, depth and `category_rule_weight` are configurable in
`catalog/context.json` (`ranking`). Every score comes with its components and reasons.

## 10. Token budget

`.ai/context/budget.json` is project-owned and editable.

| Key | Default | Meaning |
|---|---|---|
| `budgets.simple` | 12,000 | one category, no deep review |
| `budgets.normal` | 16,000 | two or more categories |
| `budgets.complex` | 24,000 | new project, three or more domains, or a deep review (performance, observability, code review) |
| `budgets.security` | 24,000 | any security task |
| phase budgets, `max_agent_context`, `max_stack_context` | as in v1.1 | per phase and per file |

The defaults were calibrated on the measured reference tasks (section 17). The L0 core alone
(entry point, project summary and master) is about 4,100 estimated tokens, so very small tiers
would always be over budget.

**Backward compatibility:** a v1.1 `budget.json` (no `budgets` block) keeps its v1.1 meaning:
`default_token_budget` applies to every tier. Existing projects keep that until they add a
`budgets` block (copy it from the template in the kit).

## 11. Context slicing

The budget slicer works on the candidates:

- **REQUIRED** items are always kept, even over budget. The status is then `OVER_BUDGET` and is
  reported; the problem is never hidden.
- **RECOMMENDED** items are kept by descending score while they reach the threshold and fit. A
  recommended agent left out also drops its rule sections and domain stacks.
- **OPTIONAL** items are listed only.

Rule files are sliced by H2 section. Each section is a CONCEPT node with its line range, and the
package lists the selected concept ids. Example: for "Audit authentication security", the
package loads the *Authentication and authorization* section of `security.md`, not *Files,
paths and network*. Each file and section is loaded once (deduplication), and every requester
is recorded.

## 12. L0–L3

| Level | Content | Loaded |
|---|---|---|
| L0 core | `AGENTS.md`, `.ai/context/project.md`, master agent | always |
| L1 specialist | backend, frontend, database, architecture, testing… | when selected |
| L2 technology | stack guides | when their domain is active or the task names them |
| L3 deep review | security, performance, observability, code review | in full only when the task is about them, otherwise targeted rule sections |

## 13. Explainability

Every selected item carries relevance, score, score components and reasons. Every skipped item
carries a reason. Typical reasons:

- `task matched: kubernetes, deploy`
- `required by task category deployment`
- `domain of required agent 12-devops`
- `graph: reached from stack.kubernetes (weight 0.90)`
- `profile backend-api includes it`
- `protected: security and tests are never dropped for budget`
- `RECOMMENDED but low relevance: score 0.25 < threshold 0.30`
- `RECOMMENDED but left out: budget: +1,264 would exceed the tier limit 12,000 (at 10,920)`
- `Not related to the task (not installed in this profile)`

## 14. Fallback

1. Load `graph.json`, then validate its structure, types, references, cycles, paths and
   fingerprint.
2. If it is missing, invalid or stale, warn *"Knowledge graph is missing/stale. Rebuild
   recommended with --rebuild-graph."* and **rebuild it in memory** from the sources.
3. If the rebuild fails, or there is no lock file, use **direct routing (v1.1)**.

A graph failure is never a kit failure.

## 15. Graph validation

`ai-project doctor` has a **Knowledge Graph** section: graph exists, structure, node and edge
types, references, project paths, no cycles, source fingerprint. A missing, corrupt or stale
graph is a **WARN** with a recovery instruction, never a FAIL. Paths must be relative and under
`.ai/` (or be `AGENTS.md`). `../../secret.txt`, absolute paths, drive letters and symlinks that
lead outside the project are rejected.

## 16. CLI

```bash
ai-project context                                     # L0 only
ai-project context --task "Create a FastAPI endpoint"  # selection, scores, reasons
ai-project context --task "Fix ClickHouse query" --json
ai-project context --profile backend-api --task "..."  # simulate a profile (nothing written)
ai-project context --rebuild-graph                     # regenerate + validate + save graph.json
ai-project context --task "..." --strict               # exit 1 when over budget
```

`--json` prints only JSON. The v1.1 keys are unchanged, and v1.2 adds `classification`,
`classification_details`, `selected`, `skipped`, `metrics`, `mode`, `graph`,
`estimation_method` and `budget.tier/limit/estimated_tokens`. With `--rebuild-graph`, the JSON
has a `graph_rebuild` object.

Real output, abridged (demo project, `ai-project context --task "Deploy service to Kubernetes"`):

```text
Routing: knowledge graph: loaded, 157 nodes, 483 edges
Classification: deployment, kubernetes
Selected agents:
✓ 10-testing - [REQUIRED, score 0.33] profile backend-api includes it; protected: security and tests are never dropped for budget
✓ 12-devops - [REQUIRED, score 0.68] task matched: kubernetes, deploy; required by task category deployment
Skipped:
○ 02-backend - RECOMMENDED but low relevance: score 0.23 < threshold 0.30 (task matched: service; ...)
Stack guides:
✓ docker - [REQUIRED, score 0.37] dependency of a stack named in the task; graph: reached from stack.kubernetes (weight 0.90)
✓ kubernetes - [REQUIRED, score 0.63] named in the task: kubernetes; domain of required agent 12-devops
○ ci-cd - RECOMMENDED but low relevance: score 0.25 < threshold 0.30
```

## 17. Metrics

These are measured on every run and reported in the CLI output and in the JSON. No history is
stored.

`routing_time_ms`, `full_context_tokens`, `optimized_context_tokens`,
`context_reduction_percentage` = `(full − optimized) / full × 100`, `selected_nodes`,
`selected_rule_sections`, `skipped_nodes`, `files_selected`, `characters_selected`,
`classification`, `budget_tier`, `status`, `mode`.

### Before (v1.1 direct) and after (v1.2 graph): measured examples

Simulated backend-API projects (Python + FastAPI, deployment Kubernetes) with the v1.2 template
budget. Estimated tokens.

| Task | DB | v1.1 tokens / files | v1.2 tokens / files | Full | v1.2 reduction | Tier |
|---|---|---|---|---|---|---|
| Create a FastAPI endpoint for equipment | postgresql | 13,109 / 13 | 13,109 / 13 | 44,242 | 70.4% | normal |
| Fix ClickHouse query | clickhouse | 14,679 / 14 | 14,679 / 14 | 44,351 | 66.9% | normal |
| Audit authentication security | postgresql | 10,286 / 9 | 10,652 / 10 | 44,242 | 75.9% | security |
| Refactor a Python service | postgresql | 13,639 / 13 | 13,639 / 13 | 44,242 | 69.2% | normal |
| Deploy service to Kubernetes | none | 19,943 / 18 | **11,033 / 10** | 41,923 | 73.7% (v1.1: 52.4%) | simple |

- **Example 1, "Create a FastAPI endpoint for equipment".** Backend, architecture and testing
  are REQUIRED; so are FastAPI (named) and Python (FastAPI specializes Python). Security
  contributes targeted rule sections. Frontend, React and Angular are skipped.
- **Example 2, "Fix ClickHouse query".** Database, backend and testing are REQUIRED, and so is
  ClickHouse. FastAPI is RECOMMENDED (score 0.30) and kept. Performance and security are
  OPTIONAL.
- **Example 3, "Audit authentication security".** Security (loaded in full as an L3 deep
  review) and testing are REQUIRED. Only the *Secure by design* and *Authentication and
  authorization* sections of `security.md` are loaded, plus targeted architecture sections
  (+366 tokens versus v1.1, deliberately: relevant architecture).
- **Example 4, "Refactor a Python service".** Quality, backend, architecture, testing and Python
  are REQUIRED. FastAPI is only **RECOMMENDED** (0.30), not required because the project
  happens to use it.
- **Example 5, "Deploy service to Kubernetes".** DevOps, testing (protected), Kubernetes and
  Docker (`depends_on`) are REQUIRED. Backend (0.23) and architecture (0.03) are RECOMMENDED but
  below the threshold. Linux (0.21), NGINX (0.19) and CI/CD (0.25) are RECOMMENDED but below the
  threshold. Python (0.45) is left out by the *simple* tier budget. The estimated context drops
  by 45%.

Absolute figures were measured with kit 1.2.0 on 2026-10-06. The selections and the
relative before/after comparisons (never more context than v1.1 except targeted rule sections;
strictly less for the Kubernetes case) are asserted by `tests/test_ranking_budget.py`.

## 18. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Knowledge graph is missing/stale" | project generated by an older kit, sources changed, or the graph was deleted | `ai-project update` or `ai-project context --rebuild-graph` |
| `Routing: direct (v1.1 fallback)` | no lock file, or the graph could not be rebuilt | check the warning; `ai-project doctor` |
| An expected agent or stack is skipped | low score or budget | read its reason; widen the budget tier, add a trigger, or name the technology in the task |
| Too much context | weak words matching | tune `catalog/context.json` (triggers, `min_recommended_score`) and re-measure |
| Edited `graph.json` or `index.json` reverted | they are derived artefacts | change the sources (`catalog/`, `agents/`...) instead |
| Doctor: "Source fingerprint – graph is stale" after editing an agent locally | the fingerprint uses the lock-file hashes | `ai-project context --rebuild-graph` |

## 19. Backward compatibility

- All commands (`init`, `doctor`, `update`, `version`, `help`, `list`) and the v1.1 JSON keys are
  unchanged.
- **Projects from 1.0 or 1.1 without `graph.json`:** the graph is rebuilt in memory with a
  warning. `update` writes `graph.json`, moves `index.json` from `managed_files` to
  `derived_files` (an optional lock field; schema still 1), adds `.ai/context/README.md`, and
  produces no conflict.
- **v1.1 `budget.json`:** works as before (single budget).
- **Derived files:** a manual edit of `graph.json` or `index.json` is replaced on `update`. This
  is intentional: they are not sources of truth, so turning them into `.kit-new` conflicts would
  ask humans to merge generated data.
- **Agent 15:** loaded only for context-optimisation tasks (for example "Improve context routing
  to reduce tokens"), never for normal tasks.

## 20. Future evolution (not implemented)

| Stage | Content | Status |
|---|---|---|
| V1 | JSON index + rule-based router | v1.1 |
| V2 | weighted graph + task classification + ranking + budget tiers + slicing | **this version (v1.2)** |
| V3 | graph + embeddings + hybrid search | not implemented |
| V4 | graph + vector database + learning from task history | not implemented |

The ranking already isolates its signals as components. A future `semantic_match` component
(embeddings) could be added with a weight, without changing the router or the package format,
when measurements justify it.

## Limitations

- Classification uses English keywords. Tasks written in other languages match only on
  technical terms.
- Token figures are estimates, not provider counts.
- The fingerprint uses lock-file hashes, so a locally edited agent needs `--rebuild-graph` to
  refresh the graph's sizes. The CLI always re-reads the files it selects.
- Assistants follow the package by convention. The kit cannot prevent an assistant from reading
  other files.
