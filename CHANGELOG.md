# Changelog

All notable changes to the kit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/) (see `docs/VERSIONING.md`).

## [Unreleased]

## [1.0.0] - 2026-10-05

### Added

- `ai-project` CLI (Python 3.9+, standard library only): `init`, `doctor`, `update`,
  `list`, `version`, `help`; interactive wizard and fully flag-driven mode.
- 15 agents: master orchestrator, frontend, backend, database, architecture, code quality,
  SOLID & patterns, OOP, performance, security, testing, documentation, DevOps,
  observability, code review.
- 6 rule sets with citable IDs: coding, architecture, security, testing, performance,
  documentation.
- 6 workflows: new project, new feature, bug fix, refactoring, security audit, release.
- 18 stack guides: Python, FastAPI, Django, Flask, Node.js, TypeScript, React, Angular,
  PostgreSQL, SQL Server, ClickHouse, MongoDB, Docker, Kubernetes, NGINX + uWSGI, Linux,
  CI/CD, data pipelines.
- 7 profiles: backend-api, frontend, fullstack, python-automation, data-engineering,
  microservice, custom.
- Templates: `AGENTS.md`, project context, docs skeleton with ADRs and Mermaid diagrams.
- Assistant integrations (thin pointers to `AGENTS.md`): Claude Code, GitHub Copilot, Cursor;
  Codex reads `AGENTS.md` natively.
- Lock file (`.ai/kit.lock.json`) with hashes for safe three-way updates (`.kit-new` on conflict).
- `doctor` checks: configuration, kit integrity, Git (team server), quality tooling,
  dependency locks, non-root containers, secret detection with `.env` credential alert,
  documentation.
- Example project `examples/fastapi-demo`.
