"""In-memory adapter for the TaskRepository port (see ADR 0002).

Thread-safe because uvicorn may serve requests from several threads. A PostgreSQL adapter
can replace it without touching the domain or application layers.
"""

from __future__ import annotations

from threading import Lock
from uuid import UUID

from fastapi_demo.domain.tasks import Task


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}
        self._lock = Lock()

    def add(self, task: Task) -> None:
        with self._lock:
            self._tasks[task.id] = task

    def get(self, task_id: UUID) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def save(self, task: Task) -> None:
        with self._lock:
            self._tasks[task.id] = task

    def list(self, limit: int, offset: int) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())[offset : offset + limit]
