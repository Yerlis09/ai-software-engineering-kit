# Customisation

There are two levels: adapting **one project**, and extending **the kit** for everyone.

## Customising a project

| You want to... | Do this |
|---|---|
| Describe the project to the AI | Edit `.ai/context/project.md` (project-owned) |
| Add project conventions, glossary or domain rules | Add Markdown files to `.ai/custom/`. `AGENTS.md` tells assistants to read them and to let them override kit files |
| Deliberately not follow a kit rule | Add an entry to `.ai/custom/exceptions.md` with the rule ID, the reason and an ADR link |
| Change README, docs or `.gitignore` | Edit freely: project-owned |
| Change a kit file (`AGENTS.md`, `.ai/agents/...`) | Avoid it. Your edit is kept, but each kit update touching that file creates a `.kit-new` to merge. Prefer `.ai/custom/` |
| Add or remove a stack guide or agent | Re-run `init --force` with other options, or add your own file in `.ai/custom/` |

Example `.ai/custom/conventions.md`:

```markdown
# Conventions
- Monetary amounts are integers in cents (never floats).
- Exception to ARCH-12: synchronous calls to the billing service, see docs/adr/0004.
```

## Extending the kit

All of these are data changes. Add a test when you add content: the test suite already
validates every profile and technology combination.

### Add a stack guide

1. Create `stacks/<name>/README.md` using the standard sections (see any existing guide).
2. Reference it from a technology in `catalog/technologies.json`, a database, a deployment,
   or a profile's `stacks` list, or let users pick it with `--stacks <name>`.

### Add a technology preset

Add an entry in `catalog/technologies.json` (`title`, `stacks`) and add its key to the
`technologies` list of the relevant profiles.

### Add a profile

1. Create `profiles/<name>.json` with the fields: `name`, `title`, `description`, `agents`,
   `agents_if_database`, `rules`, `workflows`, `technologies`, `stacks`, `template`,
   `structure`.
2. Optionally add `templates/<template>/` overlays (for example
   `docs/architecture/README.md`). Files with the same path override `templates/base/`.
3. Optionally add a sentence for it in `profile_architecture()` (`cli/ai_project/generator.py`).

### Add a template file

Put it under `templates/base/` or a profile overlay. Template syntax is only
`{{ variable }}`. Unknown variables fail the tests. Name dotfiles `dot-<name>`
(`dot-gitignore` becomes `.gitignore`). List the output path in `templates/manifest.json`
if it must be CORE (kit-managed).

Available variables: `project_name`, `package_name`, `description`, `problem`, `users`,
`owner`, `functional_requirements`, `non_functional_requirements`, `external_services`,
`security_requirements`, `performance_requirements`, `constraints`, `risks`, `created_date`,
`kit_version`, `profile`, `profile_title`, `profile_description`, `technology`,
`technology_title`, `language`, `framework` (from `catalog/technologies.json`, `TODO` when
unknown), `database`, `database_title`, `deployment`, `deployment_title`,
`architecture`, `agents_table`, `rules_list`, `workflows_list`, `stacks_list`,
`structure_list`, and `org_<key>` for each key of `catalog/organization.json`.

### Tune context routing

`catalog/context.json` holds the routing metadata: triggers (weight 1–5, `word`,
`multi word` or `prefix*`), layer (`L0`, `L1`, `L3`, `router`), `requires` with levels,
`recommended`, rule sections (`always` or triggers), stack domains and companions. Run
`pytest tests/test_context.py` after editing: the reference cases and the validation (unknown
references, cycles) protect against regressions. In a project, adjust the budget in
`.ai/context/budget.json`. A custom agent dropped into `.ai/agents/` is listed as "no routing
metadata" and loaded only when you ask for it.

### Add an AI assistant

See [integrations/README.md](../integrations/README.md).

### Change organisation defaults

Edit `catalog/organization.json`: Git server, security contact, deployment environments. They
are used in templates (`org_*` variables) and by `doctor`.

### Team fork

A team can maintain its own variant of the kit and point the CLI at it with
`AI_KIT_HOME=/path/to/kit` without reinstalling. Keep the fork rebased on the main kit.

After any kit change: bump the version and update the changelog ([VERSIONING.md](VERSIONING.md)),
then run `ai-project update` on `examples/fastapi-demo`. A test fails if the demo is out of sync.
