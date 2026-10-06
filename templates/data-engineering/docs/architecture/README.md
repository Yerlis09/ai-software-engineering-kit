# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).

## Overview

{{ architecture }}

## Data flow

```mermaid
flowchart LR
    sources[(Sources<br/>APIs, files, OLTP DBs)] --> extract[Extract<br/>incremental, checkpointed]
    extract --> staging[(Raw / staging)]
    staging --> transform[Transform<br/>schema validation]
    transform --> quality{Data quality checks}
    quality -->|pass| load[Load]
    quality -->|fail| quarantine[(Quarantine + alert)]
    load --> warehouse[("{{ database_title }}")]
    warehouse --> consumers[Dashboards / consumers]
```

## Components

```mermaid
flowchart TB
    orchestration[Orchestration<br/>scheduling, retries, backfills] --> extract[extract/]
    orchestration --> transform[transform/]
    orchestration --> load[load/]
    transform --> quality[quality/]
```

## Pipeline run

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant E as Extract
    participant T as Transform
    participant Q as Quality
    participant L as Load
    O->>E: run(window)
    E-->>O: batch + checkpoint
    O->>T: transform(batch)
    T->>Q: validate(rows)
    Q-->>T: report
    T-->>O: valid rows
    O->>L: load (idempotent, batched)
    L-->>O: row counts
```

## Deployment

Docker image; jobs run as Kubernetes CronJobs (or an orchestrator) on RKE Staging, then
the same image is promoted to RKE Prod.

## Decisions

See `docs/adr/`.
