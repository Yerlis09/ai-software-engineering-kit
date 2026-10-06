# Stack — FastAPI

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds FastAPI-specific guidance.

See also `stacks/python/README.md` (tooling, config, `.env` policy) and `agents/02-backend.md`.

## Recommended tooling

- Lint/format: `ruff`; types: `mypy` (with the Pydantic plugin) or `pyright`.
- Tests: `pytest`, `pytest-asyncio` or `anyio`, `httpx` (`AsyncClient` + `ASGITransport`) or `fastapi.testclient.TestClient`.
- Package manager: `uv` or `pip-tools`; security: `pip-audit`, `bandit`.
- Server: `uvicorn` (or `gunicorn` with `uvicorn.workers.UvicornWorker`) behind NGINX.
- DB: SQLAlchemy 2.x (async engine) + Alembic migrations.

## Serving model

FastAPI is an **ASGI** framework. uWSGI (the team's default for WSGI apps) is **not suitable** for FastAPI. Run it with `uvicorn` behind NGINX (`proxy_pass`, not `uwsgi_pass`); see `stacks/nginx/README.md`. In Kubernetes prefer one uvicorn process per pod and scale with replicas/HPA rather than many workers per pod.

## Project structure

```
src/app/
  api/v1/routers/     # Controller: APIRouter modules, thin handlers
  api/v1/schemas/     # Pydantic request/response models
  api/deps.py         # Depends() providers (db session, current user, services)
  application/        # Use cases / services
  domain/             # Entities, domain errors (no FastAPI/SQLAlchemy imports)
  repositories/       # Repository interfaces + SQLAlchemy implementations
  infrastructure/     # DB engine/session, external clients, settings
  main.py             # create_app(): routers, middleware, exception handlers, lifespan
tests/  alembic/  pyproject.toml
```

## Conventions

- Use an app factory (`create_app()`) and the `lifespan` context manager for startup/shutdown (not `@app.on_event`).
- Handlers stay thin: validate input (Pydantic), call an application service, map the result to a response model.
- Always declare `response_model` (or return type) so outputs are filtered and documented.
- Separate input/output schemas (`UserCreate`, `UserRead`); never return ORM objects with sensitive fields.
- Use `Depends()` for sessions, auth and services; override them in tests via `app.dependency_overrides`.
- Map domain errors to HTTP in exception handlers, not inside services.
- Version the API (`/api/v1`); use proper status codes (`201` on create, `204` on delete).

## Security

- Auth via OAuth2/OIDC bearer tokens (`OAuth2PasswordBearer` / `HTTPBearer`); validate signature, `exp`, `aud`, `iss`.
- Restrictive `CORSMiddleware` (explicit origins, no `*` with credentials).
- Disable or protect `/docs` and `/openapi.json` in Prod (`docs_url=None` or auth).
- Limit request body size at NGINX (`client_max_body_size`); validate uploads (type, size).
- Never log tokens or `SecretStr` values; read secrets from Kubernetes Secrets via settings.
- Rate-limit sensitive endpoints (NGINX `limit_req` or a middleware).

## Performance

- `async def` endpoints must only `await` non-blocking I/O. Blocking libraries → plain `def` endpoint (run in threadpool) or `run_in_threadpool`.
- Use async DB drivers (`asyncpg`, `aiomysql`) with a pooled engine; one session per request.
- Reuse a single `httpx.AsyncClient` created in `lifespan`; set timeouts.
- Paginate list endpoints; offload long tasks to a queue/worker (BackgroundTasks only for small, non-critical work).
- Use `ORJSONResponse` for large payloads if profiling shows serialization cost.

## Testing

- Unit-test services with fake repositories; test routers with `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- Override `Depends` providers instead of patching internals.
- Integration tests against a real database (container) with Alembic migrations applied.

## Pitfalls

- Calling blocking code (`requests`, sync DB driver, `time.sleep`) in `async def` — freezes the event loop.
- Serving with uWSGI or `uvicorn --reload` in production.
- Returning ORM models directly (leaks fields, lazy-load errors).
- Global mutable state shared across requests.
- Creating a new DB engine or HTTP client per request.

## Example

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, service: UserService = Depends(get_user_service)) -> UserRead:
    try:
        return await service.get(user_id)
    except UserNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="<nginx/ingress CIDR>"`.
