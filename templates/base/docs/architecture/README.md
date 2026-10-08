# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).
>
> Scope: database **{{ database_title }}**; deployment **{{ deployment_title }}**.
> Elements marked *(if deployed)* and the Deployment section apply only when deployment is
> in scope. Persistence is added only when the requirements need it and the database has
> been chosen. Remove what does not apply.

## Overview

{{ architecture }}

## System context

```mermaid
flowchart LR
    user([User]) --> system[{{ project_name }}]
    system --> ext[(External systems)]
```

## Components

TODO: main modules and their responsibilities. Add a component diagram when there are more
than three modules.

## Deployment (if deployed)

TODO: describe the runtime environment ({{ deployment_title }}).

## Decisions

See `docs/adr/`.
