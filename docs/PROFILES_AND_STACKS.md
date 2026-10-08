# Profiles, technologies and stacks

A **profile** decides which agents, rules, workflows and folder structure a project gets. A
**technology** preset and a **database** add stack guides. The **deployment** choice adds
infrastructure guides. Everything is data: `profiles/*.json` and `catalog/*.json`.

## Profiles

| Profile | Agents (00 master + 14 review always) | Technologies offered | Default structure |
|---|---|---|---|
| `backend-api` | 02, 04-13 (no 01) | python-fastapi, python-django, python-flask, node-typescript, custom | `src/<pkg>/{api,application,domain,infrastructure}`, `tests/{unit,integration}`, `deploy/` |
| `frontend` | 01, 04, 05, 06, 08-12 | react, angular, custom | `src/{app,components,features,services,styles}`, `tests/e2e`, `deploy/` |
| `fullstack` | 01, 02, 04-13 | react-fastapi, react-django, angular-django, custom | `backend/src/<pkg>/...`, `frontend/src`, `deploy/` |
| `python-automation` | 04-13 | python, python-fastapi, python-data, custom | `src/<pkg>/{jobs,services,adapters,config}`, `tests/`, `deploy/` |
| `data-engineering` | 03, 04, 05, 06, 08-13 | python-data, python, custom | `src/<pkg>/{extract,transform,load,quality,orchestration}`, `tests/`, `deploy/` |
| `microservice` | 02, 04-13 | python-fastapi, python-flask, node-typescript, custom | Hexagonal layout + `tests/contract` |
| `custom` | all 15 | all | none |

`03-database` is added to every profile when a database other than `none` is selected.
Every profile also installs `15-context-token-optimizer` (routing helper, never auto-loaded).
All profiles get the 6 rule sets and the 6 workflows.

## Technologies

| Key | Stack guides |
|---|---|
| `python-fastapi` | python, fastapi (+ nginx when deployed) |
| `python-django` | python, django (+ nginx when deployed) |
| `python-flask` | python, flask (+ nginx when deployed) |
| `react-fastapi` | react, typescript, python, fastapi (+ nginx when deployed) |
| `react-django` | react, typescript, python, django (+ nginx when deployed) |
| `angular-django` | angular, typescript, python, django (+ nginx when deployed) |
| `react` / `angular` | react or angular, typescript (+ nginx when deployed) |
| `node-typescript` | node, typescript |
| `python` | python |
| `python-data` | python, data-pipelines |
| `custom` | choose any with `--stacks` (or interactively) |

Databases add `postgresql`, `sqlserver`, `clickhouse` or `mongodb`; `undecided` (the default)
and `none` add nothing. Deployments `kubernetes` and `docker` add `docker`, `kubernetes` (for
`kubernetes`), `ci-cd`, `linux`, the technology's serving guide (`nginx`) and the profile's
`deploy/` folder; `undecided` (the default) adds none of them, `none` adds `ci-cd` only.

## Team defaults

- Frontend: HTML / JavaScript / **React**. Backend: **Python**.
- Serving: **NGINX + uWSGI** for WSGI apps (Django, Flask). FastAPI is ASGI and runs on
  uvicorn behind NGINX; the stack guides document this exception.
- Source on **git.netsf.fr**; when deployment is in scope, images built with **Docker** and
  deployed on **Kubernetes RKE**: Staging first, then the same immutable image promoted to Prod.
- Database: chosen per project; when persistence is needed and unspecified, the assistant asks
  and recommends **ClickHouse**.

## Stack guide format

Every `stacks/<name>/README.md` has: Recommended tooling, Project structure, Conventions,
Security, Performance, Testing, Pitfalls, and optionally an Example. Generic rules are not
repeated there.

## Adding a profile, technology or stack

See [CUSTOMIZATION.md](CUSTOMIZATION.md#extending-the-kit).
