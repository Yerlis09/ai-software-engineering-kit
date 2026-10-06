"""Application layer: use cases orchestrating the domain through its ports."""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi_demo.domain.tasks import Task, TaskNotFoundError, TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, repository: TaskRepository, new_id: Callable[[], UUID] = uuid4) -> None:
        self._repository = repository
        self._new_id = new_id

    def create(self, title: str) -> Task:
        task = Task(id=self._new_id(), title=title)
        self._repository.add(task)
        logger.info("task created", extra={"task_id": str(task.id)})
        return task

    def get(self, task_id: UUID) -> Task:
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def complete(self, task_id: UUID) -> Task:
        task = self.get(task_id).complete()
        self._repository.save(task)
        logger.info("task completed", extra={"task_id": str(task.id)})
        return task

    def list(self, limit: int, offset: int) -> list[Task]:
        return self._repository.list(limit=limit, offset=offset)
