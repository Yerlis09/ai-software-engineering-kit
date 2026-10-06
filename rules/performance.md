# Performance Rules

> Kit file — managed by `ai-project update`. Put project-specific overrides in `custom/`.

These rules are technology-agnostic. Stack-specific tuning lives in `stacks/<name>/README.md`.
Kit paths (`rules/`, `agents/`) are relative to the AI root.
Levels follow RFC 2119: **MUST**, **SHOULD**, **MAY**. Owner agent: `agents/08-performance.md`.

## Approach

- **PERF-01** — MUST measure before optimising; base every optimisation on profiling or metrics, not intuition.
- **PERF-02** — MUST NOT apply premature optimisation that harms readability without a measured need.
- **PERF-03** — MUST verify the gain of an optimisation with a before/after measurement and record it in the merge request.
- **PERF-04** — SHOULD choose appropriate algorithms and data structures from the start (avoid accidental O(n²)).

## Budgets

- **PERF-05** — MUST define performance budgets for critical paths (e.g. p95 latency, throughput, page weight) in `context/project.md` or `docs/`.
- **PERF-06** — SHOULD track budgets in CI or monitoring and alert on regressions.
- **PERF-07** — SHOULD set front-end budgets (bundle size, LCP, INP, CLS) for user-facing web apps.

## Data access

- **PERF-08** — MUST avoid N+1 queries; use joins, batch loading or eager loading.
- **PERF-09** — MUST paginate every list endpoint and query that can grow unbounded; enforce a maximum page size.
- **PERF-10** — MUST select only the columns/fields needed; no `SELECT *` on hot paths.
- **PERF-11** — MUST index columns used in frequent filters, joins and sorts; validate with the query plan.
- **PERF-12** — SHOULD use connection pooling for databases and HTTP clients.
- **PERF-13** — SHOULD batch writes and network calls where possible.
- **PERF-14** — MUST NOT load large datasets fully into memory; stream or chunk them.

## Timeouts and resilience

- **PERF-15** — MUST set explicit timeouts on every network call, database query and external dependency.
- **PERF-16** — MUST bound retries (count + exponential backoff with jitter) and only retry idempotent operations.
- **PERF-17** — SHOULD use circuit breakers or bulkheads for unreliable dependencies.
- **PERF-18** — MUST bound queues, thread pools and buffers to prevent resource exhaustion.
- **PERF-19** — SHOULD apply rate limiting and backpressure on public entry points.

## Caching

- **PERF-20** — MUST define an invalidation strategy (TTL, event-based, versioned keys) before adding any cache.
- **PERF-21** — MUST NOT cache personalised or authorised data under shared keys.
- **PERF-22** — SHOULD use HTTP caching headers (Cache-Control, ETag) for cacheable responses and static assets.
- **PERF-23** — SHOULD protect against cache stampede (request coalescing, jittered TTL).
- **PERF-24** — SHOULD monitor cache hit ratio; remove caches that do not pay off.

## Concurrency and work offloading

- **PERF-25** — SHOULD move slow or non-interactive work (emails, reports, imports) to background jobs.
- **PERF-26** — MUST NOT block the event loop or request threads with CPU-heavy or blocking I/O work.
- **PERF-27** — SHOULD make background jobs idempotent and observable.

## Resources and runtime

- **PERF-28** — MUST set CPU/memory requests and limits for containers based on measurements.
- **PERF-29** — SHOULD configure horizontal autoscaling on measured signals for variable load.
- **PERF-30** — SHOULD keep container images small and startup time short.
- **PERF-31** — SHOULD compress responses (gzip/brotli) and serve static assets through NGINX or a CDN.

## Observability

- **PERF-32** — MUST expose latency, throughput, error rate and saturation metrics for each service.
- **PERF-33** — SHOULD trace slow requests end-to-end; see `agents/13-observability.md`.
- **PERF-34** — SHOULD log slow queries above a defined threshold.

## Testing

- **PERF-35** — SHOULD load-test critical paths before major releases, against Staging, never Prod without approval.
- **PERF-36** — SHOULD add a benchmark or performance test when fixing a performance regression.
