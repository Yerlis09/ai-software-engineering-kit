# Stack — CI/CD

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds CI/CD-specific guidance.

Source lives on the internal Git server **git.netsf.fr**; images are built with Docker (`stacks/docker/README.md`) and deployed to RKE **Staging** then **Prod** (`stacks/kubernetes/README.md`). See `agents/12-devops.md`.

## Recommended tooling

- Lint/format/types: per stack (`ruff`, `mypy`; ESLint, Prettier, `tsc`).
- Tests: `pytest` / Vitest with coverage reports and JUnit XML for the CI UI.
- SAST: `bandit`, Semgrep; dependencies: `pip-audit`, `npm audit` / OSV-Scanner; secrets: `gitleaks` (also as pre-commit hook); image: Trivy.
- Manifests: `kubeconform`, `helm lint` / `kustomize build`.
- Kit check: `ai-project doctor` (exits non-zero on failure) — run it as a pipeline step.

## Project structure

```
.gitlab-ci.yml (or platform equivalent)   # pipeline definition, versioned with the code
.pre-commit-config.yaml                   # fast local checks mirroring CI
scripts/smoke.sh                          # post-deploy smoke tests
deploy/overlays/{staging,prod}/           # target manifests (stacks/kubernetes/README.md)
```

Pipeline flow (every stage fails the pipeline on error; build the image **once**, promote the same tag/digest):

```
Commit -> Lint -> Format check -> Type check -> Unit tests -> Integration tests
       -> Security scan (SAST, dependencies, secrets, image) -> Build image
       -> Deploy Staging -> Smoke tests -> Manual approval -> Promote to Prod
```

## Conventions

- **Protected branches** (`main`): merge via reviewed merge/pull requests only, green pipeline required, no force-push.
- Short-lived branches, Conventional Commits, release tags `vX.Y.Z`; image tag = git SHA (+ semver), never `latest`.
- Pipelines are code; reuse shared templates rather than copy-paste; cache dependencies keyed on lock files.
- Deploy Staging automatically from `main`; Prod requires a manual approval gate and a protected environment.

## Security

- CI variables for secrets are **masked and protected** (available only on protected branches/tags); never echo them.
- **Least-privilege deploy tokens**: one per environment, scoped to its namespace; Prod credentials unavailable to Staging jobs and merge-request pipelines.
- No credentials in `.env` files, repository files or job logs; prefer short-lived tokens (OIDC) where the platform supports it.
- Pin CI images and third-party actions/templates by version or digest.
- Runners: isolated, no privileged Docker-in-Docker unless required (prefer rootless BuildKit/kaniko).
- Fail on HIGH/CRITICAL vulnerabilities with an available fix; document accepted risks with expiry.

## Performance

- Fail fast: cheap checks (lint, format, types) first; target ~10–15 min, parallelize independent jobs.
- BuildKit layer/registry caches; parallel tests (`pytest -n auto`); service containers for integration tests.

## Testing

- Smoke tests against Staging after each deploy (health endpoint, a critical user journey via Playwright/HTTP).
- Post-Prod verification and an automated rollback path (`kubectl rollout undo` / `helm rollback`).

## Pitfalls

- Rebuilding the image for Prod (what you tested is not what you ship).
- Secrets printed by `set -x` or debug output.
- Flaky tests ignored with retries instead of being fixed.

## Example

Illustrative GitLab-CI-style YAML — exact syntax depends on the CI platform hosting git.netsf.fr.

```yaml
stages: [check, test, security, build, staging, prod]
variables: { IMAGE: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" }

.python: &python
  image: python:3.12-slim
  before_script: [pip install uv, uv sync --frozen]

lint:
  <<: *python
  stage: check
  script: [uv run ruff check ., uv run ruff format --check ., uv run mypy src]
doctor:
  image: python:3.12-slim
  stage: check
  script:                              # pin the kit version used by the project
    - pip install "git+https://git.netsf.fr/<group>/ai-software-engineering-kit.git@v1.0.0"
    - ai-project doctor                # non-zero exit fails the pipeline
unit:
  <<: *python
  stage: test
  script: [uv run pytest tests/unit --cov=src --junitxml=report.xml]
  artifacts: { reports: { junit: report.xml } }
integration:
  <<: *python
  stage: test
  services: ["postgres:16"]
  script: [uv run pytest tests/integration]
sast_deps:
  <<: *python
  stage: security
  script: [uv run bandit -r src, uv run pip-audit]
secrets:
  image: { name: "zricethezav/gitleaks:v8.18.4", entrypoint: [""] }
  stage: security
  script: [gitleaks detect --source . --no-banner --redact]
build:
  stage: build
  script:
    - docker buildx build -t "$IMAGE" --push .
    - trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE"
deploy_staging:
  stage: staging
  environment: staging
  rules: [{ if: '$CI_COMMIT_BRANCH == "main"' }]
  script:
    - kubectl -n app-staging set image deployment/api api="$IMAGE"
    - kubectl -n app-staging rollout status deployment/api --timeout=5m
    - ./scripts/smoke.sh https://app-staging.example.internal
promote_prod:
  stage: prod
  environment: production
  # manual approval gate; mark "production" as a protected environment
  rules: [{ if: '$CI_COMMIT_BRANCH == "main"', when: manual }]
  script:
    - kubectl -n app-prod set image deployment/api api="$IMAGE"
    - kubectl -n app-prod rollout status deployment/api --timeout=5m
```

Prefer committing the new tag to the prod overlay (GitOps) over `kubectl set image` when a GitOps tool is in place.
