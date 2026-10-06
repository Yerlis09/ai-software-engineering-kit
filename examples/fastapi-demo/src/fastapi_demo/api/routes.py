"""HTTP layer: validation, mapping and error translation only - no business logic."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from fastapi_demo.application.task_service import TaskService
from fastapi_demo.domain.tasks import (
    MAX_TITLE_LENGTH,
    Task,
    TaskAlreadyDoneError,
    TaskNotFoundError,
)

MAX_PAGE_SIZE = 100

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)


class TaskOut(BaseModel):
    id: UUID
    title: str
    done: bool

    @classmethod
    def from_domain(cls, task: Task) -> TaskOut:
        return cls(id=task.id, title=task.title, done=task.done)


def get_service(request: Request) -> TaskService:
    return request.app.state.task_service  # type: ignore[no-any-return]


Service = Annotated[TaskService, Depends(get_service)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskOut)
def create_task(body: TaskIn, service: Service) -> TaskOut:
    return TaskOut.from_domain(service.create(body.title))


@router.get("", response_model=list[TaskOut])
def list_tasks(
    service: Service,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskOut]:
    return [TaskOut.from_domain(t) for t in service.list(limit=limit, offset=offset)]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: UUID, service: Service) -> TaskOut:
    return TaskOut.from_domain(service.get(task_id))


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: UUID, service: Service) -> TaskOut:
    return TaskOut.from_domain(service.complete(task_id))


def problem(status_code: int, title: str, detail: str) -> JSONResponse:
    """RFC 9457 problem details."""
    return JSONResponse(
        status_code=status_code,
        content={"type": "about:blank", "title": title, "status": status_code, "detail": detail},
        media_type="application/problem+json",
    )


def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, TaskNotFoundError):
        return problem(status.HTTP_404_NOT_FOUND, "Task not found", str(exc))
    if isinstance(exc, TaskAlreadyDoneError):
        return problem(status.HTTP_409_CONFLICT, "Task already done", str(exc))
    return problem(status.HTTP_422_UNPROCESSABLE_ENTITY, "Business rule violated", str(exc))
