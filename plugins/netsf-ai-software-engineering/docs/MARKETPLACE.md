# Marketplace

## Layout

```
<repository root>/
  .claude-plugin/marketplace.json          marketplace "netsf"
  plugins/netsf-ai-software-engineering/   the plugin (only this directory is copied to the cache)
```

`marketplace.json` lists the plugin with `source: "./plugins/netsf-ai-software-engineering"`,
`version: "1.0.0"`, category `development`. The plugin must therefore not reference files outside
its own directory (the Kit knowledge is reached through the installed core, not by path).

## Publishing checklist

1. Tests, ruff and mypy green (see [Development](DEVELOPMENT.md)).
2. `claude plugin validate --strict plugins/netsf-ai-software-engineering` and
   `claude plugin validate --strict .` both pass.
3. Versions match: `plugin.json`, `scripts/netsf/__init__.py`, the marketplace entry.
4. CHANGELOG updated.
5. Merge to the default branch of the repository on git.netsf.fr through a reviewed merge request.
6. Optional: tag the release (for example with `claude plugin tag`) — only by a maintainer.

Users then run:

```
/plugin marketplace add <KIT_REPOSITORY_URL>
/plugin install netsf-ai-software-engineering@netsf
/plugin marketplace update netsf     # to receive new versions
```

## Notes

- License is `LicenseRef-NETSF-Internal`: distribute only inside NETSF.
- The repository currently has a GitHub remote; the organisation standard is git.netsf.fr.
  Point the marketplace URL given to users at the internal server.
- The plugin has no MCP servers, binaries or network access, which keeps the review surface small.
