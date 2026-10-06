# Stack — React

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds React-specific guidance.

Team frontend standard: HTML / JavaScript / React. TypeScript is recommended (`stacks/typescript/README.md`). See `agents/01-frontend.md`.

## Recommended tooling

- Build/dev server: Vite.
- Language: TypeScript (strict); plain JavaScript acceptable for small apps, with JSDoc types.
- Lint: ESLint + `eslint-plugin-react-hooks` + `eslint-plugin-jsx-a11y`; format: Prettier.
- Type check: `tsc --noEmit`.
- Unit/component tests: Vitest + React Testing Library + `@testing-library/user-event`; API mocking with MSW.
- E2E: Playwright (including `@axe-core/playwright` for accessibility checks).
- Server state: TanStack Query; routing: React Router (or the framework router in use).
- Package manager: `npm` or `pnpm`, lock file committed.

## Project structure

```
src/
  app/              # App shell, providers, router
  pages/            # Route-level components (thin, compose features)
  features/<name>/  # components/, hooks/, api/ (queries), types.ts, tests
  components/ui/    # Reusable presentational components
  services/         # API client (fetch wrapper), auth (infrastructure)
  lib/              # Pure utilities
  main.tsx
index.html  vite.config.ts  tsconfig.json
```

The layered rule applies: components (presentation) → hooks/services (application) → API client (infrastructure). Components never call `fetch` directly.

## Conventions

- Function components + hooks only; no class components in new code.
- Follow the Rules of Hooks; keep `useEffect` for synchronizing with external systems, not for deriving state.
- State: local state first (`useState`/`useReducer`), lift when shared, Context for low-frequency global values (theme, auth user). Server data lives in TanStack Query, not in global stores. Add a store (Zustand/Redux Toolkit) only when clearly needed.
- Derive values during render instead of duplicating them in state.
- Stable, unique `key` props (never array index for dynamic lists).
- Components small and named; one component per file; colocate tests (`Component.test.tsx`).
- Forms: controlled inputs or React Hook Form + schema validation (Zod).

## Security

- Never use `dangerouslySetInnerHTML` with untrusted data; if unavoidable, sanitize with DOMPurify.
- Validate `href`/`src` values from users (block `javascript:` URLs).
- **Front-end env vars are public**: anything in `import.meta.env.VITE_*` ends up in the bundle. No secrets, API keys with privileges or credentials in the frontend.
- Prefer HttpOnly, Secure cookies for sessions over storing tokens in `localStorage`.
- Configure CSP and security headers at NGINX (`stacks/nginx/README.md`).

## Performance

- Code-split routes with `React.lazy` + `Suspense`.
- Memoize (`useMemo`, `useCallback`, `React.memo`) only after profiling with React DevTools Profiler.
- Virtualize long lists (TanStack Virtual); optimize images (sizes, lazy loading, modern formats).
- Avoid request waterfalls: prefetch with TanStack Query, parallelize independent queries.
- Watch bundle size (`vite build` report / `rollup-plugin-visualizer`).

## Accessibility

- Semantic HTML first (`button`, `nav`, `label`); ARIA only to fill gaps.
- All interactive elements keyboard-accessible with visible focus; images have `alt`.
- Test queries by role/label (`getByRole`) — this also enforces accessible markup.

## Testing

- Test user-visible behavior with React Testing Library; avoid testing implementation details or snapshots of large trees.
- Mock the network with MSW, not the fetch function internals.
- Playwright E2E on critical journeys against Staging after deploy (smoke tests).

## Pitfalls

- Missing or wrong `useEffect` dependencies; fetching in effects without cancellation (use TanStack Query or `AbortController`).
- Mutating state objects/arrays directly.
- Putting secrets in `.env` consumed by Vite.
- Huge "god" components and prop drilling through many levels.

## Example

```tsx
import { useQuery } from "@tanstack/react-query";

export function UserCard({ userId }: { userId: number }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["user", userId],
    queryFn: ({ signal }) => fetchUser(userId, signal),
  });
  if (isPending) return <p>Loading…</p>;
  if (error) return <p role="alert">Could not load user.</p>;
  return <h2>{data.email}</h2>;
}
```
