# Compatibility

| Plugin | Core (`ai-project`) | Python | Claude Code |
|---|---|---|---|
| 1.0.0 | `>=1.2.0,<1.3.0` | 3.9 – 3.13 (tested 3.9 and 3.12) | validated with 2.1.292 |

The range is declared in `.claude-plugin/plugin.json` (`metadata.coreCompatibility`) and enforced
at runtime by `scripts/netsf/__init__.py` (`CORE_MIN`, `CORE_MAX`). Outside the range the bridge
reports `INCOMPATIBLE` and falls back to `DIRECT` mode.

## Core public API used

- `ai-project version` — first line `ai-project X.Y.Z`, a `Kit: <path>` line.
- `ai-project context --task T --path P --json [--profile --technology --database]` — fields
  `selected_agents`, `selected_rules` (with `sections[].lines`), `selected_workflows`,
  `selected_stacks`, `selected_core`, `metrics`, `notes`, `classification`.
- Installed Kit layout: `agents/`, `rules/`, `workflows/`, `stacks/<s>/README.md`.
- Project lock: `.ai/kit.lock.json` (`managed_files` hashes).

Any change to these in the core is a breaking change for the plugin and needs a coordinated
release.

## Versioning policy

- **Plugin patch** (1.0.x): fixes, guard/risk rule tuning, docs.
- **Plugin minor** (1.x.0): new skills, agents or bridge commands; same core range.
- **Core minor** (1.3.0): requires a plugin release that widens or moves the range after tests.
- Platforms: Windows (primary, tested), Linux and macOS (expected; symlink test only runs there).
