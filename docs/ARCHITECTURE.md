# Architecture of the kit

## Design goals

1. **Knowledge is data**: agents, rules, workflows, stacks, profiles and templates are
   Markdown and JSON. Most changes to the kit need no code.
2. **Vendor-neutral**: one knowledge base and one entry point (`AGENTS.md`). Assistant
   integrations are thin pointer files.
3. **Safe by construction**: no code execution from templates, no network access, every
   written path validated, and existing files never silently overwritten.
4. **Updatable**: projects receive kit improvements without losing their customisations.
5. **Small**: standard-library Python (about 2,300 lines including docstrings), with no runtime dependencies.

## Repository layout

```text
ai-software-engineering-kit/
├── cli/ai_project/        # the CLI (Python package)
├── agents/                # 15 agent roles               ┐
├── rules/                 # 6 rule sets                  │ copied verbatim into
├── workflows/             # 6 workflows                  │ <project>/.ai/
├── stacks/<tech>/         # 18 stack guides              ┘
├── profiles/*.json        # what each project type receives
├── catalog/*.json         # technologies, databases, deployments, assistants, organisation,
│                          # context.json = routing metadata (triggers, layers, dependencies)
├── templates/
│   ├── manifest.json      # which template outputs are CORE
│   ├── base/              # AGENTS.md, .ai/README.md, context, docs skeleton, dotfiles
│   └── <profile>/         # overlays (architecture docs with relevant diagrams)
├── integrations/<tool>/files/   # CLAUDE.md, copilot-instructions.md, cursor rule
├── examples/fastapi-demo/ # generated with the CLI, then developed
├── tests/                 # tests of the kit itself
└── docs/
```

The wheel bundles the knowledge directories under `ai_project/_kit/` (see `pyproject.toml`).
At runtime the CLI looks for the kit in this order: `$AI_KIT_HOME`, the bundled copy, then
the source checkout.

## CLI modules

```mermaid
flowchart TB
    cli[cli.py<br/>argparse, dispatch, exit codes] --> init[init_cmd.py]
    cli --> doctor[doctor.py]
    cli --> update[updater.py]
    init --> gen[generator.py<br/>file plan + safe writes]
    update --> gen
    gen --> catalog[catalog.py<br/>profiles, selection resolution]
    gen --> render[render.py<br/>non-executing substitution]
    init --> lock[lockfile.py<br/>hashes, schema]
    update --> lock
    doctor --> lock
    doctor --> scan[secrets_scan.py]
    gen --> paths[paths.py<br/>safe_join, validation, kit location]
    lock --> paths
    init --> console[console.py<br/>output + prompts, injectable]
```

| Module | Responsibility |
|---|---|
| `cli.py` | Parse arguments, dispatch, map `KitError` to exit codes. No business logic. |
| `catalog.py` | Load profiles and catalogs; resolve a `Selection` into agents, rules, workflows and stacks; validate choices. |
| `generator.py` | Build the file plan (CORE vs SEED), render templates, write with conflict handling. |
| `render.py` | `{{ variable }}` substitution only, single pass, unknown variable is an error. |
| `lockfile.py` | Read and write `.ai/kit.lock.json`; line-ending-insensitive hashing; SemVer parsing. |
| `updater.py` | Three-way update between the lock base, local files and the new kit. |
| `doctor.py` | Independent checks producing PASS, WARN, FAIL or INFO; text and JSON output. |
| `secrets_scan.py` | Heuristic secret detection and `.env` classification. |
| `paths.py` | Path safety, project-name validation, text sanitising, kit location. |
| `context_index.py` | Token estimate (characters / 4), H2 section split, routing-metadata validation (cycles), `.ai/context/index.json`. |
| `context_router.py` | Context Router: classification, dependency levels, lazy loading by layer, rule slicing, deduplication, budget. |
| `context_cmd.py` | `ai-project context`: project or simulated source, graph load/rebuild/fallback, `--rebuild-graph`, text/JSON output. |
| `context_graph.py` | Knowledge graph (v1.2): nodes/edges, build from sources, validation, iterative traversal, dependency expansion, fingerprint, save/load. |
| `context_rank.py` | Task classification (14 categories) and explainable scores in [0, 1]. |
| `context_budget.py` | Budget limits and tiers (simple/normal/complex/security), budget slicer. |
| `console.py` | Output (colours, ASCII fallback) and prompts (bounded retries). |

