#!/usr/bin/env bash
# Creates the fixture project in the empty eval workspace (files only).
set -euo pipefail
mkdir -p k8s
printf 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: svc\n' > k8s/deployment.yaml
printf 'FROM python:3.12-slim\n' > Dockerfile
