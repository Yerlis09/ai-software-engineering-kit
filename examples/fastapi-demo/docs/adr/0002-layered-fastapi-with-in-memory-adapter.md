# 0002 — Layered FastAPI service with an in-memory repository adapter

- **Status:** Accepted
- **Date:** 2026-10-05
- **Deciders:** Platform Engineering

## Context

The demo must show the kit's preferred layering (`.ai/agents/02-backend.md`) while staying
runnable with no infrastructure. The team standard for Python web apps is NGINX + uWSGI,
but FastAPI is an ASGI framework and uWSGI only serves WSGI applications well.

## Options considered

1. Django + uWSGI — matches the serving standard, but heavier for a 4-endpoint demo.
2. FastAPI + PostgreSQL — realistic, but requires a database to run the demo and tests.
3. FastAPI + in-memory adapter behind a repository port — runnable anywhere, layering intact.

## Decision

Option 3. FastAPI is served by **uvicorn behind NGINX** (documented exception to the uWSGI
default, per `.ai/stacks/nginx/README.md`). Storage is an in-memory adapter implementing the
`TaskRepository` port defined in the domain.

## Consequences

- Data is lost on restart: acceptable for a demo, stated in the README and project context.
- Replacing storage means adding an adapter in `infrastructure/`; domain and application
  layers do not change.
- Readiness has no dependency to check yet; a real adapter must add its check.
