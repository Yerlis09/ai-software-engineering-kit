# Stack — SQL Server

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds SQL Server-specific guidance.

See `agents/03-database.md`.

## Recommended tooling

- Python: `pyodbc` with the Microsoft ODBC Driver for SQL Server (18+), or `mssql-python`; SQLAlchemy 2.x with the `mssql+pyodbc` dialect; Alembic for migrations.
- Alternative schema management: SQL Server Data Tools (SSDT/`sqlpackage`) or Flyway.
- SQL lint/format: `sqlfluff` (dialect `tsql`).
- Analysis: actual execution plans, Query Store, `sys.dm_exec_query_stats`, `SET STATISTICS IO, TIME ON`.
- Tests: pytest + Testcontainers (`mcr.microsoft.com/mssql/server` image).

## Project structure

```
src/<package>/
  repositories/          # Only place containing SQL / ORM queries
  infrastructure/db/     # engine creation, connection string from settings, session scope
migrations/              # Alembic versions or SSDT project
```

## Conventions

- Schema-qualify objects (`dbo.Users`); consistent naming (PascalCase or snake_case — pick one).
- Types: `datetime2` / `datetimeoffset` (not `datetime`), `nvarchar` for Unicode text, `decimal(p,s)` for money, `bit` for booleans; avoid `nvarchar(max)` unless needed.
- Primary keys: `bigint IDENTITY` or sequential GUIDs (`NEWSEQUENTIALID()`); avoid random GUIDs as clustered keys.
- Explicit transactions with `SET XACT_ABORT ON` in stored procedures; `TRY...CATCH` with `THROW`.
- Migrations backward-compatible with the running app version (expand → migrate → contract).

## Security

- Always parameterized queries: `?` placeholders with pyodbc, bound parameters in SQLAlchemy. Never concatenate strings, including inside dynamic SQL — use `sp_executesql` with parameters and `QUOTENAME` for identifiers.
- Least privilege: app login with only required `GRANT`s (ideally `EXECUTE` on procs or DML on a schema); no `sa`, no `db_owner` for apps.
- Credentials from Kubernetes Secrets / vault; prefer integrated auth (Kerberos/Entra ID) where available.
- Encrypt connections: `Encrypt=yes;TrustServerCertificate=no` in connection strings.
- Consider Always Encrypted / Dynamic Data Masking for sensitive columns; audit access.

## Performance

- Indexes: clustered index on a narrow, increasing key; nonclustered indexes covering frequent queries (`INCLUDE` columns); filtered indexes for hot subsets; columnstore for analytics.
- Read actual execution plans: look for scans on large tables, key lookups, implicit conversions (e.g. `varchar` column vs `nvarchar` parameter), spills.
- Keep predicates SARGable (no functions on indexed columns in `WHERE`).
- Parameter sniffing: diagnose with Query Store; use `OPTION (RECOMPILE)` or plan forcing deliberately, not by default.
- Isolation: enable **READ_COMMITTED_SNAPSHOT (RCSI)** to reduce reader/writer blocking; never use `NOLOCK` as a performance fix (dirty/missing reads).
- Batch large writes (chunks of a few thousand rows) to limit lock escalation and log growth; use `fast_executemany=True` with pyodbc for bulk inserts.
- Pool connections (pyodbc pooling / SQLAlchemy pool); set command timeouts.

## Testing

- Integration tests on a SQL Server container at the Prod version/compatibility level.
- Test migrations against a restored, anonymized copy of Prod-sized data before Prod.
- Verify plans of critical queries in performance tests.

## Pitfalls

- `NOLOCK` hints everywhere.
- Implicit conversions killing index usage (match parameter types to column types).
- `SELECT *` and unbounded queries; cursors/row-by-row loops instead of set-based SQL.
- Random `uniqueidentifier` clustered keys (page splits, fragmentation).
- Long transactions holding locks during external calls.

## Example

```python
import pyodbc


def get_orders(conn: pyodbc.Connection, customer_id: int, top: int = 50) -> list[pyodbc.Row]:
    cur = conn.cursor()
    cur.execute(
        "SELECT TOP (?) OrderId, Total, CreatedAt FROM dbo.Orders "
        "WHERE CustomerId = ? ORDER BY CreatedAt DESC",
        top,
        customer_id,
    )
    return cur.fetchall()
```
