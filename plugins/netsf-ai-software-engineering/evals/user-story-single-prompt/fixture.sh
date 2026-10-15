#!/usr/bin/env bash
# Creates an existing Flask project (files only) in the empty eval workspace.
set -euo pipefail
mkdir -p app/cells tests
cat > requirements.txt <<'REQ'
flask==3.0.0
pytest==8.0.0
REQ
cat > app/__init__.py <<'PY'
from flask import Flask


def create_app():
    app = Flask(__name__)
    from app.cells.routes import bp

    app.register_blueprint(bp)
    return app
PY
touch app/cells/__init__.py
cat > app/cells/routes.py <<'PY'
from flask import Blueprint, jsonify

bp = Blueprint("cells", __name__)
CELLS = {1: {"id": 1, "name": "A1"}}


@bp.route("/cells")
def list_cells():
    return jsonify(list(CELLS.values()))
PY
cat > tests/test_cells.py <<'PY'
from app import create_app


def test_list_cells():
    assert create_app().test_client().get("/cells").status_code == 200
PY
printf '# Cells service\n\n## API\n\n- GET /cells\n' > README.md
