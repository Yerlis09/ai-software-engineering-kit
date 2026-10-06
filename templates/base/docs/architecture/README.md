# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).

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

## Deployment

TODO: describe the runtime environment ({{ deployment_title }}).

## Decisions

See `docs/adr/`.
