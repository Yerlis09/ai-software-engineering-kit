"""Composition root: wires adapters to the application and exposes health probes."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from fastapi_demo import __version__
from fastapi_demo.api.routes import domain_error_handler, router
from fastapi_demo.application.task_service import TaskService
from fastapi_demo.domain.tasks import DomainError
from fastapi_demo.infrastructure.memory_repository import InMemoryTaskRepository


def create_app() -> FastAPI:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    app = FastAPI(title="fastapi-demo", version=__version__)
    app.state.task_service = TaskService(InMemoryTaskRepository())
    app.include_router(router)
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        """Liveness: the process is running. Never checks dependencies."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        """Readiness: dependencies are reachable (none yet for the in-memory adapter)."""
        return {"status": "ready"}

    return app


app = create_app()
