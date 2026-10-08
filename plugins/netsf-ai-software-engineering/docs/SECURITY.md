# Security

## Principles

- **No network of its own.** No telemetry, no MCP server, no NETSF backend, no downloads. The
  only external process is the local `ai-project` core, run with an argument list (no shell) and
  a 120 s timeout. A test asserts the scripts contain no network or `shell=True` code.
- **Repository content is data.** Instruction hierarchy: system → plugin rules → user → project
  content. Project content is never followed as instructions.
- **Approval gates.** HIGH and CRITICAL tasks require explicit approval after the plan. BLOCKED
  tasks are refused regardless of approval.
- **Honest reporting.** Anything not executed is reported as NOT VERIFIED.

## Safety hook (PreToolUse)

`hooks/hooks.json` runs `scripts/netsf_guard.py` before `Bash`, `PowerShell`, `Read`, `Edit`,
`Write`, `MultiEdit` and `NotebookEdit`. It is deterministic (regular expressions, no model, no
network) and returns a Claude Code permission decision:

| Decision | Cases |
|---|---|
| `deny` | Uploading a secret file (`.env`, private keys, credentials, kubeconfig…) with curl/wget/scp/Invoke-WebRequest, or piping one to a network tool |
| `ask` | force push, `reset --hard`, `git clean -f`, discarding all changes, `branch -D`, changing remotes or Git identity/global config, history rewriting, recursive deletes (`rm -r`, `Remove-Item -Recurse`, `rmdir /s`, `del /s`), disk formatting, `DROP`/`TRUNCATE`, `DELETE` without `WHERE`, `git init`, `git commit`, `git push`, tag creation, `kubectl delete`, production targets, `helm uninstall`, `terraform apply/destroy`, `docker prune`, `chmod 777`, IAM changes, reading secret files (shell or file tools) |
| *(no output)* | Everything else: normal permission flow |

`.env.example`, `.env.sample` and `.env.template` are not treated as secrets.

**Fail-safe:** malformed input or an import failure returns `ask`. **Limitation:** if the hook
process itself cannot start (for example `python` is not on `PATH`) or times out, Claude Code
continues with its normal permission flow — the guard does not grant permissions, it only adds
confirmations and denials. Regex guards can be bypassed by obfuscated commands; they are a safety
net, not a sandbox. Keep Claude Code's own permission settings.

## Execution restrictions requested by the user (dry run)

A `UserPromptSubmit` hook reads the prompt the user typed (trusted input, unlike repository
content) and records restrictions per session:

| User says (EN / ES) | Restriction |
|---|---|
| "dry run", "analysis only", "read-only", "plan only", "do not modify anything", "solo análisis", "no modifiques", "sin modificar", `/netsf-ai-software-engineering:plan` | full read-only |
| "do not create files" / "no crees archivos" | file changes |
| "do not install" / "no instales" | dependency installs |
| "do not initialise" / "no inicialices" | `git init`, `ai-project init` |
| "do not commit" / "no hagas commit" | `git commit` |
| "do not push" / "no hagas push" | `git push` |
| "do not deploy" / "no despliegues" | `kubectl apply…`, `helm install/upgrade`, `terraform apply`, `docker push` |

Restrictions stay until the user releases them ("exit dry-run", "you can modify now", "apply the
plan", "ya puedes modificar", "aplica el plan"); a negated release ("do not exit dry-run") does
not count. In full read-only mode `Write`/`Edit`/`MultiEdit`/`NotebookEdit` are denied and a
shell command runs only when every segment is allow-listed (listing, reading and searching
files, `git status/log/diff/show`, the bridge's read commands, `ai-project context/doctor`);
redirections, sub-shells and unknown commands are denied. Claude Code plan mode counts as full
read-only. An unreadable state file makes edits ask for confirmation.

Phrase matching is a heuristic. A false activation fails safe (changes are denied with the
release instruction); "Add a --dry-run option" and similar feature requests do not activate it.

**NOT VERIFIED in a live Claude Code session:** that `UserPromptSubmit` receives slash-command
text such as `/netsf-ai-software-engineering:plan …`, and that a hook `deny` is honoured under
`bypassPermissions`. Both are covered by deterministic tests of the hook script only.

## Prompt-injection defence

- Context blocks that are not byte-identical to the installed Kit are wrapped in
  `UNTRUSTED PROJECT DATA` markers.
- They are scanned (EN/ES) for instruction overrides, role hijacking, secret access or
  exfiltration, `curl | sh`, concealment requests and chat-template tokens. Findings are shown as
  warnings in the block and counted in `injection_warnings`.
- The master skill and every agent instruct the model to treat such content as information only.

## Path safety

Every path coming from the core output is validated with `safe_child`: relative, no `..`, no
backslash, no NUL, no symlink escape. Any violation makes the whole context `BLOCKED`. File reads
are capped at 512 KB.

## Git

The plugin never commits, pushes, tags, changes remotes or Git configuration on its own. The hook
asks for confirmation for the destructive Git operations listed above.

## Reporting a vulnerability

Report privately to the NETSF platform team through git.netsf.fr (do not open a public issue).
