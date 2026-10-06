# Troubleshooting

## `ai-project`: command not found

The scripts directory of your Python installation is not on `PATH`.

- Use `pipx install ...` (it manages `PATH`; run `pipx ensurepath` once), or
- run the module directly: `python -m ai_project ...`, or
- Windows: add `%APPDATA%\Python\Python3XX\Scripts` (user install) or the venv `Scripts`
  folder to `PATH`.

## Installation fails on Windows with "No such file or directory" under `site-packages`

The install path exceeds the 260-character Windows limit (deep virtual environment folders).
Either use a shorter venv path (for example `C:\venvs\ai-kit`) or enable long paths (an
administrator runs `New-ItemProperty -Path HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem
-Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force`).

## Strange characters instead of ✓ / ✗, or escape codes like `[32m`

The kit falls back to ASCII markers (`OK`, `!!`, `XX`) when the terminal encoding cannot
show symbols. If you see raw escape codes, set `NO_COLOR=1`.

## "already initialised" on `init`

`.ai/kit.lock.json` exists. Use `ai-project update` to refresh kit files, or
`ai-project init . --force` to re-run the initialisation with different options.

## `*.kit-new` files appeared

A kit-managed file was modified locally and the kit also changed it. Merge by hand, delete the
`.kit-new` file, and move project-specific content to `.ai/custom/`.
See [VERSIONING.md](VERSIONING.md#resolving-a-conflict).

## `doctor` reports "Project context - N TODO(s) left"

Complete `.ai/context/project.md`. The warning stays until every `TODO` marker is gone.

## `doctor` flags a secret that is not one

The scanner is heuristic. If it is a test fixture or an obvious fake, add the comment
`ai-kit: allow-secret` on that line, and justify it in review. If it is a real credential,
remove it, **rotate it**, and purge it from Git history.

## `doctor` warns "not hosted on git.netsf.fr"

Team standard. Add the remote:
`git remote add origin https://git.netsf.fr/<group>/<project>.git`.

## `update` says the project uses a newer kit

Someone updated the project with a newer CLI. Upgrade yours:
`pipx upgrade ai-software-engineering-kit` (or `pip install --upgrade ...`).

## "The installed kit no longer supports this project's selection"

The profile, technology or database recorded in `.ai/kit.lock.json` was removed or renamed
in the new kit. Check the changelog for the replacement, then re-run
`ai-project init . --force` with the new values.

## The AI assistant ignores the kit

- Check that the assistant opened the project root (where `AGENTS.md` is).
- For Claude Code, Copilot or Cursor, make sure the assistant was selected at `init` (pointer
  files `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/ai-kit.mdc`).
- Ask explicitly: "Read AGENTS.md and follow `.ai/workflows/new-feature.md`."
