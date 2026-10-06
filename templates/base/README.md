# {{ project_name }}

{{ description }}

| | |
|---|---|
| Type | {{ profile_title }} |
| Technology | {{ technology_title }} |
| Database | {{ database_title }} |
| Deployment | {{ deployment_title }} |

## Getting started

TODO: prerequisites, installation and how to run locally. See `docs/development.md`.

## Configuration

Settings come from environment variables; `.env.example` lists them with placeholder values.
Secrets are injected at runtime (Kubernetes Secrets, vault, CI masked variables) and must
never be committed or stored with real values in `.env` files.

## Tests

TODO: how to run unit, integration and end-to-end tests.

## Deployment

See `docs/deployment.md`. Source of truth: `{{ org_git_server }}`.

## Documentation

- Architecture: `docs/architecture/README.md`
- Decisions (ADRs): `docs/adr/`
- Development guide: `docs/development.md`
- Troubleshooting: `docs/troubleshooting.md`

## Working with AI assistants

This project uses the AI Software Engineering Kit. AI assistants start from `AGENTS.md`;
the project context is in `.ai/context/project.md`. Check the setup with `ai-project doctor`.
