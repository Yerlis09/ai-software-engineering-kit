# Contributing to the kit

## Development setup

```bash
git clone https://git.netsf.fr/<group>/ai-software-engineering-kit.git
cd ai-software-engineering-kit
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
ai-project version        # "Kit:" points to your checkout
```

## Checks before a merge request

```bash
pytest                    # full kit test suite
ruff check cli tests
ruff format --check cli tests
```

CI (`.gitlab-ci.yml`) runs the same on Linux with Python 3.9 and 3.12, builds the wheel and
smoke-tests the installed CLI.

## What the tests cover

| File | Scope |
|---|---|
| `test_paths_and_render.py` | Path traversal, symlink escape, name validation, renderer safety |
| `test_secrets_scan.py` | Secret patterns, placeholders, `.env` classification, exclusions |
| `test_knowledge_base.py` | Every agent has the required sections; cross-references resolve; **every profile x technology combination renders** with no unknown variable or unsafe path |
| `test_init.py` | Non-interactive and interactive init, invalid input, existing projects, `--force` |
| `test_doctor.py` | Each check, exit codes, JSON output, `.env` alert, demo project health |
| `test_update.py` | Three-way update cases, `--check`, `--dry-run`, `--force`, tampered or corrupt lock, CRLF |
| `test_cli.py` | Help, version, list, usage errors, `python -m ai_project` |
| `test_context.py` | Classification, selection (agents, rules, stacks), estimation, budget, slicing, dependencies and cycles, deduplication, explainability, CLI/JSON, empty or unknown input, legacy project update, measured reduction |
| `test_graph.py` | Knowledge graph: build, save/load, rebuild, validation (duplicates, types, missing nodes, weights, path traversal, symlinks, cycles), traversal, dependency expansion, corrupt/stale graphs, fallback, `--rebuild-graph`, doctor, derived files and 1.1 migration |
| `test_ranking_budget.py` | 14 task categories, scores and components, budget tiers and slicer, the 5 reference cases, before/after vs v1.1, L0–L3, explanations, metrics, JSON compatibility, determinism |

## Guidelines

- **Content changes** (agents, rules, workflows, stacks) are the most common contributions.
  Keep files dense and actionable; AI context windows are a budget. Reference other kit
  files with paths relative to the AI root (`rules/security.md`, never `../` or `.ai/`).
- Agents keep the standard sections (Role, Objective, Responsibilities, Rules, Inputs,
  Outputs, Validation, Forbidden behavior, Collaboration with other agents).
- **CLI changes**: standard library only; keep `cli.py` free of logic; every new behaviour gets
  tests; never add network access or process execution.
- Update `CHANGELOG.md` under `[Unreleased]`.
- After changing kit content, run `ai-project update --path examples/fastapi-demo` (a test
  checks the demo is in sync).

## Releasing

1. Move `[Unreleased]` entries to a new version in `CHANGELOG.md`; bump `__version__` in
   `cli/ai_project/__init__.py` ([VERSIONING.md](VERSIONING.md) explains MAJOR, MINOR and PATCH).
2. `ai-project update --path examples/fastapi-demo`, then run the checks above.
3. Merge, tag `vX.Y.Z` on git.netsf.fr, and announce the changelog to the teams.
