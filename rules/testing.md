# Testing Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Stack-specific tooling lives in `stacks/<name>/README.md`.
Kit paths (`rules/`, `agents/`, `workflows/`) are relative to the AI root.
Levels follow RFC 2119: **MUST**, **SHOULD**, **MAY**. Owner agent: `agents/10-testing.md`.

## Integrity

- **TEST-01** — MUST NOT delete, skip, comment out or weaken a test to make a build pass.
- **TEST-02** — MUST NOT change an assertion to match buggy behaviour; fix the code or document the behaviour change.
- **TEST-03** — MUST justify any skipped test with a ticket reference and an expiry.
- **TEST-04** — MUST NOT write tests whose only purpose is to raise coverage (no assertions, trivial getters, executing code without checking outcomes).

## Testable by design

- **TEST-05** — MUST design code so that dependencies (I/O, clock, randomness, network) can be injected or substituted.
- **TEST-06** — SHOULD keep business logic in pure units that can be tested without infrastructure.

## What to test

- **TEST-07** — MUST cover the happy path of every new or changed behaviour.
- **TEST-08** — MUST cover input validation (invalid, missing, malformed values).
- **TEST-09** — MUST cover edge cases (empty, zero, boundaries, max sizes, unicode, time zones).
- **TEST-10** — MUST cover failure paths (dependency down, timeout, exception, partial failure).
- **TEST-11** — MUST cover authorization: allowed role succeeds, other roles and anonymous users are denied.
- **TEST-12** — MUST add a regression test reproducing the bug before every bug fix; see `workflows/bug-fix.md`.
- **TEST-13** — SHOULD test public behaviour and contracts, not private implementation details.

## Test pyramid

- **TEST-14** — SHOULD favour many fast unit tests, fewer integration tests, and a small set of end-to-end tests.
- **TEST-15** — MUST have integration tests for each adapter (database, queue, external API) against real or containerised dependencies.
- **TEST-16** — SHOULD have contract tests for APIs consumed by other teams or services.
- **TEST-17** — SHOULD have smoke tests runnable against Staging and Prod after deployment.

## Determinism and isolation

- **TEST-18** — MUST be deterministic: same input, same result, every run, on every machine.
- **TEST-19** — MUST NOT depend on execution order, shared mutable state or other tests' data.
- **TEST-20** — MUST control time, randomness and IDs (fixed clock, seeded random, injectable generators).
- **TEST-21** — MUST NOT call real third-party services or production systems from automated tests.
- **TEST-22** — MUST NOT use `sleep` to wait for async work; wait on explicit conditions with timeouts.
- **TEST-23** — MUST quarantine and fix flaky tests promptly; a flaky test is a bug.

## Structure and readability

- **TEST-24** — SHOULD follow Arrange–Act–Assert (Given–When–Then) with one behaviour per test.
- **TEST-25** — MUST name tests after the behaviour they verify (`rejects_expired_token`).
- **TEST-26** — SHOULD use builders/factories for test data instead of large literal fixtures.
- **TEST-27** — SHOULD mock only at architectural boundaries; do not mock the unit under test or value objects.
- **TEST-28** — MUST NOT put real secrets or personal data in test fixtures.

## Continuous integration

- **TEST-29** — MUST run the full automated test suite in CI on every merge request.
- **TEST-30** — MUST block merges when tests fail.
- **TEST-31** — SHOULD keep the unit suite fast (target: under 5 minutes) so it runs locally before each push.
- **TEST-32** — SHOULD track coverage as a signal, with a floor that never decreases on changed code; coverage is not a goal in itself.
- **TEST-33** — MAY use mutation testing on critical business logic to measure test effectiveness.

## Non-functional tests

- **TEST-34** — SHOULD include security tests (authz, injection, input fuzzing) for exposed endpoints; see `rules/security.md`.
- **TEST-35** — SHOULD include performance tests against defined budgets for critical paths; see `rules/performance.md`.
