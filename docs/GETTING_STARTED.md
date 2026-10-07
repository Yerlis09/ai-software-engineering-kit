# Getting started

This guide takes you from nothing to an AI-ready project in about ten minutes.

## 1. Install the CLI

```bash
pipx install "git+https://git.netsf.fr/<group>/ai-software-engineering-kit.git@v1.2.0"
# or: pip install "git+https://git.netsf.fr/<group>/ai-software-engineering-kit.git@v1.2.0"
ai-project version
```

If `ai-project` is not found, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#ai-project-command-not-found).

## 2. Create a project

```text
$ ai-project init
AI SOFTWARE ENGINEERING KIT  (v1.0.0)

Project name:
> automation-hub

Project type:
  1. Backend API - HTTP API exposing business capabilities (REST/JSON).
  2. Frontend - Web user interface (SPA) consuming APIs.
  3. Full Stack - Frontend + backend API delivered together.
  4. Python Automation - Scripts, scheduled jobs, integrations and internal tooling in Python.
  5. Data Engineering - Ingestion, transformation and loading pipelines, analytics storage.
  6. Microservice - One independently deployable service with a narrow bounded context.
  7. Custom - Anything else: all agents, you pick the stack guides.
Select:
> 4

Technology:
  1. Python (scripts, automation) (default)
  2. Python + FastAPI
  ...
Database:          (PostgreSQL, SQL Server, ClickHouse, MongoDB, None, Custom)
Deployment:        (Docker + Kubernetes RKE Staging/Prod is the default)
AI assistants:     (Claude Code, Copilot, Cursor, Codex; Enter keeps all)
Business objective (one sentence):
Describe the project in more detail now? [y/N]
```

Press Enter to accept the defaults. A summary is shown before anything is written.

**Without prompts** (scripts, CI):

```bash
ai-project init --non-interactive --name automation-hub --profile python-automation \
  --technology python --database clickhouse --description "Automate weekly reporting."
```

**Existing project:** run `ai-project init .` in its root. The kit never overwrites your
files: if a kit-managed file (for example `AGENTS.md`) already exists with different content,
the kit version is written next to it as `AGENTS.md.kit-new` for you to merge.

## 3. What you get

```text
automation-hub/
├── AGENTS.md                 # entry point for every AI assistant
├── CLAUDE.md                 # thin pointer (per selected assistant)
├── .github/copilot-instructions.md
├── .ai/
│   ├── agents/               # 00-master.md + specialised roles for your profile
│   ├── rules/                # coding, architecture, security, testing, performance, docs
│   ├── workflows/            # new-project, new-feature, bug-fix, refactoring, ...
│   ├── stacks/               # python, clickhouse, docker, kubernetes, ...
│   ├── context/project.md    # YOUR project description (project-owned)
│   ├── custom/               # YOUR overrides (project-owned)
│   └── kit.lock.json         # kit version + hashes (commit it)
├── docs/architecture/, docs/adr/, development.md, deployment.md, troubleshooting.md
├── README.md, .gitignore, .editorconfig, .env.example
└── src/automation_hub/{jobs,services,adapters,config}/, tests/, deploy/
```

## 4. Describe your project

Open `.ai/context/project.md` and replace every `TODO`: objective, users, requirements,
constraints, risks. This is the most valuable 15 minutes you will spend. The AI reads this
file before every task.

## 5. Work with your AI assistant

Open the folder in Claude Code, Cursor, Copilot or Codex. The assistant picks up
`AGENTS.md` automatically (or through its pointer file). Then ask, for example:

> Follow `.ai/workflows/new-project.md` to set up the project skeleton, tooling and CI.

> Follow `.ai/workflows/new-feature.md`: add an endpoint that exports the weekly report as CSV.

The master agent (`.ai/agents/00-master.md`) selects the relevant specialists and enforces
the lifecycle: Understand, Analyze, Plan, Design, Implement, Test, Security Review,
Quality Review, Document, Final Review. Review the output as you would a colleague's merge
request. The assistant must show real test results, and anything it did not run is
reported as **NOT VALIDATED**.

## 6. Check and push

```bash
git init && git add . && git commit -m "Initial project from AI engineering kit"
git remote add origin https://git.netsf.fr/<group>/automation-hub.git
git push -u origin main
ai-project doctor
```

`doctor` exits with code 1 on any FAIL, so add it to your CI pipeline (example in
`.ai/stacks/ci-cd/README.md`).

## 7. Keep it up to date

When a new kit version is released:

```bash
pipx upgrade ai-software-engineering-kit   # or pip install --upgrade ...
ai-project update --dry-run                # preview
ai-project update                          # apply; your customisations are preserved
```

See [VERSIONING.md](VERSIONING.md).
