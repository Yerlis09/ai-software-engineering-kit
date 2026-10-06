"""Domain model: pure Python, no framework or database imports."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

MAX_TITLE_LENGTH = 200


class DomainError(Exception):
    """Base class for business-rule violations."""


class TaskNotFoundError(DomainError):
    def __init__(self, task_id: UUID) -> None:
        super().__init__(f"Task {task_id} not found")
        self.task_id = task_id


class TaskAlreadyDoneError(DomainError):
    def __init__(self, task_id: UUID) -> None:
        super().__init__(f"Task {task_id} is already done")
        self.task_id = task_id


@dataclass(frozen=True)
class Task:
    id: UUID
    title: str
    done: bool = False

    def __post_init__(self) -> None:
        title = self.title.strip()
        if not title or len(title) > MAX_TITLE_LENGTH:
            raise ValueError(f"title must be 1-{MAX_TITLE_LENGTH} characters")
        object.__setattr__(self, "title", title)

    def complete(self) -> Task:
        if self.done:
            raise TaskAlreadyDoneError(self.id)
        return replace(self, done=True)


class TaskRepository(Protocol):
    """Port implemented by the infrastructure layer."""

    def add(self, task: Task) -> None: ...

    def get(self, task_id: UUID) -> Task | None: ...

    def save(self, task: Task) -> None: ...

    def list(self, limit: int, offset: int) -> list[Task]: ...
