#!/usr/bin/env bash
# Creates the fixture project in the empty eval workspace (files only).
set -euo pipefail
printf 'API_KEY=dummy-not-a-real-key\n' > .env
printf 'print(1)\n' > app.py
