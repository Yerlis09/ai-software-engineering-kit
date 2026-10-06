# Workflow — Refactoring

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`) are relative to the AI root; `docs/adr/` and `docs/architecture/` are relative to the project root.

## When to use

- Improving internal structure (readability, cohesion, coupling, duplication) without changing observable behaviour.
- Preparing the code to make an upcoming feature easy ("make the change easy, then make the easy change").
- Paying down technical debt identified by `agents/05-quality.md` or `agents/14-code-review.md`.
- Not for changing behaviour — use `workflows/new-feature.md` or `workflows/bug-fix.md`.

## Agents involved

- `agents/00-master.md` — orchestration and final review.
- `agents/05-quality.md` — identifies code smells and target quality.
- `agents/06-solid-patterns.md`, `agents/07-oop.md` — target design.
- `agents/04-architecture.md` — structural or cross-module refactorings.
- `agents/10-testing.md` — safety net.
- `agents/08-performance.md` — check for performance regressions.
- `agents/09-security.md` — check security controls are preserved.
- `agents/14-code-review.md` — final quality gate.

## Steps

1. **Understand** — `agents/00-master.md`. State the motivation (which smell, which upcoming change) and the scope boundary. Output: refactoring goal in one paragraph.
2. **Analyze** — `agents/05-quality.md`. Map the affected code, its callers and its public contracts; measure baseline (complexity, duplication, coverage, performance if relevant). Output: baseline metrics and smell list.
3. **Secure the safety net** — `agents/10-testing.md`. Ensure tests are green before any change; add characterisation tests where behaviour is not covered. Output: green, sufficient test suite.
4. **Plan** — `agents/00-master.md`. Split into small, behaviour-preserving steps, each independently committable (rename, extract, move, inline, introduce interface). Output: ordered step list.
5. **Design** — `agents/06-solid-patterns.md` / `agents/04-architecture.md`. Describe the target structure; write an ADR in `docs/adr/` if module boundaries or dependency direction change. Output: target design (and ADR if needed).
6. **Implement in small steps** — implementing agent. Apply one step at a time; run tests after each step; commit each green step. Prefer automated IDE refactorings. Output: series of small commits.
7. **Test** — `agents/10-testing.md`. Full suite green after the last step, with the same tests as before (characterisation tests may be kept). Output: green CI.
8. **Performance check** — `agents/08-performance.md`. Compare against baseline on hot paths. Output: no regression.
9. **Security review** — `agents/09-security.md`. Verify validation, authorization and encoding were not lost while moving code. Output: confirmation.
10. **Quality review** — `agents/05-quality.md`. Compare metrics with the baseline. Output: before/after summary in the merge request.
11. **Document** — `agents/11-documentation.md`. Update `docs/architecture/` diagrams and module docs if structure changed. Output: updated docs.
12. **Final review** — `agents/14-code-review.md` then `agents/00-master.md`. Output: approved merge request labelled as refactoring.

## Exit criteria

- [ ] Tests were green before the first change and are green after the last.
- [ ] No test assertion was changed to accommodate the refactoring.
- [ ] Observable behaviour, public contracts and outputs are unchanged.
- [ ] No feature or bug fix is mixed into the change.
- [ ] Each commit is small and leaves the build green.
- [ ] Quality metrics improved or stayed equal; no performance regression.
- [ ] Diagrams/ADRs updated if structure changed.

## Anti-patterns

- "Big bang" rewrites in a single merge request.
- Refactoring code without tests.
- Sneaking in a feature or "small fix" while refactoring.
- Adjusting tests to fit the new code.
- Introducing patterns or abstractions with no current need (YAGNI).
- Refactoring for taste with no stated goal.
