# Stack — Docker

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Docker-specific guidance.

Every deployable service is packaged as a container image, built in CI from git.netsf.fr, and deployed to Kubernetes (`stacks/kubernetes/README.md`). See `agents/12-devops.md`.

## Recommended tooling

- Build: Docker with BuildKit (`docker buildx build`).
- Lint: `hadolint` for Dockerfiles.
- Scan: Trivy (image vulnerabilities, misconfigurations, secrets) — or Grype; fail CI on HIGH/CRITICAL with a fix available.
- SBOM: `syft` or `trivy --format cyclonedx`; signing optional (`cosign`).
- Local dev: Docker Compose (`compose.yaml`) for app + dependencies.

## Project structure

```
Dockerfile            # multi-stage: builder -> runtime
.dockerignore
compose.yaml          # local development only (not used in Staging/Prod)
docker/               # optional: entrypoint scripts, uwsgi.ini, nginx.conf
```

## Conventions

- **Multi-stage builds**: compile/install in a builder stage; copy only artifacts into a slim runtime stage.
- **Pin base images** by explicit version tag, ideally with digest (`python:3.12-slim@sha256:...`); never `latest`. Update via Renovate/Dependabot.
- Prefer `-slim` or distroless runtime images; install only what runs.
- Order layers from least to most frequently changing (dependency manifests before source) to maximize cache hits.
- **Non-root `USER`** with a fixed UID/GID (e.g. 10001) so Kubernetes `runAsNonRoot` works.
- **One process per container**; NGINX and the app server run in separate containers/pods (or a sidecar), not under supervisord.
- `ENTRYPOINT`/`CMD` in exec form (`["uwsgi", "--ini", "uwsgi.ini"]`) so signals reach the process; handle `SIGTERM`.
- Add `HEALTHCHECK` for Compose/standalone use; Kubernetes uses its own probes.
- Images are **immutable**: tag with the git SHA (and release version); the same image is promoted from Staging to Prod.
- Configuration via environment variables at runtime; no environment-specific images.
- `.dockerignore` excludes `.git`, `.env*`, `node_modules`, `__pycache__`, tests artefacts, local secrets.

## Security

- **No secrets in layers, `ENV` or `ARG`** (they persist in image history). Use BuildKit secrets: `RUN --mount=type=secret,id=pip_conf ...` and `docker buildx build --secret id=pip_conf,src=...`.
- Never `COPY . .` without a strict `.dockerignore` (it leaks `.env`, keys, `.git`).
- Scan every image in CI (Trivy) and rebuild regularly for base-image patches.
- Do not run containers `--privileged` or mount the Docker socket.
- Read-only root filesystem compatible: write only to declared volumes / `/tmp`.

## Performance

- Small images pull faster and reduce attack surface; remove build tools and caches (`pip --no-cache-dir`, `apt-get clean`).
- Use BuildKit cache mounts (`--mount=type=cache,target=/root/.cache/uv`) and registry cache in CI.
- Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` for Python images.

## Testing

- `hadolint Dockerfile` and `trivy image <image>` in CI.
- Run the built image in CI for a smoke test (start, hit health endpoint, stop).
- Container structure tests optional (`container-structure-test`).

## Pitfalls

- `latest` tags, unpinned `apt-get install` versions drifting silently.
- Running as root; files owned by root that the non-root user cannot read.
- Secrets passed as build args or copied `.env` files.
- Shell-form `CMD` (PID 1 is `sh`, signals not forwarded → slow, unclean shutdowns).
- Rebuilding a different image for Prod instead of promoting the tested one.

## Example

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
RUN groupadd -g 10001 app && useradd -u 10001 -g app -s /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER 10001
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Pin the base images by digest in real projects; versions above are illustrative.
