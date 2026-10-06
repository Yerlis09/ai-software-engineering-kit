# Workflow — Bug Fix

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`) are relative to the AI root; `README.md` and `docs/` are relative to the project root.

## When to use

- Observed behaviour differs from specified or documented behaviour.
- A defect reported by users, monitoring, tests or a security scan.
- For security vulnerabilities, also follow `workflows/security-audit.md` for disclosure and remediation tracking.

## Agents involved

- `agents/00-master.md` — orchestration and final review.
- `agents/10-testing.md` — reproduction and regression test.
- `agents/01-frontend.md`, `agents/02-backend.md`, `agents/03-database.md` — diagnosis and fix.
- `agents/13-observability.md` — logs, traces and metrics for diagnosis.
- `agents/09-security.md` — security impact review.
- `agents/05-quality.md`, `agents/14-code-review.md` — quality gates.
- `agents/11-documentation.md` — changelog and docs.

## Steps

1. **Understand** — `agents/00-master.md`. Gather the report: expected vs actual behaviour, environment, version, frequency, impact. Output: clear problem statement and severity.
2. **Reproduce** — `agents/10-testing.md`. Reproduce locally or in Staging using logs and traces from `agents/13-observability.md`; then write an automated test that fails because of the bug. Output: failing test (no fix without it).
3. **Analyze root cause** — implementing agent. Apply the 5 whys until reaching a cause you can act on (code, design, process or missing test), not just the symptom. Output: root cause statement in the merge request.
4. **Plan** — `agents/00-master.md`. Decide the minimal fix and whether a hotfix release is needed; note any follow-up structural work as separate tickets. Output: fix plan.
5. **Search for siblings** — implementing agent. Search the codebase for the same pattern or misuse elsewhere (same function, copy-pasted logic, same library call). Output: list of other occurrences fixed or ticketed.
6. **Implement** — `agents/01-frontend.md` / `agents/02-backend.md` / `agents/03-database.md`. Apply the smallest change that fixes the root cause; no unrelated refactoring or features. Output: fix commit.
7. **Test** — `agents/10-testing.md`. The reproduction test now passes and stays as a regression test; the full suite is green; add edge cases revealed by the analysis. Output: green CI.
8. **Security review** — `agents/09-security.md`. Check whether the bug had security impact (data exposure, authz bypass, injection) and whether the fix introduces risk. Output: security note; escalate to the security contact in `context/project.md` if data was exposed.
9. **Quality review** — `agents/05-quality.md`. Verify the fix is readable, minimal and consistent with `rules/coding.md`. Output: findings addressed.
10. **Document** — `agents/11-documentation.md`. Add a `Fixed` entry in `CHANGELOG.md`; update docs if they were wrong; add monitoring/alerting if the bug went undetected. Output: updated docs.
11. **Final review** — `agents/14-code-review.md` then `agents/00-master.md`. Output: approved merge request, linked to the ticket; release via `workflows/release.md`.

## Exit criteria

- [ ] A test reproduced the bug before the fix and now passes.
- [ ] Root cause (5 whys) is documented in the merge request.
- [ ] Other occurrences of the same defect were searched for and handled.
- [ ] The fix is minimal and contains no unrelated changes.
- [ ] Full test suite is green in CI; no test was deleted or skipped.
- [ ] Security impact assessed; `CHANGELOG.md` updated.

## Anti-patterns

- Fixing without reproducing ("should work now").
- Patching the symptom (try/catch around it, special-case `if`) instead of the root cause.
- Changing or deleting the test that exposed the bug.
- Bundling refactoring or features with the fix.
- Ignoring identical bugs in copy-pasted code.
- Closing the ticket without a regression test.
