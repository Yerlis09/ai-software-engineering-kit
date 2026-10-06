# Workflow — Release

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`) are relative to the AI root; `CHANGELOG.md`, `README.md` and `docs/` are relative to the project root.

## When to use

- Shipping a new version of an application or library to Staging and Production.
- Hotfix releases (same steps, reduced scope, expedited reviews — never skipped).

## Agents involved

- `agents/00-master.md` — release coordination and go/no-go.
- `agents/12-devops.md` — build, tag, deploy, rollback.
- `agents/10-testing.md` — regression and smoke tests.
- `agents/09-security.md` — release security gate.
- `agents/05-quality.md`, `agents/14-code-review.md` — quality gate.
- `agents/13-observability.md` — post-release monitoring.
- `agents/11-documentation.md` — changelog and release notes.

## Steps

1. **Understand** — `agents/00-master.md`. List merged changes since the last tag and check they are all reviewed and linked to tickets. Output: release scope.
2. **Analyze** — `agents/00-master.md`. Classify changes (breaking / feature / fix), identify migrations, config or secret changes, and risky items. Output: risk assessment.
3. **Plan** — `agents/12-devops.md`. Define the release window, migration order, feature flags and the rollback plan (previous image tag, reversible migrations, data backup). Output: release and rollback plan.
4. **Version** — `agents/00-master.md`. Apply SemVer: MAJOR for breaking changes, MINOR for features, PATCH for fixes. Output: new version number.
5. **Changelog** — `agents/11-documentation.md`. Move `Unreleased` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md` (Keep a Changelog: Added, Changed, Deprecated, Removed, Fixed, Security); document breaking changes and migration steps. Output: updated `CHANGELOG.md`.
6. **Test** — `agents/10-testing.md`. Full suite green on the release commit. Output: green CI.
7. **Security review** — `agents/09-security.md`. Dependency and image scans pass; no secrets in the image or repository; required Kubernetes Secrets exist in Staging and Prod (no `.env` credentials). Output: security gate passed.
8. **Quality review** — `agents/14-code-review.md`. Release merge request (version bump + changelog) approved. Output: approved merge request.
9. **Tag and build** — `agents/12-devops.md`. Create an annotated tag `vX.Y.Z` on git.netsf.fr; CI builds one immutable Docker image tagged `X.Y.Z` (and recorded by digest) and pushes it to the registry. Output: tag and image digest.
10. **Deploy to Staging** — `agents/12-devops.md`. Deploy the image by digest to Kubernetes (RKE) Staging; run migrations. Output: Staging deployment.
11. **Smoke tests** — `agents/10-testing.md`. Run smoke and critical-path tests against Staging; check dashboards and error rates. Output: go/no-go evidence.
12. **Promote to Prod** — `agents/12-devops.md` after `agents/00-master.md` go decision. Deploy the *same* image digest to Kubernetes (RKE) Prod — never rebuild; use a rolling or canary strategy. Output: Prod deployment.
13. **Post-release monitoring** — `agents/13-observability.md`. Watch error rate, latency, saturation and business metrics for an agreed period; run smoke tests on Prod. Output: release health report.
14. **Rollback if needed** — `agents/12-devops.md`. If health degrades, redeploy the previous image digest and follow the rollback plan; open a bug via `workflows/bug-fix.md`. Output: restored service and incident note.
15. **Final review** — `agents/00-master.md`. Publish release notes, close tickets, record lessons learned. Output: closed release.

## Exit criteria

- [ ] Version follows SemVer and matches the git tag `vX.Y.Z`.
- [ ] `CHANGELOG.md` has a dated section in Keep a Changelog format.
- [ ] One immutable image built once and identified by digest.
- [ ] Deployed to RKE Staging and smoke tests passed before Prod.
- [ ] The same image digest is running in RKE Prod.
- [ ] Rollback plan documented and tested (previous digest available).
- [ ] Post-release monitoring completed with no unresolved alerts.

## Anti-patterns

- Rebuilding the image for Prod instead of promoting the Staging image.
- Using mutable tags such as `latest` for deployments.
- Deploying straight to Prod, or on Friday evening without on-call.
- Releasing with failing or skipped tests "to meet the deadline".
- Irreversible migrations without backup or rollback plan.
- Putting release credentials in `.env` files instead of protected CI variables.
- Declaring success without watching metrics after deployment.
