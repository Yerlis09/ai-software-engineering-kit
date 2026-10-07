# Installation

## Requirements

- Claude Code with plugin support (validated with CLI 2.1.292).
- Python 3.9+ on `PATH` as `python` (the skills fall back to `py -3` on Windows; the hook uses
  `python`, see [Troubleshooting](TROUBLESHOOTING.md)).
- The AI Software Engineering Kit core `>=1.2.0,<1.3.0`.

## 1. Install the core (one time per machine)

```
pipx install "git+<KIT_REPOSITORY_URL>@v1.2.0"
# or
uv tool install "git+<KIT_REPOSITORY_URL>@v1.2.0"
```

`<KIT_REPOSITORY_URL>` is the Kit repository on the team's Git server (git.netsf.fr). Pinning the
tag keeps the core inside the supported range. Verify with `ai-project version`.

`/netsf-ai-software-engineering:setup` performs this check and prints the same command; it runs
it only after explicit approval.

## 2. Install the plugin from the marketplace

```
/plugin marketplace add <KIT_REPOSITORY_URL>
/plugin install netsf-ai-software-engineering@netsf
```

The marketplace manifest is `.claude-plugin/marketplace.json` at the repository root; the plugin
lives in `plugins/netsf-ai-software-engineering/`.

## 3. Try it without installing (development)

```
claude --plugin-dir plugins/netsf-ai-software-engineering
```

This loads the plugin for one session only and changes nothing in `~/.claude`.

## 4. Optional: initialise a project with the Kit

Inside a project, `ai-project init .` writes the `.ai/` standards (never overwriting existing
files). Routing then runs in `OPTIMIZED` mode instead of `DEGRADED`. Check with `ai-project doctor`.

## Uninstall

```
/plugin uninstall netsf-ai-software-engineering@netsf
pipx uninstall ai-software-engineering-kit   # or: uv tool uninstall ...
```
