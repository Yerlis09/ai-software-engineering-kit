# NETSF AI Software Engineering

A Claude Code plugin that works like a small professional software team: it understands what you
ask in plain language, plans the work, picks the right specialists, loads only the engineering
standards that matter for the task, implements, tests and reports — and asks for your approval
before anything risky.

It is a thin layer over the **AI Software Engineering Kit** (the "core", `ai-project`), which
holds the engineering knowledge. Plugin `1.0.0` works with core `>=1.2.0,<1.3.0`.

---

## Quick start (beginners)

You only need Claude Code and Python 3.9 or newer.

**1. Add the NETSF marketplace and install the plugin** (inside Claude Code):

```
/plugin marketplace add <KIT_REPOSITORY_URL>
/plugin install netsf-ai-software-engineering@netsf
```

Ask your team for `<KIT_REPOSITORY_URL>` (the Kit repository on git.netsf.fr).

**2. Check that everything is ready:**

```
/netsf-ai-software-engineering:setup
```

It tells you whether the core is installed and, if not, shows the one command to install it. It
never installs anything without your "yes".

**3. Just describe what you want.** For example:

> Create an API endpoint that returns the list of cells from the database.

> The monthly report script fails when the Excel file is empty. Fix it.

The plugin will explain the plan, do the work, run the tests and tell you what changed.

**4. Want to see the plan first without changing anything?**

```
/netsf-ai-software-engineering:plan Add a column "region" to the customers table
```

### What you will see

| Message | What it means |
|---|---|
| `Risk: LOW / MEDIUM` | Normal work. It proceeds and reports. |
| `Risk: HIGH / CRITICAL — approval required` | It stops and waits for you to say "yes, proceed". |
| `BLOCKED` | The request is unsafe (for example, uploading passwords). It will not do it. |
| A confirmation prompt from Claude Code | The safety guard caught a dangerous command (force push, deleting folders, reading `.env`…). Read it before accepting. |
| `NOT VERIFIED` | Something could not be checked. It is never reported as passed. |

---

## Commands

| Command | For | What it does |
|---|---|---|
| *(just describe the task)* | everyone | The NETSF AI Engineer handles it end to end. |
| `/netsf-ai-software-engineering:plan <task>` | everyone | Dry-run plan. Changes no files. |
| `/netsf-ai-software-engineering:setup` | everyone | Checks Python and the core; guides installation. |
| `/netsf-ai-software-engineering:context <task>` | advanced | Shows which context would be loaded, why, and its size. |

Specialist agents (`netsf-ai-software-engineering:backend`, `:frontend`, `:security`, …) are used
automatically; you do not need to call them.

## What it measured

On 9 representative tasks (FastAPI, ClickHouse, React, Docker, Kubernetes, automation,
microservice, Python backend and a Kit-initialised project), the routed context was **82% smaller**
than loading every standard (67,774 vs 376,255 estimated tokens), with routing in tens of milliseconds
(12–53 ms measured; it varies with the machine and its load).
Details and how to reproduce: [docs/BENCHMARKING.md](docs/BENCHMARKING.md). Answer quality has not
been measured with a real model evaluation yet (NOT VERIFIED).

## Privacy and safety

No telemetry, no MCP servers, no network calls of its own, no NETSF backend. A small local safety
guard asks for confirmation before destructive commands and blocks uploading secret files.

It is a safety net, not a guarantee: it needs `python` on the `PATH`, and if it cannot start,
Claude Code silently falls back to its normal permission prompts. It recognises common commands
only, so always read what Claude is about to run. See [docs/SECURITY.md](docs/SECURITY.md).

## More documentation (advanced)

[Architecture](docs/ARCHITECTURE.md) · [Installation](docs/INSTALLATION.md) ·
[Usage](docs/USAGE.md) · [Security](docs/SECURITY.md) · [Development](docs/DEVELOPMENT.md) ·
[Troubleshooting](docs/TROUBLESHOOTING.md) · [Compatibility](docs/COMPATIBILITY.md) ·
[Benchmarking](docs/BENCHMARKING.md) · [Marketplace](docs/MARKETPLACE.md)

For a non-technical team guide to the core, see the Kit's `docs/GUIA_EQUIPO.md` (Spanish).
