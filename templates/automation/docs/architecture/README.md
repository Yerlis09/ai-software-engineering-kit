# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).

## Overview

{{ architecture }}

Jobs are small, idempotent and safe to re-run. External systems are reached only through
adapters, so jobs and services are testable without network access.

## Components

```mermaid
flowchart LR
    trigger[Scheduler<br/>Kubernetes CronJob / CLI] --> job[Job]
    job --> service[Services<br/>business logic]
    service --> adapters[Adapters]
    adapters --> ext1[External API]
    adapters --> ext2[(Files / database)]
    config[Typed settings<br/>env vars + injected secrets] --> job
```

## Execution flow

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant J as Job
    participant Svc as Service
    participant A as Adapter
    S->>J: run (with run id)
    J->>Svc: execute(params)
    Svc->>A: fetch / push (timeout, retry with backoff)
    A-->>Svc: result or error
    Svc-->>J: summary
    J-->>S: exit code 0 / non-zero + structured logs
```

## Deployment

Packaged as a Docker image, scheduled as a Kubernetes CronJob on RKE Staging, then the
same image is promoted to RKE Prod.

## Decisions

See `docs/adr/`.
