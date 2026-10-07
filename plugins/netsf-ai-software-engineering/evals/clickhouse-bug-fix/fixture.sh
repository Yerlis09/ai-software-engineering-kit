#!/usr/bin/env bash
# Creates the fixture project in the empty eval workspace (files only).
set -euo pipefail
cat > requirements.txt <<'EOF'
clickhouse-connect==0.7.0
EOF
cat > kpi.py <<'EOF'
def daily_total(client):
    rows = client.query("SELECT sum(value) FROM kpis WHERE day = today()").result_rows
    return rows[0][0]
EOF
