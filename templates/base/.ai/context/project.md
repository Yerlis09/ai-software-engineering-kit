# Project context — {{ project_name }}

> Project-owned. Compact summary read by AI assistants at the start of every task (L0 context):
> keep it short and factual. Unknown facts stay `TODO` (`ai-project doctor` warns while some remain).

## Summary

| Field | Value |
|---|---|
| Project | {{ project_name }} |
| Purpose | {{ description }} |
| Language | {{ language }} |
| Framework | {{ framework }} |
| Architecture | {{ architecture }} |
| Database | {{ database_title }} |
| Deployment | {{ deployment_title }} |
| Testing | TODO: test frameworks and where tests live |
| Commands | TODO: install, run, test, lint (one line each) |
| Integrations | {{ external_services }} |
| Owner | {{ owner }} |
| Security contact | {{ org_security_contact }} |
| Source | `{{ org_git_server }}` |
| Kit | v{{ kit_version }}, profile `{{ profile }}`, created {{ created_date }} |

## Problem and users

- **Problem:** {{ problem }}
- **Users:** {{ users }}

## Requirements

- **Functional:** {{ functional_requirements }}
- **Non-functional:** {{ non_functional_requirements }}
- **Security:** {{ security_requirements }} Secrets are injected at runtime (Kubernetes
  Secrets / vault / CI masked variables), never stored in the repository or in `.env` files.
- **Performance:** {{ performance_requirements }}

## Constraints and risks

- **Constraints:** {{ constraints }}
- **Risks:** {{ risks }}

## Pointers

- Architecture: `docs/architecture/README.md`; decisions: `docs/adr/`.
- Structure:
{{ structure_list }}
