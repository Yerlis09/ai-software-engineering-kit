# Stack — Django

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Django-specific guidance.

See also `stacks/python/README.md` and `stacks/nginx/README.md`.

## Recommended tooling

- Lint/format: `ruff` (enable the `DJ` rules); types: `mypy` + `django-stubs` (or `pyright`).
- Tests: `pytest`, `pytest-django`, `pytest-cov`, `factory_boy`.
- Package manager: `uv` or `pip-tools`; security: `pip-audit`, `bandit`, `python manage.py check --deploy`.
- API: Django REST Framework (DRF) when exposing JSON APIs.
- Debug locally: `django-debug-toolbar` (never in Prod).

## Serving model

Django is served as a **WSGI** app by **uWSGI behind NGINX** (team standard). NGINX serves `/static/` and `/media/` directly and forwards the rest with `uwsgi_pass`. If you need ASGI features (websockets), use an ASGI server (uvicorn/daphne) instead of uWSGI for that service.

## Project structure

```
src/
  config/               # settings/ (base.py, staging.py, prod.py), urls.py, wsgi.py
  apps/<feature>/
    views.py | api/      # Controller: views / DRF viewsets, serializers
    services.py          # Application: use cases, transactions
    domain.py            # Domain rules, value objects (no ORM/HTTP imports when possible)
    selectors.py         # Read queries (repository role)
    models.py            # ORM models (infrastructure/persistence)
    migrations/  admin.py  tests/
manage.py  uwsgi.ini  pyproject.toml
```

Keep business logic out of views, serializers, models' `save()` and signals; put it in services.

## Conventions

- Split settings per environment; read secrets and env-specific values from environment variables (typed settings or `django-environ`), never hard-code.
- One app per bounded feature; avoid cross-app model imports where a service call suffices.
- Custom user model from day one (`AUTH_USER_MODEL`).
- Wrap multi-write operations in `transaction.atomic()`; use `select_for_update()` for concurrency-sensitive rows.
- Migrations are committed, reviewed and reversible; never edit an applied migration. Separate schema and data migrations.
- Run migrations as a Kubernetes Job / pre-deploy step, not at container start in every replica.

## Security

- Prod: `DEBUG=False`, explicit `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER` (TLS terminated at NGINX/ingress).
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_CONTENT_TYPE_NOSNIFF`.
- `SECRET_KEY` from a Kubernetes Secret; never in git or `.env` committed files.
- Keep CSRF middleware on; never `@csrf_exempt` for session-authenticated views.
- Avoid `raw()`/`extra()`/`RawSQL` with string formatting; use parameters. Never `mark_safe` user input.
- Restrict admin (`/admin/` path change, IP allowlist at NGINX, MFA).
- Run `manage.py check --deploy` in CI.

## Performance

- Kill N+1 queries: `select_related` (FK) and `prefetch_related` (M2M/reverse). Assert with `django_assert_num_queries`.
- Use `.only()/.values()` for narrow reads, `bulk_create`/`bulk_update` for batches, `iterator()` for large scans.
- Add DB indexes (`Meta.indexes`) for filtered/ordered fields; check with `EXPLAIN`.
- Cache with Redis (`django.core.cache`); persistent connections via `CONN_MAX_AGE` (tune with uWSGI process count).
- Long work goes to a task queue (Celery/RQ) or a Kubernetes Job, not request handlers.

## Testing

- `pytest-django` with `@pytest.mark.django_db`; factories over fixtures files.
- Test services directly; test views/APIs with `client` / DRF `APIClient`.
- Use the same DB engine as Prod (PostgreSQL container), not SQLite, for integration tests.

## Pitfalls

- Business logic in signals (hidden control flow) or in templates.
- `DEBUG=True` or `ALLOWED_HOSTS=["*"]` reaching Staging/Prod.
- Running `collectstatic` or `migrate` concurrently in every pod at startup.
- Querying inside loops in templates/serializers (N+1).
- Using `runserver` in containers.
