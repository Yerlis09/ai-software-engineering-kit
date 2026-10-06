# Stack — Flask

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Flask-specific guidance.

See also `stacks/python/README.md` and `stacks/nginx/README.md`.

## Recommended tooling

- Lint/format: `ruff`; types: `mypy` or `pyright`.
- Tests: `pytest`, `pytest-cov`, Flask `app.test_client()`.
- Package manager: `uv` or `pip-tools`; security: `pip-audit`, `bandit`.
- Common extensions: SQLAlchemy 2.x (+ Flask-SQLAlchemy optional), Alembic / Flask-Migrate, Pydantic or marshmallow for validation, Flask-WTF (CSRF) for forms.

## Serving model

Flask is a **WSGI** app, served by **uWSGI behind NGINX** (team standard, `uwsgi_pass`). Expose a module-level `app = create_app()` in `wsgi.py` for uWSGI (`module = app.wsgi:app`). Never use `flask run` / the Werkzeug dev server outside local development.

## Project structure

```
src/app/
  __init__.py          # create_app(config): register blueprints, extensions, error handlers
  wsgi.py              # app = create_app()  (uWSGI entry point)
  api/<feature>.py     # Controller: Blueprints, request parsing, response mapping
  schemas/             # Pydantic/marshmallow models
  application/         # Use cases / services
  domain/              # Entities, domain errors (no Flask imports)
  repositories/        # Data access
  infrastructure/      # DB session, clients, settings
tests/  migrations/  uwsgi.ini  pyproject.toml
```

## Conventions

- Application factory pattern; no global `app` used across modules (use `current_app` sparingly).
- Blueprints per feature, registered with a URL prefix (`/api/v1/...`).
- Validate every input explicitly (Flask does not do it for you); return consistent JSON error bodies.
- Register error handlers (`@app.errorhandler(DomainError)`) to translate domain errors into HTTP responses.
- Scope DB sessions per request and remove them in `teardown_appcontext`.
- Load configuration from environment via a typed settings object; `app.config.from_mapping(settings.model_dump())`.

## Security

- `SECRET_KEY` from a Kubernetes Secret; `DEBUG=False` and never enable the Werkzeug debugger in Staging/Prod (it allows remote code execution).
- Cookies: `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE="Lax"`.
- CSRF protection (Flask-WTF) for cookie-authenticated forms.
- Jinja2 autoescape stays on; never `|safe` or `Markup()` on user input; never `render_template_string` with user data (SSTI).
- Use `ProxyFix` with the exact number of proxies when behind NGINX/ingress.
- Use `send_from_directory` / `secure_filename` for file access and uploads.

## Performance

- Tune uWSGI `processes`/`threads` rather than adding app-level concurrency hacks.
- Use connection pooling (SQLAlchemy engine) created once per process (uWSGI `lazy-apps = true` avoids sharing connections across forks).
- Cache expensive reads (Flask-Caching + Redis); paginate list endpoints.
- Offload long tasks to a worker (Celery/RQ) or Kubernetes Job.

## Testing

- Fixture creates the app with a test config: `app = create_app(TestSettings())`, then `app.test_client()`.
- Unit-test services without Flask; integration-test blueprints with a real DB container.

## Pitfalls

- Circular imports from a global `app` object; use the factory + blueprints.
- Opening DB connections at import time (shared across uWSGI forks → corrupted connections).
- Using `flask run` or `app.run(debug=True)` in containers.
- Missing input validation and inconsistent error formats.

## Example

```python
from flask import Blueprint, jsonify

bp = Blueprint("users", __name__, url_prefix="/api/v1/users")


@bp.get("/<int:user_id>")
def get_user(user_id: int):
    user = get_user_service().get(user_id)  # raises UserNotFound -> 404 via error handler
    return jsonify(UserRead.model_validate(user, from_attributes=True).model_dump())
```
