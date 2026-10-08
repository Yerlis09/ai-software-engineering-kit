# Architecture Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Stack-specific guidance lives in `stacks/<name>/README.md`.
Kit paths (`rules/`, `agents/`, `context/`) are relative to the AI root; `docs/adr/`, `docs/architecture/` and `README.md` are relative to the project root.
Levels follow RFC 2119: **MUST**, **SHOULD**, **MAY**. Owner agent: `agents/04-architecture.md`.

## Proportionality

- **ARCH-01** — MUST size the architecture to the problem, team and expected load described in `context/project.md`.
- **ARCH-02** — MUST start with the simplest viable structure (well-modularised monolith by default) and evolve it with evidence.
- **ARCH-03** — MUST NOT introduce layers, patterns or infrastructure without a current, concrete need (YAGNI).
- **ARCH-04** — SHOULD prefer boring, proven technology already used by the team over novel options.

## Scope and decisions

- **ARCH-42** — MUST turn the request into requirements first (goal, actors, inputs, outputs, business rules, data and persistence, external dependencies, security, performance, deployment, acceptance criteria, constraints, unknowns), labelled as explicit requirement, technical decision, missing business decision or assumption.
- **ARCH-43** — MUST decide technical choices (language, framework, libraries, structure, patterns, testing, errors, logging) and explain significant ones; MUST NOT ask the human to choose options that can reasonably be decided.
- **ARCH-44** — MUST ask only what cannot be inferred: ambiguous business meaning, external systems' identity or access, real infrastructure values, and the database (ARCH-45).
- **ARCH-45** — MUST ask which database to use when persistence is required and none is specified (MAY recommend ClickHouse, the team default); MUST NOT add a database when no persistence is needed (e.g. file in, file out).
- **ARCH-46** — MUST add Docker, Kubernetes (RKE), NGINX, CI/CD or production configuration only when deployment is requested or required; ask for a missing target environment.
- **ARCH-47** — MUST NOT invent IP addresses, hostnames, namespaces, clusters, repository URLs, credentials or production configuration; keep them `TODO`.

## Structure and boundaries

- **ARCH-05** — MUST separate concerns into clear layers or modules: presentation, application, domain, infrastructure.
- **ARCH-06** — MUST keep business rules in the domain layer, free of framework, database and transport details.
- **ARCH-07** — SHOULD organise code by feature/bounded context rather than by technical type at the top level.
- **ARCH-08** — MUST give each module a small, explicit public interface; internals stay private.
- **ARCH-09** — MUST maximise cohesion inside a module and minimise coupling between modules.
- **ARCH-10** — SHOULD favour composition of small components over deep inheritance hierarchies.

## Dependency direction

- **ARCH-11** — MUST point dependencies inward: infrastructure → application → domain, never the reverse.
- **ARCH-12** — MUST invert dependencies on infrastructure through interfaces/ports owned by the inner layer.
- **ARCH-13** — MUST NOT allow circular dependencies between modules, packages or services.
- **ARCH-14** — SHOULD enforce dependency rules automatically (import linters, architecture tests), in CI when the project has a pipeline.
- **ARCH-15** — MUST wire concrete implementations at a single composition root.

## Integration and APIs

- **ARCH-16** — MUST define API contracts explicitly (OpenAPI, JSON Schema, protobuf) and version them.
- **ARCH-17** — MUST NOT break a published contract without a deprecation period and a new version.
- **ARCH-18** — MUST treat every external system as unreliable: timeouts, retries with backoff, circuit breaking where relevant.
- **ARCH-19** — SHOULD make operations idempotent when they may be retried.
- **ARCH-20** — SHOULD isolate third-party SDKs behind adapters to limit vendor lock-in.

## Distribution

- **ARCH-21** — MUST NOT adopt microservices without a written justification (independent scaling, team autonomy, deployment cadence) recorded in an ADR.
- **ARCH-22** — MUST give each service ownership of its own data; no shared database between services.
- **ARCH-23** — SHOULD prefer asynchronous messaging for cross-service workflows that do not require an immediate answer.
- **ARCH-24** — MUST design for partial failure and define behaviour when a dependency is unavailable.

## Configuration and runtime (12-factor)

- **ARCH-25** — MUST read configuration from the environment; no environment-specific values in code.
- **ARCH-26** — MUST keep secrets out of the codebase and images; inject them at runtime (see `rules/security.md`).
- **ARCH-27** — MUST keep processes stateless; persist state in backing services.
- **ARCH-28** — MUST log to stdout/stderr as an event stream; the platform collects logs.
- **ARCH-29** — MUST keep dev, staging and prod as similar as possible (same image, different config).
- **ARCH-30** — MUST expose health endpoints (liveness, readiness) for orchestration.

## Deployment target

Applies when deployment is in scope (ARCH-46).

- **ARCH-31** — MUST package every deployable as a Docker image built once from a versioned Dockerfile.
- **ARCH-32** — MUST deploy to Kubernetes (RKE): Staging first, then promote the *same* image to Prod.
- **ARCH-33** — MUST describe deployments declaratively (manifests, Helm or Kustomize) versioned on git.netsf.fr.
- **ARCH-34** — SHOULD prefer NGINX as reverse proxy and uWSGI as application server for Python web services, unless an ADR states otherwise.
- **ARCH-35** — MUST define resource requests/limits and graceful shutdown for every workload.

## Observability by design

- **ARCH-36** — MUST plan logs, metrics and traces as part of the design; see `agents/13-observability.md`.
- **ARCH-37** — SHOULD propagate correlation/trace IDs across every boundary.

## Decisions and documentation

- **ARCH-38** — MUST record every significant decision (structure, technology, data store, integration style, security model) as an ADR in `docs/adr/NNNN-title.md`.
- **ARCH-39** — MUST NOT edit an accepted ADR's decision; supersede it with a new ADR.
- **ARCH-40** — MUST keep the architecture diagrams in `docs/architecture/` in sync with the code; see `rules/documentation.md`.
- **ARCH-41** — SHOULD review architecture with `agents/04-architecture.md` before implementing any cross-cutting change.
