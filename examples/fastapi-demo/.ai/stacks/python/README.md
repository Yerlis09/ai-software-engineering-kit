# Stack — Python

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Python-specific guidance.

## Recommended tooling

| Concern | Tool |
|---|---|
| Lint + format | `ruff` (`ruff check`, `ruff format`) |
| Type checking | `mypy --strict` or `pyright` |
| Tests | `pytest`, `pytest-cov`, `pytest-mock`, `hypothesis` (property tests) |
| Packaging / deps | `uv` (preferred) or `pip-tools`; lock files committed |
| Security | `pip-audit` (dependencies), `bandit` (SAST), secret scanner in CI |
| Config | `pydantic-settings` (typed settings from environment) |

Configure everything in `pyproject.toml`. Pin the Python version (`requires-python`, `.python-version`).

## Project structure

```
src/<package>/
  api/             # Controller: HTTP/CLI entry points, request/response schemas
  application/     # Use cases / services, orchestration, transactions
  domain/          # Entities, value objects, domain errors (no framework imports)
  repositories/    # Repository interfaces + implementations
  infrastructure/  # DB engine, external clients, messaging, settings
  main.py          # Composition root (wiring / dependency injection)
tests/
  unit/  integration/  conftest.py
pyproject.toml  uv.lock  Dockerfile  .env.example
```

Use the `src/` layout so tests run against the installed package. Dependencies point inward: `domain` imports nothing from other layers (see `rules/architecture.md`).

## Conventions

- PEP 8 via `ruff format`; type hints on all public functions; `from __future__ import annotations` where useful.
- Use `dataclasses` (frozen for value objects) or Pydantic models at boundaries; do not pass raw dicts across layers.
- Raise specific exceptions (domain errors) and translate them to HTTP/CLI errors in the controller layer only.
- Use `logging` (structured JSON in production), never `print`. Get loggers with `logging.getLogger(__name__)`.
- Use `pathlib`, f-strings, context managers (`with`) for every resource (files, connections, locks).
- Keep functions small; avoid mutable default arguments; prefer composition over inheritance (`agents/07-oop.md`).
- Inject dependencies through constructors or function parameters; no module-level singletons holding I/O clients.

## Security

- **Team policy: `.env` files containing real credentials are strongly discouraged.** Never commit them, never bake them into images. Use Kubernetes Secrets (via Sealed Secrets / External Secrets), a vault, or masked CI variables.
- Commit only `.env.example` with placeholders (`DB_PASSWORD=changeme`), and keep `.env` in `.gitignore` and `.dockerignore`.
- Read configuration from the environment through a typed settings object; fail fast on missing values.
- Never use `eval`, `exec`, `pickle`/`shelve` on untrusted data, `yaml.load` (use `yaml.safe_load`), or `subprocess(..., shell=True)` with user input.
- Use parameterized queries / ORM bindings; never build SQL with f-strings.
- Use `secrets` (not `random`) for tokens; hash passwords with `argon2` or `bcrypt`.
- Run `pip-audit` and `bandit` in CI; see `rules/security.md` and `agents/09-security.md`.

## Performance

- Measure first (`cProfile`, `py-spy`, `pytest-benchmark`); see `rules/performance.md`.
- Use generators/iterators for large data; avoid loading whole files or result sets into memory.
- Prefer built-ins, comprehensions, `collections`, `itertools`; vectorize numeric work (NumPy/Polars).
- I/O-bound concurrency: `asyncio` or threads; CPU-bound: `multiprocessing` / process pools.
- Reuse HTTP sessions and DB connection pools; set explicit timeouts on every network call.
- Cache pure, expensive computations with `functools.lru_cache` / `cache` (bounded).

## Testing

- `pytest` with fixtures in `conftest.py`; unit tests must not hit network or DB.
- Integration tests use real dependencies via containers (e.g. Testcontainers) or a dedicated test DB.
- Enforce coverage threshold with `pytest --cov=src --cov-fail-under=80` (adjust per `rules/testing.md`).
- Mock at boundaries (repositories, clients), not internals; use `freezegun`/injected clocks for time.

## Pitfalls

- Mutable default arguments (`def f(x=[])`).
- Bare `except:` or `except Exception: pass` swallowing errors.
- Circular imports caused by business logic in `__init__.py`.
- Mixing sync blocking calls (e.g. `requests`, `time.sleep`) inside `async` code.
- Unpinned dependencies or a lock file not committed.
- Naive datetimes; always use timezone-aware UTC (`datetime.now(tz=UTC)`).
- Credentials in `.env`, source code, notebooks or logs.

## Example

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    database_url: str
    database_password: SecretStr  # injected from a Kubernetes Secret / CI variable
    log_level: str = "INFO"
    request_timeout_s: float = 5.0


settings = Settings()  # raises ValidationError if a required variable is missing
```
