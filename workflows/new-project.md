# Workflow — New Project

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`, `stacks/`) are relative to the AI root; `README.md`, `docs/adr/` and `docs/architecture/` are relative to the project root.

## When to use

- Bootstrapping a new application, service or library from scratch.
- Re-founding an existing codebase that has no context or ADRs.

## Agents involved

- `agents/00-master.md` — orchestrates the workflow and the final review.
- `agents/04-architecture.md` — architecture choice and ADRs.
- `agents/01-frontend.md`, `agents/02-backend.md`, `agents/03-database.md` — stack skeletons, as relevant.
- `agents/09-security.md` — secure defaults and secret management.
- `agents/10-testing.md` — test harness.
- `agents/12-devops.md` — repository, and CI, Docker, Kubernetes when deployment is in scope.
- `agents/13-observability.md` — logging, metrics, health checks.
- `agents/11-documentation.md` — README and docs skeleton.
- `agents/14-code-review.md` — final quality gate.

## Steps

1. **Understand** — `agents/00-master.md`. Turn the request into structured requirements (`rules/architecture.md` ARCH-42): goal, actors, inputs, outputs, business rules, data and persistence needs, external dependencies, security, performance, deployment, acceptance criteria, constraints and unknowns. Label each item as explicit requirement, technical decision, missing business decision or assumption. Ask the human only for missing business decisions (ARCH-44). Output: completed `context/project.md` (including owners and security contact when known).
2. **Analyze** — `agents/04-architecture.md`. Identify quality attributes (availability, latency, security, compliance), integrations and risks. Output: requirements and risks section in `context/project.md`.
3. **Plan** — `agents/00-master.md`. Define the first milestone (walking skeleton) and the backlog of initial tasks; state what is in and out of scope, including deployment. Output: milestone plan, approved by the human when it creates or changes files.
4. **Design** — `agents/04-architecture.md`. Choose the simplest proportional architecture (`rules/architecture.md`) and the stack from `stacks/` yourself, and explain the choice (ARCH-43). Persistence: only when the requirements need it, with the database the human confirmed (ARCH-45). Output: `docs/adr/0001-record-architecture-decisions.md`, `docs/adr/0002-architecture-and-stack.md` (+ further ADRs), and a system architecture Mermaid diagram in `docs/architecture/`.
5. **Repository** — `agents/12-devops.md`. If the project directory is not its own Git repository, say so (even when a parent directory is one) and propose `git init` inside the project; run it only after approval. Never invent a remote: the team hosts code on git.netsf.fr, and the human creates or provides the repository URL. Add `.gitignore` (including `.env`, `.env.*`, keeping `.env.example`) and `.editorconfig`. Output: repository state reported, initialised only if approved.
6. **Implement skeleton** — `agents/01-frontend.md` / `agents/02-backend.md` / `agents/03-database.md`. Create the folder structure, composition root, configuration from environment, health endpoints, one end-to-end vertical slice. Output: runnable skeleton.
7. **Security baseline** — `agents/09-security.md`. Configure secret handling (`.env.example` with placeholders only; runtime injection), a secret scanner and dependency scanning. Output: no real credentials anywhere.
8. **Test harness** — `agents/10-testing.md`. Set up unit and integration test runners, coverage reporting, a first meaningful test per layer. Output: green test suite.
9. **Containerise and CI/CD (only when deployment is in scope)** — `agents/12-devops.md`. When deployment is requested or required (ARCH-46): multi-stage, non-root Dockerfile; CI pipeline with lint, test, scans, image build tagged by commit SHA, deploy to Kubernetes (RKE) Staging, manual promotion to Prod. Ask for missing target-environment facts instead of inventing them (ARCH-47). Output: Dockerfile, pipeline file, Kubernetes manifests/Helm chart — or "deployment not in scope" in the report.
10. **Observability** — `agents/13-observability.md`. Structured logging to stdout, metrics endpoint, liveness/readiness probes, correlation IDs, proportional to the project. Output: observability baseline.
11. **Document** — `agents/11-documentation.md`. Write `README.md` with the sections required by `rules/documentation.md`, `CHANGELOG.md`, `docs/adr/README.md` index, and a deployment diagram when deployment is in scope. Output: docs skeleton in English describing the current system.
12. **Doctor** — `agents/12-devops.md`. Run `ai-project doctor` and fix every reported issue. Output: clean doctor report.
13. **Final review** — `agents/14-code-review.md` then `agents/00-master.md`. Review against all `rules/` and report what was and was not verified. Output: review report; commits, merge requests and tags only when the human authorises them.

## Exit criteria

- [ ] `context/project.md` is complete; open business decisions are listed, not guessed.
- [ ] ADR-0001 and the architecture/stack ADR are accepted in `docs/adr/`.
- [ ] Repository state is explicit: own repository (initialised with approval) or reported as missing.
- [ ] `.env` is git-ignored; only `.env.example` with placeholders exists.
- [ ] Tests run and pass locally; results are reported as executed, or **NOT VALIDATED**.
- [ ] When deployment is in scope: CI runs lint, tests and scans, builds a Docker image, and the deployment is reported as executed or **NOT VALIDATED**.
- [ ] `README.md` contains the required sections; architecture diagram exists.
- [ ] `ai-project doctor` reports no errors.

## Anti-patterns

- Starting with microservices, event sourcing or Kubernetes operators "because we might need them".
- Choosing a stack outside `stacks/` without an ADR.
- Asking the human to pick a framework or library the requirements already let you decide.
- Adding a database to a workflow that does not need persistence, or choosing one silently.
- Adding Docker, Kubernetes, NGINX or CI when deployment is not in scope.
- Inventing hosts, namespaces, clusters, repository URLs or credentials.
- Committing a `.env` with real credentials, or committing and pushing without authorisation.
- Using a parent directory's Git repository for the new project.
- Writing a README that only says "TODO".
