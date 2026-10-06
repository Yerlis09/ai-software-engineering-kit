# Stack — Angular

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Angular-specific guidance.

Team frontend default is React (`stacks/react/README.md`); use this guide for Angular projects. See `stacks/typescript/README.md` and `agents/01-frontend.md`.

## Recommended tooling

- Angular CLI (`ng`) with the application builder (esbuild).
- Lint: `angular-eslint` (+ template accessibility rules); format: Prettier.
- Type check: strict TypeScript + `strictTemplates` (compiler runs on `ng build`).
- Tests: Vitest or Jest (or Karma/Jasmine if already in place), Angular `TestBed`, Angular Testing Library; E2E: Playwright.
- Package manager: `npm`, lock file committed; `ng update` for framework upgrades.

## Project structure

```
src/app/
  core/                 # Singletons: interceptors, guards, auth, config, error handler
  shared/ui/            # Reusable presentational standalone components, pipes, directives
  features/<name>/
    pages/              # Routed container components (Controller role)
    components/         # Presentational components (inputs/outputs only)
    data-access/        # Services calling HttpClient, state (signals/store)
    <name>.routes.ts    # Lazy-loaded routes
  app.config.ts  app.routes.ts  app.component.ts
```

## Conventions

- Standalone components only (no new NgModules); lazy-load features with `loadComponent` / `loadChildren`.
- `ChangeDetectionStrategy.OnPush` on every component.
- Signals for local and shared state (`signal`, `computed`, `effect` sparingly); `input()`/`output()` APIs; use `toSignal` to bridge observables.
- Use built-in control flow (`@if`, `@for` with `track`, `@switch`).
- `inject()` for DI; services `providedIn: 'root'` unless scoped.
- Typed reactive forms; no business logic in templates.
- Strict mode on: `"strict": true` in `tsconfig.json` and `strictTemplates`, `strictInjectionParameters` in `angularCompilerOptions`.

## RxJS hygiene

- Every manual `subscribe` must be torn down: `takeUntilDestroyed()` (inside injection context or with `DestroyRef`), or prefer the `async` pipe / `toSignal`.
- Pick the right flattening operator: `switchMap` (search/navigation), `concatMap` (ordered writes), `exhaustMap` (submit buttons).
- No nested subscribes; handle errors with `catchError` close to the source.
- Share HTTP results deliberately (`shareReplay({ bufferSize: 1, refCount: true })`).

## Security

- Auth via a functional `HttpInterceptorFn`: attach tokens only to your own API origins; handle 401 centrally.
- Angular escapes interpolation by default; do not bypass it. `DomSanitizer.bypassSecurityTrust*` only for trusted, reviewed content, never user input.
- Avoid `[innerHTML]` with untrusted HTML; never build templates dynamically from user data.
- `environment.ts` values are public in the bundle: no secrets.
- Use route guards for UX only; the backend must enforce authorization.
- CSP and security headers set at NGINX (`stacks/nginx/README.md`).

## Performance

- OnPush + signals; `track` in `@for`; avoid function calls in templates (use `computed` or pure pipes).
- Lazy routes and `@defer` blocks for heavy components.
- `NgOptimizedImage` for images; check bundle budgets in `angular.json`.

## Testing

- Component tests with `TestBed` / Angular Testing Library, querying by role/label.
- Mock HTTP with `provideHttpClientTesting()` and `HttpTestingController`.
- Playwright E2E on critical flows; smoke tests on Staging.

## Pitfalls

- Memory leaks from un-torn-down subscriptions.
- Default change detection everywhere causing slow UIs.
- Fat "shared" modules/barrels imported by everything.
- `bypassSecurityTrustHtml` used to "fix" a sanitization warning.

## Example

```ts
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { switchMap } from 'rxjs';

@Component({
  selector: 'app-user-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (user(); as u) { <h2>{{ u.email }}</h2> } @else { <p>Loading…</p> }`,
})
export class UserCardComponent {
  private readonly users = inject(UserService);
  readonly userId = input.required<number>();
  readonly user = toSignal(toObservable(this.userId).pipe(switchMap((id) => this.users.get(id))));
}
```
