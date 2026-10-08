# Deployment guide — {{ project_name }}

Target: {{ deployment_title }}.

This guide applies once deployment is in scope. Until it is requested, keep the TODOs and do
not add Docker, Kubernetes, NGINX or CI files. Never invent environment values (hosts,
namespaces, clusters, URLs, credentials): they stay `TODO` until the team provides them.

## Pipeline

Commit -> Lint -> Format -> Type check -> Unit tests -> Integration tests -> Security scan
-> Build image -> Deploy Staging -> Smoke tests -> Approval -> Promote the same image to Prod.

## Environments

| Environment | Where | How it is deployed |
|---|---|---|
| Staging | TODO | TODO |
| Production | TODO | TODO |

## Configuration and secrets

Configuration via environment variables / ConfigMaps. Secrets via Kubernetes Secrets
(Sealed Secrets or External Secrets), a vault or CI masked variables — never in Git.

## Rollback

TODO: how to roll back (for Kubernetes: `kubectl rollout undo deployment/<name>` or redeploy
the previous image tag).

## Health checks

TODO: liveness and readiness endpoints, smoke tests.
