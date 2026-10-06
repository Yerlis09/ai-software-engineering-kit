# Stack — Linux

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Linux-specific guidance.

Covers shell scripting, container base images and server/host conventions. Applications run in containers on Kubernetes (`stacks/kubernetes/README.md`); prefer that over hand-managed servers.

## Recommended tooling

- Shell lint: `shellcheck`; format: `shfmt -i 2 -ci`.
- Tests for scripts: `bats-core`.
- Prefer Python (`stacks/python/README.md`) for scripts longer than ~50 lines or with non-trivial logic.
- Host management (if any): Ansible, idempotent roles, stored on git.netsf.fr.
- Diagnostics: `ss`, `journalctl`, `top`/`htop`, `iostat`, `vmstat`, `strace`, `lsof`.

## Project structure

```
scripts/
  lib/common.sh        # shared functions (logging, retries)
  deploy-check.sh      # small, single-purpose scripts
tests/scripts/*.bats
```

## Conventions

- Start scripts with `#!/usr/bin/env bash` and `set -euo pipefail`; set `IFS=$'\n\t'` when iterating over lines.
- Quote every variable expansion (`"$var"`, `"$@"`); use `[[ ... ]]` in bash; `$(...)` not backticks.
- Use functions and `local` variables; a `main "$@"` entry point; `usage()` with `-h`.
- Clean up with `trap cleanup EXIT`; create temp files with `mktemp`.
- Log to stderr with timestamps; exit codes: `0` success, non-zero meaningful failures.
- Scripts must be idempotent and safe to re-run.
- Use long options in scripts for readability (`--recursive`), and absolute paths or `cd "$(dirname "$0")"` deliberately.
- LF line endings (enforce with `.gitattributes`: `*.sh text eol=lf`) — CRLF breaks shebangs.

## Security

- Never put credentials in scripts, crontabs, shell history or `.env` files; read them from the environment injected by Kubernetes Secrets / CI variables, or a vault CLI.
- Avoid `eval` and unquoted user input; validate arguments.
- Least privilege: no `sudo` in application scripts; containers run as non-root.
- Restrictive file permissions for sensitive files (`umask 077`, `chmod 600`).
- `curl` with `--fail --show-error --silent --proto '=https'`; verify checksums of downloaded binaries; never `curl | bash` from the internet.
- Hosts: SSH keys only (no password auth), no root login, automatic security updates, minimal packages, firewall enabled.

## Performance

- Prefer built-ins and single-pass tools (`awk`) over long pipelines of subprocesses in loops.
- Use `xargs -P` or GNU `parallel` for parallel batch work, with bounded concurrency.
- For containers: understand cgroup limits — tools that read `/proc/cpuinfo` may oversize thread pools; configure workers explicitly.

## Testing

- `shellcheck` and `shfmt -d` in CI for every `*.sh`.
- `bats` tests for scripts with logic; run them in the same base image used in production.

## Pitfalls

- Missing `set -euo pipefail` → failures silently ignored.
- Unquoted variables with spaces or globs (`rm -rf $DIR/*` with empty `DIR`).
- Parsing `ls` output; using `for f in $(cat file)`.
- CRLF line endings from Windows editors.
- Relying on GNU-specific flags in Alpine/busybox images (or vice versa).

## Example

```bash
#!/usr/bin/env bash
set -euo pipefail

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }

main() {
  local url="${1:?usage: $0 <health-url>}"
  local attempt
  for attempt in 1 2 3 4 5; do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
      log "healthy after ${attempt} attempt(s)"
      return 0
    fi
    log "attempt ${attempt} failed, retrying"
    sleep $((attempt * 2))
  done
  log "service unhealthy: ${url}"
  return 1
}

main "$@"
```
