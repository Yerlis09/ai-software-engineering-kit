# Workflow — New Feature

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`) are relative to the AI root; `README.md`, `docs/adr/` and `docs/architecture/` are relative to the project root.

## When to use

- Adding new user-facing or system behaviour (endpoint, screen, job, integration).
- Extending existing behaviour in a way that changes its contract or output.
- Not for bug fixes (`workflows/bug-fix.md`) or behaviour-preserving changes (`workflows/refactoring.md`).

## Agents involved

- `agents/00-master.md` — orchestration and final review.
- `agents/04-architecture.md` — design note and ADR when needed.
- `agents/01-frontend.md`, `agents/02-backend.md`, `agents/03-database.md` — implementation.
- `agents/06-solid-patterns.md`, `agents/07-oop.md` — design quality.
- `agents/10-testing.md` — test strategy.
- `agents/08-performance.md` — performance impact.
- `agents/09-security.md` — security review.
- `agents/05-quality.md`, `agents/14-code-review.md` — quality gates.
- `agents/11-documentation.md` — documentation.

## Steps

1. **Understand** — `agents/00-master.md`. Read the ticket and `context/project.md`; clarify ambiguities with the requester. Output: explicit acceptance criteria (Given/When/Then), including error and authorization cases.
2. **Analyze** — `agents/04-architecture.md`. Locate affected modules, contracts and data; assess impact on security, performance and existing users. Output: impact list and risks.
3. **Plan** — `agents/00-master.md`. Break the work into small, independently reviewable increments; decide on feature flag if partial delivery is needed. Output: task list.
4. **Design** — `agents/04-architecture.md` with `agents/06-solid-patterns.md`. For non-trivial features (new module, new contract, new data model, cross-cutting change), write a short design note: context, approach, alternatives, API/data changes, Mermaid sequence or data-flow diagram if helpful. Output: design note in the merge request or `docs/architecture/`; ADR in `docs/adr/` for significant decisions.
5. **Test first or alongside** — `agents/10-testing.md`. Translate acceptance criteria into failing tests: happy path, validation, edge cases, failure, authorization (`rules/testing.md`). Output: failing tests.
6. **Implement** — `agents/01-frontend.md` / `agents/02-backend.md` / `agents/03-database.md`. Write the simplest code that passes the tests, following `rules/coding.md` and the stack guide; include migrations, configuration via environment, logs and metrics. Output: passing implementation.
7. **Test** — `agents/10-testing.md`. Run the full suite locally and in CI; add integration tests for new adapters. Output: green pipeline.
8. **Performance check** — `agents/08-performance.md`. Check for N+1, missing pagination, missing timeouts, unbounded loads (`rules/performance.md`). Output: findings resolved or ticketed.
9. **Security review** — `agents/09-security.md`. Check input validation, authorization (deny by default), output encoding, secrets handling, new dependencies (`rules/security.md`). Warn about any credentials in `.env` files. Output: security checklist in the merge request.
10. **Quality review** — `agents/05-quality.md`. Verify readability, cohesion, coupling, duplication, linter/formatter results. Output: quality findings addressed.
11. **Document** — `agents/11-documentation.md`. Update `README.md` (configuration, usage), API contract, diagrams, `CHANGELOG.md` (Unreleased section). Output: docs in the same merge request.
12. **Final review** — `agents/14-code-review.md` then `agents/00-master.md`. Verify every acceptance criterion is met and tested. Output: approved merge request on git.netsf.fr.

## Exit criteria

- [ ] All acceptance criteria are covered by automated tests.
- [ ] Tests cover happy path, validation, edge, failure and authorization cases.
- [ ] CI is green (lint, tests, scans, image build).
- [ ] Design note / ADR exists for non-trivial or significant changes.
- [ ] No new secret, `.env` credential or disabled security control.
- [ ] Docs and `CHANGELOG.md` updated in the same merge request.
- [ ] Code review approved with no unresolved blocking comments.

## Anti-patterns

- Starting to code before acceptance criteria are clear.
- Gold-plating: adding options or abstractions no criterion asks for.
- Writing tests only after the merge request is "done" — or not at all.
- Mixing unrelated refactoring into the feature merge request.
- One giant merge request instead of small increments.
- "Docs will follow in another ticket."
