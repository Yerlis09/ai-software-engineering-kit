# Project customisations

Project-owned: `ai-project update` never touches this folder.

Add Markdown files here to adapt the kit to **fastapi-demo**. AI assistants are told
(by `AGENTS.md`) to read every file in this folder and to let it override kit files.

Good candidates:

- `conventions.md` — naming, folder layout or library choices specific to this project.
- `domain.md` — glossary and business rules of the domain.
- `exceptions.md` — a kit rule you deliberately do not follow, with the rule ID, the reason
  and a link to the ADR (for example: "ARCH-12 not applied, see docs/adr/0004-...").

Keep each file short and specific; do not copy kit content here.
