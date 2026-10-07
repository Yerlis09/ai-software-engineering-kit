# Development

## Setup

From the repository root (the core and the plugin share one repository):

```
uv venv && uv pip install -e ".[dev]"      # or: python -m venv .venv && pip install -e ".[dev]"
```

The plugin scripts use only the Python standard library (3.9+).

## Tests and checks

```
python -m pytest plugins/netsf-ai-software-engineering/tests     # plugin only
python -m pytest                                                 # core + plugin
ruff check plugins/netsf-ai-software-engineering
ruff format --check plugins/netsf-ai-software-engineering
mypy plugins/netsf-ai-software-engineering/scripts
claude plugin validate --strict plugins/netsf-ai-software-engineering
claude plugin validate --strict .
claude --plugin-dir plugins/netsf-ai-software-engineering plugin details netsf-ai-software-engineering
```

Test conventions:

- Plugin test files are named `test_plugin_*.py` and helpers live in `tests/netsf_testkit.py`.
  There is deliberately **no** plugin `conftest.py`: the core tests import helpers with
  `from conftest import ...`, and a second module named `conftest` would shadow theirs. Import
  the `kit_project` fixture explicitly: `from netsf_testkit import kit_project as kit_project`.
- `pyproject.toml` adds the plugin `scripts/` and `tests/` to `pythonpath`.
- `tests/scenarios.py` defines the 8 integration projects (Python backend, FastAPI, ClickHouse,
  automation, frontend, microservice, Docker, Kubernetes) with expected detection and routing.

## Adding a specialist

1. Make sure the knowledge exists in the core (`agents/NN-role.md` in the Kit). Do not copy it.
2. Add `agents/<role>.md` with frontmatter `name`, `description`, `tools`, and a body that calls
   `context --focus NN-role --lean`. Keep it under 2,000 characters (enforced by a test).
3. Map it in `scripts/netsf/plan.py` (`SPECIALISTS` or `CATEGORY_SPECIALISTS`).
4. Add routing expectations to `tests/scenarios.py` and update `EXPECTED_AGENTS` in
   `tests/test_plugin_structure.py`.

## Changing guard or risk rules

Add the case to the parametrised tables in `tests/test_plugin_security.py` first (dangerous and
safe examples), then change the rule. Every rule needs at least one negative test to avoid
blocking normal work.

## Versioning

See [Compatibility](COMPATIBILITY.md). Bump `version` in `.claude-plugin/plugin.json`,
`PLUGIN_VERSION` in `scripts/netsf/__init__.py` and the marketplace entry together (a test checks
they match).

## Evals

`evals/` contains prepared `claude plugin eval` cases. They have **not** been executed; running
them uses model calls on your credential and requires authorisation.
