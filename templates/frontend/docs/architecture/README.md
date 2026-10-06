# Architecture — {{ project_name }}

> Project-owned. Keep diagrams in sync with the code (see `.ai/agents/11-documentation.md`).

## Overview

{{ architecture }}

## System architecture

```mermaid
flowchart LR
    browser([Browser]) -->|HTTPS| nginx[NGINX<br/>static files + CSP headers]
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

## Deployment

Static assets built in CI, packaged into an NGINX image and deployed to RKE Staging, then
the same image is promoted to RKE Prod.

## Decisions

See `docs/adr/`.
