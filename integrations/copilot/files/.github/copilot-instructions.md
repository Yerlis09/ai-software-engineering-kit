# Copilot instructions — {{ project_name }}

Kit-managed pointer (AI Software Engineering Kit v{{ kit_version }}).

Follow `AGENTS.md` at the repository root: it defines the project, the mandatory workflow,
the agents (`.ai/agents/`), rules (`.ai/rules/`) and workflows (`.ai/workflows/`).
Project context: `.ai/context/project.md`. Project overrides: `.ai/custom/`.

Essentials: no hard-coded secrets (and no real credentials in `.env` files), validate input
at boundaries, add tests with every change, keep docs and ADRs up to date.
