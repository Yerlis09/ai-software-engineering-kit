"""Realistic miniature repositories used by the integration tests and the benchmark.

Each scenario is an existing, production-like project (files only, never executed) plus the
tasks a user would ask and what routing must and must not select.
"""

from __future__ import annotations

from pathlib import Path

FASTAPI_MAIN = """from fastapi import FastAPI

from app.api.cells import router

app = FastAPI(title="cells-api")
app.include_router(router)
"""
CELLS_API = """from fastapi import APIRouter

router = APIRouter(prefix="/cells")


@router.get("")
def list_cells() -> list[dict]:
    return []
"""
K8S_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: svc
spec:
  template:
    spec:
      containers:
        - name: svc
          image: registry.example/svc:1.0.0
"""

SCENARIOS: dict[str, dict] = {
    "python_backend": {
        "files": {
            "requirements.txt": "flask==3.0.0\npsycopg2-binary==2.9.9\npytest==8.0.0\n",
            "app.py": "from flask import Flask\napp = Flask(__name__)\n",
            "tests/test_app.py": "def test_ok():\n    assert True\n",
            "README.md": "# Billing service\n",
        },
        "expect": {"frameworks": ["Flask"], "databases": ["PostgreSQL"], "profile": "backend-api"},
        "tasks": [("Add an endpoint to list invoices", {"backend", "testing"}, {"frontend"})],
    },
    "fastapi": {
        "files": {
            "pyproject.toml": '[project]\nname = "cells"\n'
            'dependencies = ["fastapi>=0.110", "uvicorn"]\n'
            '[project.optional-dependencies]\ndev = ["pytest", "httpx"]\n',
            "app/main.py": FASTAPI_MAIN,
            "app/api/cells.py": CELLS_API,
            "tests/test_cells.py": "from app.api.cells import list_cells\n\ndef test_list():\n"
            "    assert list_cells() == []\n",
            "README.md": "# Cells API\n",
        },
        "expect": {"frameworks": ["FastAPI"], "profile": "backend-api"},
        "tasks": [
            (
                "Create a FastAPI endpoint to retrieve cells",
                {"backend", "api", "testing", "security"},
                {"frontend", "devops"},
            )
        ],
    },
    "clickhouse": {
        "files": {
            "requirements.txt": "clickhouse-connect==0.7.0\nopenpyxl==3.1.2\nrequests==2.31.0\n",
            "jobs/load_kpis.py": "import clickhouse_connect\n\ndef run():\n    pass\n",
            "sql/kpis.sql": "CREATE TABLE kpis (d Date) ENGINE = MergeTree ORDER BY d;\n",
            "tests/test_load.py": "def test_x():\n    assert True\n",
        },
        "expect": {"databases": ["ClickHouse"], "profile": "python-automation"},
        "tasks": [("Fix ClickHouse query", {"database", "testing", "debugging"}, {"frontend"})],
    },
    "python_automation": {
        "files": {
            "requirements.txt": "openpyxl==3.1.2\nrequests==2.31.0\nschedule==1.2.1\n",
            "report.py": "import openpyxl\nimport requests\n",
            "README.md": "# Daily Excel report\n",
        },
        "expect": {"libraries": ["openpyxl (Excel)"], "profile": "python-automation"},
        "tasks": [
            (
                "Refactor a Python service that reads the Excel report",
                {"refactoring", "testing"},
                {"frontend", "devops"},
            )
        ],
    },
    "frontend": {
        "files": {
            "package.json": '{"name": "dash", "dependencies": {"react": "^18.2.0"}, '
            '"devDependencies": {"vitest": "^1.0.0", "typescript": "^5.0.0"}}',
            "src/App.tsx": "export function App() { return null; }\n",
            "src/App.test.tsx": "test('x', () => {});\n",
        },
        "expect": {"frameworks": ["React"], "profile": "frontend"},
        "tasks": [
            (
                "Improve React dashboard performance",
                {"frontend", "performance", "testing"},
                {"backend", "database"},
            )
        ],
    },
    "microservice": {
        "files": {
            "pyproject.toml": '[project]\nname = "orders"\ndependencies = ["fastapi", "pytest"]\n',
            "app/main.py": FASTAPI_MAIN,
            "app/api/cells.py": CELLS_API,
            "Dockerfile": "FROM python:3.12-slim\nUSER 10001\n",
            "deploy/k8s/deployment.yaml": K8S_DEPLOYMENT,
            "tests/contract/test_contract.py": "def test_contract():\n    assert True\n",
        },
        "expect": {
            "frameworks": ["FastAPI"],
            "deployment": ["Docker", "Kubernetes"],
            "profile": "microservice",
        },
        "tasks": [
            ("Review the authentication implementation", {"security", "testing"}, {"frontend"})
        ],
    },
    "docker": {
        "files": {
            "requirements.txt": "flask==3.0.0\n",
            "app.py": "from flask import Flask\napp = Flask(__name__)\n",
            "Dockerfile": 'FROM python:3.12-slim\nCMD ["python", "app.py"]\n',
            "docker-compose.yml": "services:\n  db:\n    image: postgres:16\n",
        },
        "expect": {"deployment": ["Docker"], "databases": ["PostgreSQL"]},
        "tasks": [("Add a health check to the Docker image", {"devops"}, {"frontend"})],
    },
    "kubernetes": {
        "files": {
            "pyproject.toml": '[project]\nname = "svc"\ndependencies = ["fastapi"]\n',
            "app/main.py": FASTAPI_MAIN,
            "app/api/cells.py": CELLS_API,
            "Dockerfile": "FROM python:3.12-slim\n",
            "k8s/deployment.yaml": K8S_DEPLOYMENT,
        },
        "expect": {"deployment": ["Docker", "Kubernetes"]},
        "tasks": [
            ("Deploy service to Kubernetes", {"devops", "testing"}, {"frontend", "database"})
        ],
    },
}


def build(root: Path, name: str) -> Path:
    project = root / name
    for rel, content in SCENARIOS[name]["files"].items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return project
