# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `core status MISSING` | `ai-project` not on `PATH` and not importable | Install the core (see [Installation](INSTALLATION.md)); reopen Claude Code so `PATH` refreshes |
| `core status INCOMPATIBLE` | Core outside `>=1.2.0,<1.3.0` | Reinstall pinned: `pipx install --force "git+<KIT_REPOSITORY_URL>@v1.2.0"` |
| State `DIRECT` | Core missing, incompatible, timed out or returned invalid JSON | Run `/netsf-ai-software-engineering:setup`; work continues with essential rules meanwhile |
| State `DEGRADED` | Project not initialised with the Kit, or graph missing/invalid | Optional: `ai-project init .` then `ai-project context --rebuild-graph` |
| State `BLOCKED` with a path message | Core output contained an unsafe path or line range | Run `ai-project doctor`; check `.ai/` for tampering; reinstall the core |
| `python: command not found` (skills) | Python not on `PATH` | Skills retry with `py -3`; otherwise install Python 3.9+ and tick "Add to PATH" |
| The safety guard never asks anything | Hook could not start (`python` missing for the hook shell) | Ensure `python` resolves in Git Bash/PowerShell; run `echo '{}' \| python scripts/netsf_guard.py` — it must print an `ask` decision |
| Too many confirmations | A guard rule matched a safe command | Accept once; report the command so a negative test and rule fix can be added |
| `UnicodeEncodeError` on Windows | Old console encoding | Entry scripts force UTF-8; update the plugin if you see this |
| Untrusted / injection warnings in context | A project file contains instruction-like text, or a Kit file was edited locally | Review the file; `ai-project update` restores managed Kit files |
| Plugin not listed after install | Marketplace not added or cache stale | `/plugin marketplace update netsf`, then reinstall |

## Diagnostics

```
python "<plugin>/scripts/netsf_bridge.py" check --json
python "<plugin>/scripts/netsf_bridge.py" detect --snapshot
ai-project doctor
claude plugin validate --strict "<plugin>"
```

Never paste `.env` files or credentials into an issue.
