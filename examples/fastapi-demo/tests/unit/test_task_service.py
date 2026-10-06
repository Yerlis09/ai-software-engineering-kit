from __future__ import annotations

from uuid import UUID

import pytest

from fastapi_demo.application.task_service import TaskService
from fastapi_demo.domain.tasks import (
    MAX_TITLE_LENGTH,
    Task,
    TaskAlreadyDoneError,
    TaskNotFoundError,
)
from fastapi_demo.infrastructure.memory_repository import InMemoryTaskRepository

FIXED_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def service() -> TaskService:
    return TaskService(InMemoryTaskRepository(), new_id=lambda: FIXED_ID)


def test_create_trims_title_and_stores_task(service: TaskService) -> None:
    task = service.create("  Write ADR  ")
    assert task == Task(id=FIXED_ID, title="Write ADR", done=False)
    assert service.get(FIXED_ID) == task


@pytest.mark.parametrize("title", ["", "   ", "x" * (MAX_TITLE_LENGTH + 1)])
def test_create_rejects_invalid_titles(service: TaskService, title: str) -> None:
    with pytest.raises(ValueError, match="title"):
        service.create(title)


def test_complete_marks_task_done(service: TaskService) -> None:
    service.create("Ship it")
    assert service.complete(FIXED_ID).done is True
    assert service.get(FIXED_ID).done is True


def test_completing_twice_is_a_business_error(service: TaskService) -> None:
    service.create("Ship it")
    service.complete(FIXED_ID)
    with pytest.raises(TaskAlreadyDoneError):
        service.complete(FIXED_ID)


def test_unknown_task(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.get(FIXED_ID)


def test_list_is_paginated() -> None:
    ids = iter(UUID(int=i) for i in range(1, 6))
    service = TaskService(InMemoryTaskRepository(), new_id=lambda: next(ids))
    for i in range(5):
        service.create(f"task {i}")
    assert [t.title for t in service.list(limit=2, offset=1)] == ["task 1", "task 2"]