Dependencies point one way: commands depend on the generator and lock file, and those depend
on `paths`. `console` and `catalog` are injected, which keeps every command testable in-process.

## Generated project model

```mermaid
flowchart LR
    subgraph CORE[CORE - kit-managed, hashed in kit.lock.json]
        A[AGENTS.md]
        B[.ai/agents, rules, workflows, stacks]
        C[.ai/README.md, .ai/context/README.md]
        D[CLAUDE.md, copilot, cursor pointers]
    end
    subgraph OWNED[Project-owned - created once, never touched]
        E[.ai/context/project.md, budget.json]
        F[.ai/custom/]
        G[README.md, docs/, .gitignore, .env.example]
        H[src/, tests/, deploy/ skeleton]
    end
```

`init` writes both kinds. `update` only touches CORE files, and creates project-owned
files that are new in the kit, never recreating ones you deleted.

## Data flow of `init`

```mermaid
sequenceDiagram
    participant U as Developer
    participant C as CLI
    participant K as Catalog
    participant G as Generator
    participant FS as Project directory
    U->>C: answers / flags
    C->>C: validate name and target
    C->>K: resolve(selection)
    K-->>C: agents, rules, workflows, stacks
    C->>G: build_plan(selection, answers)
    G-->>C: [PlannedFile(path, content, managed)]
    C->>FS: apply_plan (safe_join, no silent overwrite)
    C->>FS: write .ai/kit.lock.json (hashes of CORE files)
```

## Context routing

`ai-project context` selects the minimum context per task; the master agent receives that
package instead of reading every file.

```mermaid
flowchart LR
    task([Task]) --> classify[Task classifier]
    classify --> graph[(Knowledge graph<br/>graph.json, derived)]
    graph --> router[Context router]
    router --> rank[Ranker] --> budget[Budget slicer] --> pkg[Context package]
    pkg --> master[Master agent]
    pkg -.-> metrics[Metrics + explanations]
    router -. graph unavailable .-> direct[Direct v1.1 routing]
```

Metadata lives in `catalog/context.json` (agents, rules, stacks, `tasks`, `tools`, `ranking`).
Each project gets `graph.json` and `index.json` (**derived**: listed in the lock's
`derived_files`, regenerated by `update` and `--rebuild-graph`, never conflicts) and
`budget.json` (project-owned). See [CONTEXT_OPTIMIZATION.md](CONTEXT_OPTIMIZATION.md).

## Key decisions

| Decision | Rationale |
|---|---|
| Python, standard library only | Available everywhere in the team, cross-platform, nothing to audit or break |
| JSON for profiles and catalogs | Parsed by the standard library on Python 3.9+ (TOML needs 3.11) |
| Own 30-line renderer instead of Jinja2 | No code execution in templates, no dependency |
| Copy files, not symlinks | Works on Windows without privileges and survives Git |
| Hash the content the kit wrote | A precise three-way merge base, without storing old file contents |
| Hash with LF-normalised content | Git `autocrlf` on Windows does not create false "modifications" |
| Dotfile templates named `dot-*` | A real `.gitignore` under `templates/` would apply to the kit repo itself |
| Keyword router, not an LLM | Deterministic, explainable, offline, vendor-neutral; the master can widen the context |
| Tokens = characters / 4 | No tokenizer dependency; clearly labelled as an estimate |
| Budgets reported, never auto-trimmed | Dropping security or tests to fit would invert the priority order |
| Knowledge graph as derived JSON (v1.2) | Local, portable, regenerable; no external database; sources of truth unchanged |
| Graph/index are derived, not CORE | Regenerated data should not become `.kit-new` merge conflicts |
| Direct v1.1 routing kept as fallback | A graph failure must never be a kit failure |
