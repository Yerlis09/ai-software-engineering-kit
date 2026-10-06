from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fastapi_demo.main import create_app

BASE = "/api/v1/tasks"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_probes(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_task_lifecycle(client: TestClient) -> None:
    created = client.post(BASE, json={"title": "Review PR"})
    assert created.status_code == 201
    task = created.json()
    assert task["title"] == "Review PR" and task["done"] is False

    assert client.get(f"{BASE}/{task['id']}").json() == task
    done = client.post(f"{BASE}/{task['id']}/complete")
    assert done.status_code == 200 and done.json()["done"] is True
    assert [t["id"] for t in client.get(BASE).json()] == [task["id"]]


def test_completing_twice_returns_problem_details(client: TestClient) -> None:
    task_id = client.post(BASE, json={"title": "Once"}).json()["id"]
    client.post(f"{BASE}/{task_id}/complete")
    response = client.post(f"{BASE}/{task_id}/complete")
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Task already done"


def test_unknown_task_is_404(client: TestClient) -> None:
    response = client.get(f"{BASE}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["status"] == 404


@pytest.mark.parametrize(
    "body",
    [{}, {"title": ""}, {"title": "x" * 201}, {"title": "ok", "admin": True}],
)
def test_invalid_input_is_rejected(client: TestClient, body: dict) -> None:
    assert client.post(BASE, json=body).status_code == 422


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_pagination_bounds(client: TestClient, query: str) -> None:
    assert client.get(f"{BASE}?{query}").status_code == 422


def test_malformed_id_is_rejected(client: TestClient) -> None:
    assert client.get(f"{BASE}/not-a-uuid").status_code == 422
