# 0001 — Record architecture decisions

- **Status:** Accepted
- **Date:** {{ created_date }}

## Context

{{ project_name }} is developed with AI assistants. Decisions made in chat sessions are lost
unless they are written down, and AI assistants need them to stay consistent.

## Decision

We record every significant architecture decision as an ADR in `docs/adr/`, following
`template.md`. AI assistants read the ADRs before proposing structural changes and must not
contradict an accepted ADR without proposing a superseding one.

## Consequences

- Decisions are reviewable and traceable in Git.
- A small amount of writing per decision; trivial choices do not need an ADR.
