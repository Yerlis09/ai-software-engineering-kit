# Stack — TypeScript

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds TypeScript-specific guidance.

Applies to frontend (`stacks/react/README.md`, `stacks/angular/README.md`) and Node.js code (`stacks/node/README.md`).

## Recommended tooling

- Compiler/type checker: `tsc --noEmit` in CI (bundlers like Vite/esbuild strip types without checking them).
- Lint: ESLint flat config + `typescript-eslint` (`strictTypeChecked` preset where feasible).
- Format: Prettier.
- Tests: Vitest (or Jest with `ts-jest`); Playwright for E2E.
- Package manager: `npm` or `pnpm`, lock file committed.
- Runtime validation: Zod (or Valibot) at I/O boundaries.

## Project structure

```
src/
  api/ | http/      # Controller / transport: routes or API client adapters
  application/      # Use cases, services
  domain/           # Types, entities, pure business logic
  repositories/     # Data access abstractions
  infrastructure/   # Concrete clients, config, logging
  types/            # Shared ambient/global types (keep minimal)
tsconfig.json  eslint.config.js  package.json
```

## Conventions

- `tsconfig.json`: `"strict": true`, `"noUncheckedIndexedAccess": true`, `"noImplicitOverride": true`, `"exactOptionalPropertyTypes": true` (if practical), `"verbatimModuleSyntax": true`.
- No `any`. Use `unknown` and narrow it; justify any `// @ts-expect-error` with a comment. Never `@ts-ignore`.
- Prefer `type`/`interface` consistently (team choice); model states with discriminated unions instead of optional flags.
- Use `readonly` and `as const` for immutable data; `satisfies` to check literals without widening.
- Exhaustive `switch` with a `never` check.
- Avoid `enum` (prefer union of string literals or `as const` objects).
- Avoid non-null assertions (`!`) and unchecked casts (`as Foo`); validate external data instead.
- Use `import type` for type-only imports.

## Security

- Types are erased at runtime: **validate** all external data (HTTP bodies, API responses, env, storage) with a schema.
- Do not put secrets in frontend bundles; any `VITE_*`/public env var is visible to users.
- Keep `strict` on; loosening types often hides injection/undefined-access bugs.
- Run dependency audits in CI (`npm audit`, OSV-Scanner).

## Performance

- Type-checking speed: use project references / `incremental`, avoid huge union types and deep conditional types.
- `skipLibCheck: true` is acceptable for build speed.
- Tree-shaking: use ES modules, avoid barrel files that re-export everything in large apps.

## Testing

- Test behavior, not types; for library types use `expectTypeOf` (Vitest) or `tsd`.
- Type-check test files too (include them in a `tsconfig` checked in CI).

## Pitfalls

- Trusting `as` casts on `fetch().json()` results.
- `any` leaking from untyped libraries (add/declare types, wrap the library).
- Relying on the bundler for type safety (it does not check types).
- Overengineered generic types that nobody can read; prefer simple, explicit types.

## Example

```ts
import { z } from "zod";

const User = z.object({ id: z.number().int(), email: z.string().email(), role: z.enum(["admin", "user"]) });
type User = z.infer<typeof User>;

export async function fetchUser(id: number, signal?: AbortSignal): Promise<User> {
  const res = await fetch(`/api/v1/users/${id}`, { signal });
  if (!res.ok) throw new Error(`fetchUser failed: ${res.status}`);
  return User.parse(await res.json()); // runtime validation, not a cast
}
```
