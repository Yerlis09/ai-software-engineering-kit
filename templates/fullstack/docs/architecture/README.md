# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).
>
> Scope: database **{{ database_title }}**; deployment **{{ deployment_title }}**.
> Elements marked *(if deployed)* and the Deployment section apply only when deployment is
> in scope. Persistence is added only when the requirements need it and the database has
> been chosen. Remove what does not apply.

## Overview

{{ architecture }}

`frontend/` and `backend/` are separate deployables sharing one repository; the contract
between them is the API specification (OpenAPI), versioned with the code.

## System architecture

```mermaid
flowchart LR
    browser([Browser]) -->|HTTPS| nginx[NGINX<br/>(if deployed)]
    nginx -->|/ static| spa[Frontend SPA]
    nginx -->|/api| api[Backend API]
    api --> db[("{{ database_title }}")]
    api --> ext[External services]
```

## Components

```mermaid
flowchart TB
    subgraph frontend
        pages[Pages] --> features[Features] --> uisvc[API services]
    end
    subgraph backend
        routes[Routes] --> app[Application services] --> domain[Domain]
        repo[Repositories] -. implements .-> domain
    end
    uisvc -->|JSON over HTTPS| routes
    repo --> db[(Database)]
```

## Request flow

```mermaid
sequenceDiagram
    participant U as User
    participant SPA as Frontend
    participant API as Backend
    participant DB as Database
    U->>SPA: action
    SPA->>API: HTTPS request + token
    API->>API: authN, authZ, validation
    API->>DB: parameterised query
    DB-->>API: rows
    API-->>SPA: JSON
    SPA-->>U: updated view
```

## Deployment (if deployed)

```mermaid
flowchart LR
    git[{{ org_git_server }}] --> ci[CI pipeline] --> registry[(Images: frontend, backend)]
    registry --> staging[RKE Staging]
    staging -->|same images, after approval| prod[RKE Prod]
```

## Decisions

See `docs/adr/`.
