# Security Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Stack-specific hardening lives in `stacks/<name>/README.md`.
Kit paths (`rules/`, `agents/`, `workflows/`) are relative to the AI root; `docs/` paths are relative to the project root.
Levels follow RFC 2119: **MUST**, **SHOULD**, **MAY**. Owner agent: `agents/09-security.md`.

## Secure by design

- **SEC-01** — MUST consider security from the design phase; run a threat model (STRIDE) for new features touching data, auth or external input.
- **SEC-02** — MUST NOT disable, bypass or weaken a security mechanism (TLS verification, CSRF, CORS, auth, linters, scanners) for convenience — not even "temporarily".
- **SEC-03** — MUST fail closed: on error, deny access rather than grant it.
- **SEC-04** — SHOULD minimise attack surface: remove unused endpoints, ports, features and dependencies.

## Secrets management

- **SEC-05** — MUST NOT hardcode secrets (passwords, API keys, tokens, private keys, connection strings) in code, config, images, tests or docs.
- **SEC-06** — MUST inject secrets at runtime from a secret store: Kubernetes Secrets managed via Sealed Secrets or External Secrets, a vault (e.g. HashiCorp Vault), or CI/CD variables marked **masked** and **protected**.
- **SEC-07** — MUST git-ignore `.env` and all `.env.*` files except `.env.example`.
- **SEC-08** — MUST commit only `.env.example`, containing placeholders (`DB_PASSWORD=changeme`), never real values.
- **SEC-09** — Real credentials in `.env` files are strongly discouraged, even locally. Tools and AI assistants MUST emit a clear, dissuasive warning whenever they find one (see below), without blocking the user's work.
- **SEC-10** — MUST rotate secrets regularly and use distinct secrets per environment (dev / staging / prod).
- **SEC-11** — MUST NOT log, print, echo or include secrets in error messages, URLs or crash reports.

### Mandatory `.env` warning (for tools and AI assistants)

When a real credential is detected in a `.env` file (or any tracked file), display a message such as:

> **SECURITY WARNING — credentials found in `<file>`.** Storing real secrets in `.env` files exposes them to leaks (commits, backups, screenshots, shared machines). Move them to Kubernetes Secrets (Sealed Secrets / External Secrets), HashiCorp Vault, or masked + protected CI/CD variables. Keep only placeholders in `.env.example`. If this file was ever committed, treat the secret as compromised and follow "Secret found? Do this" in `rules/security.md`.

## Input validation and output encoding

- **SEC-12** — MUST validate all input at trust boundaries (HTTP, CLI, files, messages, env, third-party APIs): type, length, format, range.
- **SEC-13** — MUST validate with allow-lists rather than deny-lists.
- **SEC-14** — MUST use parameterized queries or a safe ORM API; never build queries by string concatenation.
- **SEC-15** — MUST encode output for its context (HTML, attribute, JS, URL, SQL, shell) to prevent injection and XSS.
- **SEC-16** — MUST NOT pass untrusted input to shell commands, `eval`, template engines or deserializers.
- **SEC-17** — MUST use safe deserialization formats (JSON) and reject unsafe ones (pickle, native object serialization) for untrusted data.

## Authentication and authorization

- **SEC-18** — MUST deny by default: every endpoint and resource requires explicit authorization.
- **SEC-19** — MUST check authorization server-side on every request, including object-level ownership (no IDOR).
- **SEC-20** — MUST apply least privilege to users, service accounts, database roles, Kubernetes RBAC and CI tokens.
- **SEC-21** — MUST use vetted libraries for authentication, password hashing (Argon2, bcrypt) and cryptography; never roll your own.
- **SEC-22** — MUST protect sessions and tokens: short lifetime, secure/HttpOnly/SameSite cookies, revocation.
- **SEC-23** — SHOULD rate-limit authentication and other abuse-prone endpoints.

## Files, paths and network

- **SEC-24** — MUST canonicalize and confine file paths to an allowed base directory; reject `..` traversal and absolute paths from users.
- **SEC-25** — MUST validate uploaded files (size, type by content, name) and store them outside the web root with generated names.
- **SEC-26** — MUST protect against SSRF: allow-list outbound hosts/schemes, block private, loopback and metadata IP ranges, disable redirects or re-validate them.
- **SEC-27** — MUST use TLS for all network traffic outside the pod/host; never disable certificate verification.

## Dependencies and supply chain

- **SEC-28** — MUST pin dependencies with lock files and pinned base-image digests or tags.
- **SEC-29** — MUST scan dependencies and container images for vulnerabilities in CI; block on critical/high findings without accepted risk.
- **SEC-30** — MUST run a secret scanner (pre-commit and CI) on every change.
- **SEC-31** — SHOULD use minimal, non-root container images and read-only filesystems.
- **SEC-32** — SHOULD review licences and maintenance status of new dependencies.

## Data protection and logging

- **SEC-33** — MUST classify personal and sensitive data and encrypt it in transit and, where required, at rest.
- **SEC-34** — MUST NOT log secrets, passwords, tokens, full card numbers or unnecessary personal data; mask when needed.
- **SEC-35** — MUST log security events (logins, permission denials, admin actions) for audit.
- **SEC-36** — MUST return generic error messages to clients; details go to server logs only.

## Configuration

- **SEC-37** — MUST set secure defaults: debug off, security headers on, verbose errors off in staging and prod.
- **SEC-38** — MUST review security-relevant configuration (CORS, CSP, headers, RBAC, network policies) during `workflows/security-audit.md`.

## Secret found? Do this

1. **Rotate** — generate a new secret and deploy it through the secret store (never via `.env` or code).
2. **Revoke** — invalidate the leaked secret at its provider immediately; assume it is compromised once committed or shared.
3. **Purge history** — remove it from the repository history (`git filter-repo` or BFG), force-push with coordination, and clear CI caches and artefacts.
4. **Notify** — inform the security contact named in `context/project.md` with what leaked, where, since when, and actions taken.
5. **Prevent** — add the file to `.gitignore`, enable or tune the secret scanner, and record the incident.
