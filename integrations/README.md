# Integrations

The kit's knowledge is plain Markdown under `.ai/`, with `AGENTS.md` as the single entry point.
Each integration only adds a **thin pointer** file in the location a given assistant reads —
the knowledge itself is never duplicated per vendor.

| Assistant | Folder | Generated file |
|---|---|---|
| Claude Code | `claude-code/files/` | `CLAUDE.md` |
| GitHub Copilot | `copilot/files/` | `.github/copilot-instructions.md` |
| Cursor | `cursor/files/` | `.cursor/rules/ai-kit.mdc` |
| Codex (and other AGENTS.md-native tools) | `codex/` | nothing: reads `AGENTS.md` directly |

## Adding an assistant

1. Create `integrations/<name>/files/` mirroring the paths to generate in the project.
2. Keep the file a pointer to `AGENTS.md` (templates may use `{{ project_name }}`-style variables).
3. Register it in `catalog/assistants.json`.
4. Add a test in `tests/test_generation.py` and an entry in `CHANGELOG.md`.

Generated integration files are CORE (kit-managed) and refreshed by `ai-project update`.
