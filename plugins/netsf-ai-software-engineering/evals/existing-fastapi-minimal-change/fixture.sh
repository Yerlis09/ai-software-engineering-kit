#!/usr/bin/env bash
# Creates the fixture project in the empty eval workspace (files only).
set -euo pipefail
mkdir -p app/api tests
cat > pyproject.toml <<'EOF'
[project]
name = "cells"
dependencies = ["fastapi>=0.110", "uvicorn"]
EOF
cat > app/main.py <<'EOF'
from fastapi import FastAPI
from app.api.cells import router

app = FastAPI()
app.include_router(router)
EOF
cat > app/api/cells.py <<'EOF'
from fastapi import APIRouter

router = APIRouter()


@router.get("/cells")
def list_cells() -> list[dict]:
    return [{"id": 1, "name": "A1"}]
EOF
cat > tests/test_cells.py <<'EOF'
from app.api.cells import list_cells


def test_list_cells():
    assert list_cells()[0]["id"] == 1
EOF
