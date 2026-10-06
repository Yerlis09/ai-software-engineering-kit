# Coding Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Stack-specific conventions live in `stacks/<name>/README.md`.
Paths such as `rules/security.md` are relative to the AI root; `docs/` and `README.md` are relative to the project root.
Levels follow RFC 2119: **MUST** (mandatory), **SHOULD** (expected unless justified), **MAY** (optional).

## Guiding principles

- **CODE-01** — MUST favour the simplest solution that meets the requirement (KISS).
- **CODE-02** — MUST NOT build features, options or abstractions "for later" (YAGNI).
- **CODE-03** — SHOULD remove duplicated knowledge (DRY), but MUST NOT merge code that only looks alike and changes for different reasons.
- **CODE-04** — MUST apply SOLID where it reduces coupling; see `agents/06-solid-patterns.md`.
- **CODE-05** — SHOULD prefer composition over inheritance; see `agents/07-oop.md`.
- **CODE-06** — MUST keep separation of concerns: I/O, business logic and presentation live in distinct units.

## Naming and readability

- **CODE-07** — MUST use intention-revealing names; avoid abbreviations except well-known domain terms.
- **CODE-08** — MUST follow the naming conventions of the stack guide in `stacks/`.
- **CODE-09** — SHOULD name booleans as predicates (`is_active`, `hasAccess`) and functions as verbs.
- **CODE-10** — MUST NOT use magic numbers or strings; extract named constants.
- **CODE-11** — SHOULD write code that reads top-down; the public entry point comes before its helpers.

## Functions and modules

- **CODE-12** — SHOULD keep functions small and single-purpose (rule of thumb: under 40 lines).
- **CODE-13** — SHOULD limit parameters to 4; group related values into a typed object.
- **CODE-14** — SHOULD keep cyclomatic complexity low (≤ 10 per function); use early returns over deep nesting.
- **CODE-15** — MUST keep modules highly cohesive; one module, one responsibility.
- **CODE-16** — MUST depend on abstractions at module boundaries, not on concrete infrastructure (dependency inversion).
- **CODE-17** — SHOULD prefer pure functions and immutable data for business logic.
- **CODE-18** — MUST NOT use global mutable state; inject dependencies explicitly.

## Types and contracts

- **CODE-19** — SHOULD use static typing or type hints where the language supports it.
- **CODE-20** — MUST validate preconditions at public boundaries and fail fast with a clear message.
- **CODE-21** — MUST NOT return `null`/`None` for "error"; use exceptions, result types or explicit optionals.
- **CODE-22** — SHOULD make illegal states unrepresentable (enums, value objects, constructors that validate).

## Error handling

- **CODE-23** — MUST NOT swallow errors silently; handle, wrap with context, or propagate.
- **CODE-24** — MUST catch the most specific error type possible; no bare catch-all except at the top-level boundary.
- **CODE-25** — MUST release resources deterministically (context managers, `finally`, `using`, `defer`).
- **CODE-26** — MUST return user-facing errors that do not leak internals (stack traces, SQL, paths); see `rules/security.md`.
- **CODE-27** — SHOULD define domain-specific error types for expected business failures.

## Observability by design

- **CODE-28** — MUST log through the project's structured logger, never with ad-hoc prints.
- **CODE-29** — SHOULD log at the right level (DEBUG/INFO/WARN/ERROR) with correlation IDs; see `agents/13-observability.md`.
- **CODE-30** — MUST NOT log secrets, tokens or personal data.

## Comments and dead code

- **CODE-31** — SHOULD comment *why*, not *what*; the code explains what.
- **CODE-32** — MUST NOT commit commented-out code, debug statements or unused imports.
- **CODE-33** — MUST link `TODO`/`FIXME` comments to a ticket (`TODO(PROJ-123): …`).

## Formatting and tooling

- **CODE-34** — MUST pass the project formatter and linter with zero errors before commit.
- **CODE-35** — MUST NOT disable a linter rule without an inline justification.
- **CODE-36** — SHOULD enforce formatting and linting via pre-commit hooks and CI.

## Dependencies

- **CODE-37** — MUST justify every new dependency (maintenance, licence, size, security); prefer the standard library.
- **CODE-38** — MUST pin dependency versions with a lock file; see `rules/security.md`.

## Version control

- **CODE-39** — MUST host code on the team Git server (git.netsf.fr) and work through merge requests.
- **CODE-40** — MUST keep commits small, atomic and described with a clear message (Conventional Commits recommended).
- **CODE-41** — MUST NOT mix refactoring, formatting and behaviour changes in the same commit.
- **CODE-42** — MUST NOT commit generated artefacts, build outputs, `.env` files or secrets.

## Testability by design

- **CODE-43** — MUST write code that can be tested without network, clock or filesystem by injecting those dependencies.
- **CODE-44** — MUST ship tests with every behaviour change; see `rules/testing.md`.
