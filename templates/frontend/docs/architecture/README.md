# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).
>
> Scope: database **{{ database_title }}**; deployment **{{ deployment_title }}**.
> Elements marked *(if deployed)* and the Deployment section apply only when deployment is
> in scope. Persistence is added only when the requirements need it and the database has
> been chosen. Remove what does not apply.

## Overview

{{ architecture }}

## System architecture

```mermaid
flowchart LR
    browser([Browser]) -->|HTTPS| nginx[NGINX<br/>(if deployed)<br/>static files + CSP headers]
    browser -->|HTTPS / JSON| api[Backend API]
    browser --> idp[Identity provider]
```

## Components

```mermaid
flowchart TB
    pages[Pages / routes] --> features[Feature components<br/>state, forms, validation]
    features --> ui[Shared UI components<br/>design system, accessibility]
    features --> services[API services<br/>HTTP client, error mapping]
    services --> api[(Backend API)]
```

## Data flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Feature component
    participant S as API service
    participant A as Backend API
    U->>F: action
    F->>F: client-side validation, loading state
    F->>S: request
    S->>A: HTTPS + auth token
    A-->>S: JSON / problem details
    S-->>F: typed result or mapped error
    F-->>U: data, empty state or error message
```

## Deployment (if deployed)

Static assets built in CI, packaged into an NGINX image and deployed to RKE Staging, then
the same image is promoted to RKE Prod.

## Decisions

See `docs/adr/`.
