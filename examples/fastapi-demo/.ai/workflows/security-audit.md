# Workflow — Security Audit

> Kit file — managed by `ai-project update`.

Kit paths (`agents/`, `rules/`, `context/`) are relative to the AI root; `docs/` paths are relative to the project root.

## When to use

- Before the first production release and before major releases.
- Periodically (at least once a year) or after significant architecture changes.
- After a security incident, leaked secret or critical vulnerability disclosure.

## Agents involved

- `agents/00-master.md` — orchestration and final review.
- `agents/09-security.md` — lead auditor.
- `agents/04-architecture.md` — architecture and trust boundaries.
- `agents/02-backend.md`, `agents/01-frontend.md`, `agents/03-database.md` — code-level review and remediation.
- `agents/12-devops.md` — CI/CD, Docker, Kubernetes (RKE) configuration.
- `agents/13-observability.md` — security logging and alerting.
- `agents/10-testing.md` — security tests.
- `agents/11-documentation.md` — report and runbooks.

## Steps

1. **Understand / scope** — `agents/00-master.md` with `agents/09-security.md`. Define in-scope components, environments, data classes and out-of-scope items; read `context/project.md`. Output: audit scope.
2. **Analyze / threat model** — `agents/09-security.md` with `agents/04-architecture.md`. Draw a data-flow diagram with trust boundaries; apply STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) per element. Output: threat model in `docs/security/threat-model.md`.
3. **Dependency scan** — `agents/12-devops.md`. Scan application dependencies and container images (SCA); verify lock files and pinned base images. Output: vulnerability list with CVSS.
4. **Secret scan** — `agents/09-security.md`. Scan the working tree and full git history for secrets. Inspect every `.env*` file: `.env` must be git-ignored, only `.env.example` with placeholders committed. For each real credential found in a `.env` file, emit the dissuasive warning defined in `rules/security.md` and recommend Kubernetes Secrets (Sealed/External Secrets), HashiCorp Vault or masked + protected CI variables. Output: secret findings; leaked secrets trigger "Secret found? Do this".
5. **Code review** — implementing agents. Review against `rules/security.md`: input validation, parameterized queries, output encoding, authorization (deny by default, object-level checks), file/path handling, SSRF, deserialization, error messages. Run SAST. Output: code findings.
6. **Configuration review** — `agents/12-devops.md`. Review Dockerfiles (non-root, minimal), Kubernetes manifests (RBAC, network policies, securityContext, secrets usage), NGINX/uWSGI config (TLS, headers, limits), CI/CD permissions and variable protection. Output: configuration findings.
7. **Logging and detection** — `agents/13-observability.md`. Verify security events are logged, secrets are not, and alerts exist. Output: findings.
8. **Test** — `agents/10-testing.md`. Confirm critical findings with tests or a DAST run against Staging (never Prod without approval). Output: verified findings.
9. **Report** — `agents/09-security.md`. Rate each finding (Critical / High / Medium / Low / Info) with evidence, impact, affected component and recommendation. Output: `docs/security/audit-YYYY-MM-DD.md`.
10. **Remediation plan** — `agents/00-master.md`. Create tickets with owners and deadlines (e.g. Critical: immediate, High: 7 days, Medium: 30 days, Low: backlog); record accepted risks with sign-off. Output: remediation plan.
11. **Document** — `agents/11-documentation.md`. Update runbooks, ADRs for security decisions, `README.md` configuration section. Output: updated docs.
12. **Final review** — `agents/00-master.md`. Present the report to the owners and the security contact. Output: signed-off audit and scheduled follow-up.

## Exit criteria

- [ ] Scope and STRIDE threat model documented.
- [ ] Dependency, image, secret (history included) and SAST scans executed.
- [ ] Every `.env` credential reported with a warning and a secure alternative.
- [ ] Docker, Kubernetes, NGINX/uWSGI and CI/CD configuration reviewed.
- [ ] Report lists findings with severities, evidence and recommendations.
- [ ] Remediation tickets created with owners and deadlines; leaked secrets rotated and revoked.
- [ ] Security contact notified of Critical/High findings.

## Anti-patterns

- Running a scanner and calling it an audit.
- Silencing findings or disabling scanners to get a clean report.
- Reporting `.env` credentials without a remediation path — or not reporting them.
- Removing a leaked secret from the latest commit without rotating it.
- Testing destructively against production.
- A report with no owners or deadlines.
