# Workflow — New Project

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`, `stacks/`) are relative to the AI root; `README.md`, `docs/adr/` and `docs/architecture/` are relative to the project root.

## When to use

- Bootstrapping a new application, service or library from scratch.
- Re-founding an existing codebase that has no context, ADRs, CI or container setup.

## Agents involved

- `agents/00-master.md` — orchestrates the workflow and the final review.
- `agents/04-architecture.md` — architecture choice and ADRs.
- `agents/01-frontend.md`, `agents/02-backend.md`, `agents/03-database.md` — stack skeletons, as relevant.
- `agents/09-security.md` — secure defaults and secret management.
- `agents/10-testing.md` — test harness.
- `agents/12-devops.md` — repository, CI, Docker, Kubernetes.
- `agents/13-observability.md` — logging, metrics, health checks.
- `agents/11-documentation.md` — README and docs skeleton.
- `agents/14-code-review.md` — final quality gate.

## Steps

1. **Understand** — `agents/00-master.md`. Interview stakeholders on purpose, users, scope, constraints, expected load, data sensitivity, deadlines. Output: completed `context/project.md` (including owners and security contact).
2. **Analyze** — `agents/04-architecture.md`. Identify quality attributes (availability, latency, security, compliance), integrations and risks. Output: requirements and risks section in `context/project.md`.
3. **Plan** — `agents/00-master.md`. Define the first milestone (walking skeleton) and the backlog of initial tasks. Output: milestone plan.
4. **Design** — `agents/04-architecture.md`. Choose the simplest proportional architecture (`rules/architecture.md`), the stack from `stacks/`, data store and integration style. Output: `docs/adr/0001-record-architecture-decisions.md`, `docs/adr/0002-architecture-and-stack.md` (+ further ADRs), and a system architecture Mermaid diagram in `docs/architecture/`.
5. **Repository** — `agents/12-devops.md`. Create the project on git.netsf.fr with protected `main`, merge-request approvals, `.gitignore` (including `.env`, `.env.*`, keeping `.env.example`), `.editorconfig`, licence. Output: initialised repository.
6. **Implement skeleton** — `agents/01-frontend.md` / `agents/02-backend.md` / `agents/03-database.md`. Create the folder structure, composition root, configuration from environment, health endpoints, one end-to-end vertical slice. Output: runnable skeleton.
7. **Security baseline** — `agents/09-security.md`. Configure secret injection (Kubernetes Secrets via Sealed/External Secrets or Vault, masked + protected CI variables), secret scanner pre-commit hook, dependency and image scanning. Output: `.env.example` with placeholders only; no real credentials anywhere.
8. **Test harness** — `agents/10-testing.md`. Set up unit and integration test runners, coverage reporting, a first meaningful test per layer. Output: green test suite.
9. **Containerise and CI/CD** — `agents/12-devops.md`. Write a multi-stage, non-root Dockerfile; CI pipeline with lint, test, scans, image build tagged by commit SHA, deploy to Kubernetes (RKE) Staging, manual promotion to Prod. Output: Dockerfile, pipeline file, Kubernetes manifests/Helm chart.
10. **Observability** — `agents/13-observability.md`. Structured logging to stdout, metrics endpoint, liveness/readiness probes, correlation IDs. Output: observability baseline.
11. **Document** — `agents/11-documentation.md`. Write `README.md` with all sections required by `rules/documentation.md`, `CHANGELOG.md`, `docs/adr/README.md` index, deployment diagram. Output: docs skeleton.
12. **Doctor** — `agents/12-devops.md`. Run `ai-project doctor` and fix every reported issue. Output: clean doctor report.
13. **Final review** — `agents/14-code-review.md` then `agents/00-master.md`. Review against all `rules/`. Output: approved first merge request and a tagged `v0.1.0`.

## Exit criteria

- [ ] `context/project.md` is complete, including owners and security contact.
- [ ] ADR-0001 and the architecture/stack ADR are accepted in `docs/adr/`.
- [ ] Repository exists on git.netsf.fr with protected `main` and required reviews.
- [ ] `.env` is git-ignored; only `.env.example` with placeholders is committed.
- [ ] CI runs lint, tests, dependency/image/secret scans and builds a Docker image.
- [ ] The skeleton is deployed to Kubernetes (RKE) Staging and passes health checks.
- [ ] `README.md` contains all required sections; architecture diagram exists.
- [ ] `ai-project doctor` reports no errors.

## Anti-patterns

- Starting with microservices, event sourcing or Kubernetes operators "because we might need them".
- Choosing a stack outside `stacks/` without an ADR.
- Committing a `.env` with real credentials "just for the first deploy".
- Postponing CI, tests or Docker until "after the MVP".
- Writing a README that only says "TODO".
- Hosting the repository outside git.netsf.fr.
