# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).

## Overview

{{ architecture }}

Dependencies point inwards: the domain knows nothing about HTTP, the database or frameworks.

## System architecture

```mermaid
flowchart LR
    client([API clients]) -->|HTTPS| proxy[NGINX]
    proxy --> api[{{ project_name }} API]
    api --> db[("{{ database_title }}")]
    api --> ext[External services]
```

## Components

```mermaid
flowchart TB
    subgraph api_layer[API layer]
        routes[Routes / controllers<br/>validation, auth, mapping]
    end
    subgraph application[Application layer]
        services[Use cases / services<br/>transactions, orchestration]
    end
    subgraph domain[Domain layer]
        model[Entities, value objects,<br/>business rules, ports]
    end
    subgraph infrastructure[Infrastructure layer]
        repos[Repositories]
        clients[External API clients]
    end
    routes --> services --> model
    repos -. implements .-> model
    clients -. implements .-> model
```

## Request flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as Service
    participant Repo as Repository
    participant DB as Database
    C->>R: HTTP request
    R->>R: authenticate, validate input
    R->>S: command / query
    S->>Repo: load / save aggregate
    Repo->>DB: parameterised query
    DB-->>Repo: rows
    Repo-->>S: domain objects
    S-->>R: result
    R-->>C: HTTP response (or RFC 9457 problem details)
```

## Deployment

```mermaid
flowchart LR
    git[{{ org_git_server }}] --> ci[CI pipeline] --> registry[(Image registry)]
    registry --> staging[RKE Staging]
    staging -->|same image, after approval| prod[RKE Prod]
```

## Decisions

See `docs/adr/`.
