# Stack — Node.js

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Node.js-specific guidance.

Team default for backends is Python (`stacks/python/README.md`). Use Node.js for frontend tooling, BFFs or services where it is explicitly chosen. Prefer TypeScript (`stacks/typescript/README.md`).

## Recommended tooling

- Runtime: an active LTS version, pinned in `.nvmrc` / `engines` and in the Docker base image.
- Package manager: `npm` (or `pnpm`) with a committed lock file; install with `npm ci` in CI.
- Lint: ESLint (flat config) + `typescript-eslint`; format: Prettier.
- Type checking: `tsc --noEmit`.
- Tests: Vitest (or Jest / built-in `node:test`), Supertest for HTTP.
- Security: `npm audit` / OSV-Scanner, `eslint-plugin-security`, secret scanner in CI.
- Framework: Fastify or Express; validation with Zod or JSON Schema.

## Project structure

```
src/
  http/           # Controller: routes, handlers, request validation
  application/    # Use cases / services
  domain/         # Entities, domain errors (no framework imports)
  repositories/   # Data access interfaces + implementations
  infrastructure/ # DB client, external APIs, config, logger
  app.ts          # buildApp(): wiring, plugins, error handler
  server.ts       # listen + graceful shutdown
test/  package.json  package-lock.json  tsconfig.json  Dockerfile
```

## Conventions

- ES modules (`"type": "module"`), `async/await` everywhere; no callback-style APIs in new code.
- Validate all external input at the controller boundary (Zod/JSON Schema); never trust `req.body`.
- Centralized error handler; throw typed domain errors, map them to HTTP status codes in one place.
- Structured logging (pino) with request IDs; no `console.log` in production code.
- Configuration from `process.env` parsed once into a typed, validated config object at startup.
- Handle `SIGTERM`: stop accepting connections, finish in-flight requests, close pools, then exit.

## Security

- No credentials in `.env` files committed to git or copied into images; inject via Kubernetes Secrets / CI variables. Commit only `.env.example`.
- Never `eval`, `new Function`, `child_process.exec` with user input (use `execFile` with argument arrays).
- Use `helmet` (Express) or `@fastify/helmet`; strict CORS origins.
- Parameterized queries / query builders only; beware prototype pollution (avoid deep-merging untrusted objects).
- Limit body size; rate-limit auth endpoints.
- Review new dependencies (maintenance, install scripts); consider `npm ci --ignore-scripts` where possible.

## Performance

- Never block the event loop: no sync FS/crypto (`*Sync`) in request paths; offload CPU work to `worker_threads`.
- Use streams for large files/responses; set timeouts on outbound HTTP (`AbortSignal.timeout`).
- Reuse DB pools and HTTP agents (keep-alive).
- Scale horizontally with Kubernetes replicas, not `cluster` inside a container.
- Profile with `--cpu-prof`, clinic.js; watch event-loop lag metrics.

## Testing

- Unit tests for services with fakes; HTTP tests via `app.inject()` (Fastify) or Supertest.
- Integration tests against real dependencies in containers.
- Run with coverage (`vitest run --coverage`) and enforce thresholds from `rules/testing.md`.

## Pitfalls

- Unhandled promise rejections / floating promises (enable `@typescript-eslint/no-floating-promises`).
- `npm install` in CI instead of `npm ci`; lock file not committed.
- Running as root or with `npm start` as PID 1 without signal handling (use `node` directly or `tini`).
- Shipping `devDependencies` and source maps with secrets into the production image.
- Using `latest` tags for Node base images.
