# Documentation Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Kit paths (`rules/`, `agents/`, `context/`) are relative to the AI root;
`README.md`, `CHANGELOG.md`, `docs/adr/` and `docs/architecture/` are relative to the project root.
Levels follow RFC 2119: **MUST**, **SHOULD**, **MAY**. Owner agent: `agents/11-documentation.md`.

## General

- **DOC-01** — MUST update documentation in the same change (merge request) as the code it describes.
- **DOC-02** — MUST write documentation in Markdown, versioned in the repository next to the code.
- **DOC-03** — SHOULD write for the reader: concise, task-oriented, with copy-pasteable commands.
- **DOC-04** — MUST NOT duplicate information; link to the single source of truth instead.
- **DOC-05** — MUST NOT include real secrets, internal credentials or personal data in docs or examples.
- **DOC-06** — SHOULD remove or update obsolete documentation rather than leaving it to rot.
- **DOC-30** — MUST describe the current system in English, not its implementation history (history: `CHANGELOG.md`, ADRs).
- **DOC-31** — MUST, before declaring a task done, update docs affected by changed public behaviour, API, configuration, deployment, architecture or business rules.
- **DOC-32** — MUST NOT state that something was tested or deployed unless it was executed; otherwise **NOT VALIDATED**.

## README

- **DOC-07** — MUST provide a `README.md` at the project root with at least these sections:
  - **Overview** — what the project does and for whom.
  - **Architecture** — short summary and link to `docs/architecture/`.
  - **Prerequisites** — tools and versions required.
  - **Getting started** — install, configure (using `.env.example` placeholders only), run locally.
  - **Configuration** — environment variables table (name, purpose, default, required) and where secrets come from.
  - **Testing** — how to run unit, integration and end-to-end tests.
  - **Deployment** — when deployment is in scope, Docker build and Kubernetes (RKE) Staging/Prod deployment; otherwise state that the project is not deployed yet.
  - **Contributing** — branching, merge request process on git.netsf.fr, coding rules.
  - **Support / owners** — team and contacts.
- **DOC-08** — MUST ensure the "Getting started" steps work on a clean machine.
- **DOC-09** — SHOULD keep the README under a few screens; move detail into `docs/`.

## Architecture Decision Records

- **DOC-10** — MUST record significant decisions as ADRs in `docs/adr/NNNN-title.md` (four-digit number, kebab-case title).
- **DOC-11** — MUST include in each ADR: Status, Date, Context, Decision, Alternatives considered, Consequences.
- **DOC-12** — MUST use statuses `Proposed`, `Accepted`, `Deprecated` or `Superseded by NNNN`.
- **DOC-13** — MUST NOT rewrite an accepted ADR; create a new ADR that supersedes it.
- **DOC-14** — SHOULD keep an index of ADRs in `docs/adr/README.md`.

## Diagrams

- **DOC-15** — MUST write diagrams as Mermaid code blocks so they are versioned and diffable.
- **DOC-16** — MUST include only diagrams that add understanding; choose among:
  - **System architecture** (context) — the system, its users and external systems.
  - **Component** — main modules/services and their dependencies.
  - **Data flow** — how data moves and where it is stored, especially sensitive data.
  - **Sequence** — non-trivial interactions (auth flows, async workflows).
  - **Deployment** — Docker images, Kubernetes (RKE) namespaces, ingress, backing services.
- **DOC-17** — MUST store architecture diagrams in `docs/architecture/` and update them with structural changes.
- **DOC-18** — SHOULD give each diagram a title and a one-line caption explaining what it shows.

## Code-level documentation

- **DOC-19** — MUST document public APIs and every non-obvious module, class or function with docstrings/doc comments describing current behaviour: purpose, parameters, return, errors (see `rules/coding.md` CODE-46/47).
- **DOC-20** — SHOULD comment *why* (constraints, trade-offs, workarounds), not *what*.
- **DOC-21** — MUST publish HTTP API contracts (e.g. OpenAPI) and keep them generated from or validated against the code.

## Change history

- **DOC-22** — MUST maintain `CHANGELOG.md` in Keep a Changelog format with SemVer versions; see `workflows/release.md`.
- **DOC-23** — MUST describe every merge request: what, why, how it was tested, and linked ticket.
- **DOC-24** — SHOULD flag breaking changes and migration steps explicitly in the changelog and merge request.

## Operations

- **DOC-25** — SHOULD provide runbooks in `docs/runbooks/` for alerts, rollback and common incidents.
- **DOC-26** — MUST document how to roll back a release.
- **DOC-27** — SHOULD document dashboards, key metrics and alerts; see `agents/13-observability.md`.

## AI context

- **DOC-28** — MUST keep `context/project.md` accurate (purpose, stack, constraints, owners, security contact).
- **DOC-29** — MUST put project-specific rule overrides in `custom/`, never by editing kit files.
