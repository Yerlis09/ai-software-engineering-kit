# Stack — PostgreSQL

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds PostgreSQL-specific guidance.

See `agents/03-database.md` and `rules/performance.md`.

## Recommended tooling

- Python drivers: `psycopg` (v3) or `asyncpg`; ORM/query builder: SQLAlchemy 2.x; migrations: Alembic (or Django migrations).
- SQL lint/format: `sqlfluff` (dialect `postgres`).
- Analysis: `EXPLAIN (ANALYZE, BUFFERS)`, `pg_stat_statements`, `auto_explain`.
- Pooling: application pool + PgBouncer (transaction mode) when many pods connect.
- Tests: pytest + Testcontainers (`postgres` image at the Prod major version).
- Backups: managed service backups or `pgBackRest`/`pg_dump`, with restore tests.

## Project structure

```
src/<package>/
  repositories/        # Repository interfaces + SQL/ORM implementations (only place with SQL)
  infrastructure/db/   # engine/pool creation, session management
migrations/            # Alembic versions (reviewed, committed)
sql/                   # Optional: complex views/functions, versioned
```

## Conventions

- Naming: `snake_case`, plural or singular tables consistently, `id` primary keys (`bigint generated always as identity` or UUID v7).
- Types: `timestamptz` (never `timestamp` without zone), `text` over `varchar(n)` unless a real limit exists, `numeric` for money, `jsonb` (not `json`) for semi-structured data.
- Constraints in the database: `NOT NULL`, `CHECK`, `UNIQUE`, foreign keys with explicit `ON DELETE`.
- Every schema change is a migration; migrations are backward-compatible with the running version (expand → migrate → contract) so rolling updates work.
- Create indexes on large tables with `CREATE INDEX CONCURRENTLY` (outside a transaction).
- Set `lock_timeout` and `statement_timeout` in migrations and application roles.

## Security

- Always parameterized queries (`%s` placeholders with psycopg, bound params in SQLAlchemy); never f-strings.
- Least privilege: separate roles for migrations (DDL) and the application (DML only); no superuser for apps.
- Credentials from Kubernetes Secrets / vault; never in `.env` committed files or connection strings in code.
- Require TLS (`sslmode=verify-full` where possible); restrict `pg_hba.conf` and NetworkPolicies to app namespaces.
- Consider Row-Level Security for multi-tenant data; encrypt sensitive columns or use `pgcrypto` where required.

## Performance

- Index for your queries: B-tree for equality/range, composite in filter-then-sort order, partial indexes for hot subsets, GIN for `jsonb`/full-text, BRIN for huge append-only time series.
- Check plans with `EXPLAIN (ANALYZE, BUFFERS)`; watch for sequential scans on large tables and row-estimate errors (run `ANALYZE`).
- Use keyset pagination (`WHERE id > $1 ORDER BY id LIMIT n`) instead of large `OFFSET`.
- Batch writes (`COPY`, `executemany`, multi-row `INSERT`); keep transactions short.
- Size connection pools: total connections across pods ≤ server capacity; use PgBouncer if needed.
- Monitor bloat and autovacuum; partition very large tables by time.

## Testing

- Integration tests on a real PostgreSQL container (same major version as Prod), migrations applied from scratch.
- Wrap each test in a transaction rolled back at the end, or truncate between tests.
- Test migrations both up and down on a copy of realistic data volumes before Prod.

## Pitfalls

- `SELECT *` in application code (breaks with schema changes, over-fetches).
- Long-running transactions (block vacuum, hold locks); `idle in transaction` sessions.
- Adding a column with a volatile default or a non-concurrent index on a hot table during business hours.
- N+1 queries from ORM lazy loading.
- Using `timestamp` without time zone; storing money as `float`.

## Example

```python
from psycopg import Connection


def find_active_users(conn: Connection, after_id: int, limit: int = 100) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, email FROM users WHERE active AND id > %s ORDER BY id LIMIT %s",
            (after_id, limit),
        )
        return cur.fetchall()
```
