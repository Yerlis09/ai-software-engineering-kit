# Project context — {{ project_name }}

> Project-owned. AI assistants read this file first. Keep it short, factual and current.
> Replace every `TODO` (`ai-project doctor` warns while some remain).

## Identity

- **Project name:** {{ project_name }}
- **Owner:** {{ owner }}
- **Security contact:** {{ org_security_contact }}
- **Created:** {{ created_date }} (kit v{{ kit_version }}, profile `{{ profile }}`)

## Business objective

{{ description }}

## Problem

{{ problem }}

## Users

{{ users }}

## Functional requirements

{{ functional_requirements }}

## Non-functional requirements

{{ non_functional_requirements }}

## Technology stack

- **Profile:** {{ profile_title }} — {{ profile_description }}
- **Technology:** {{ technology_title }}
- **Database:** {{ database_title }}
- **Deployment:** {{ deployment_title }}

## Architecture

{{ architecture }}

Decisions are recorded in `docs/adr/`. Details: `docs/architecture/README.md`.

## Database

{{ database_title }}. TODO: main entities, expected volumes, retention, backup/restore needs.

## External services

{{ external_services }}

## Security requirements

{{ security_requirements }}

Secrets are injected at runtime (Kubernetes Secrets / vault / CI masked variables), never
stored in the repository or in `.env` files with real values.

## Performance requirements

{{ performance_requirements }}

## Deployment

{{ deployment_title }}. Source on `{{ org_git_server }}`. TODO: URLs, namespaces, release cadence.

## Constraints

{{ constraints }}

## Risks

{{ risks }}

## Recommended structure

{{ structure_list }}
