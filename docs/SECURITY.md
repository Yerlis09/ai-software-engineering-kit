# Security

Two topics: the security standards the kit gives generated projects, and the security of
the kit itself.

## Standards for generated projects

- `rules/security.md` (rule IDs `SEC-*`) and `agents/09-security.md` apply from the first
  line of code: input validation at trust boundaries, parameterised queries, output encoding,
  deny-by-default authorisation, dependency pinning and scanning, no secrets in logs,
  hardened containers, least-privilege CI/CD.
- `workflows/security-audit.md` defines a repeatable audit (STRIDE threat model, dependency,
  secret and configuration review, report with severities).
- `ai-project doctor` gives a first automated signal in CI.

### Team policy: no real credentials in `.env` files

Plain-text credentials in `.env` files leak through backups, shared folders, Docker build
contexts, screenshots and accidental commits. When `doctor` finds them it **does not block**,
but it prints a prominent alert:

```text
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! SECURITY WARNING - REAL CREDENTIALS FOUND IN .env FILES                         !
! ...                                                                             !
! Treat every credential stored this way as ALREADY COMPROMISED.                  !
! Do this now:                                                                    !
!   1. Move secrets to Kubernetes Secrets (Sealed Secrets / External Secrets),    !
!      a vault (e.g. HashiCorp Vault) or CI/CD masked + protected variables.      !
!   2. Rotate the exposed credentials.                                            !
!   3. Keep only placeholders in .env.example; keep .env in .gitignore.           !
!   4. Report the exposure to the security contact: <security contact>           !
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

The security contact comes from `catalog/organization.json`. Hard-coded secrets in **source
or config files** are a **FAIL** (exit 1). The AI agents are instructed to raise the same
warning whenever they encounter such files.

The kit never sends findings anywhere by itself: no network access, no telemetry. Use
`ai-project doctor --format json` to feed a report to your own tooling.

### Limits of the built-in scanner

It is heuristic, built for "no *obvious* secrets". It detects private keys, AWS, GitHub,
GitLab, Slack and Google tokens, credentials in URLs, and `password = "..."`-style
assignments in code and config files. It ignores placeholders and environment lookups.
Use gitleaks (or equivalent) in CI as well; the CI/CD stack guide shows how.

## Security of the kit itself

| Threat | Mitigation |
|---|---|
| Path traversal / writing outside the project (malicious names, templates or a tampered lock file) | Every write goes through `paths.safe_join`: rejects absolute paths, drive letters, `..`, `.`, backslashes and NUL, and checks the resolved path (symlinks included) stays inside the project. Lock-file paths are validated on read. |
| Template injection / code execution | Templates support only `{{ variable }}` substitution, single pass, no expressions; user input containing `{{ }}` is never re-expanded. Knowledge files are copied verbatim. |
| Arbitrary shell execution | The CLI never spawns processes or uses a shell. Git information is read by parsing `.git/config`. |
| Downloading and running code | No network access at all. Upgrades are an explicit `pip` / `pipx` step from git.netsf.fr, pinned to a tag. |
| Malicious or invalid input | Project names validated (portable, no Windows reserved names); free text stripped of control characters and capped at 2,000 characters; bounded prompt retries; invalid choices rejected with exit code 2. |
| Silent data loss | Existing files are never overwritten without `--force`; with `--force` a `.kit-backup` is kept. |
| Supply chain | Zero runtime dependencies. Dev dependencies (pytest, ruff) only in `[dev]`. |

Validation performed for v1.0.0 is recorded in the release notes and the kit's test suite
(`tests/test_paths_and_render.py`, `tests/test_secrets_scan.py`,
`tests/test_update.py::test_tampered_lock_cannot_escape_project`). The ruff `S` (bandit)
rule set runs on the CLI code.

## Reporting a vulnerability

Contact the security contact listed in `catalog/organization.json`. Do not open a public issue.
