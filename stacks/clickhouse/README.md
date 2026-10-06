# Stack — ClickHouse

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds ClickHouse-specific guidance.

ClickHouse is a columnar **OLAP** database: excellent for large analytical scans and aggregations, poor at transactional row-by-row updates. Keep OLTP data in PostgreSQL/SQL Server and feed ClickHouse via pipelines (`stacks/data-pipelines/README.md`).

## Recommended tooling

- Python client: `clickhouse-connect` (HTTP) or `clickhouse-driver` (native); SQLAlchemy dialect only for simple use.
- Migrations: versioned SQL files applied by a migration tool (e.g. `golang-migrate`, `clickhouse-migrations`) or a small, idempotent runner.
- SQL lint/format: `sqlfluff` (dialect `clickhouse`).
- Analysis: `EXPLAIN indexes = 1`, `system.query_log`, `system.parts`, `system.mutations`.
- Tests: pytest + Testcontainers (`clickhouse/clickhouse-server` at the Prod version).

## Project structure

```
src/<package>/
  repositories/analytics/   # Query functions (only place with ClickHouse SQL)
  infrastructure/clickhouse/ # client factory, settings, batching writer
migrations/clickhouse/      # 001_create_events.sql, 002_mv_daily.sql, ...
```

## Conventions

- Default to the **MergeTree family**: `MergeTree`, `ReplacingMergeTree` (dedup by key, eventually), `AggregatingMergeTree`/`SummingMergeTree` (pre-aggregation), `Replicated*` / `ON CLUSTER` in clustered deployments.
- **`ORDER BY` (sorting key) is the primary index**: put low-cardinality, frequently filtered columns first, then time (e.g. `ORDER BY (tenant_id, event_type, event_time)`).
- **`PARTITION BY`** coarse (usually by month `toYYYYMM(ts)` or day for very large volumes); partitions are for data lifecycle (TTL, drop), not for query speed. Avoid thousands of partitions.
- Use `LowCardinality(String)` for columns with < ~10k distinct values; `DateTime64` with explicit timezone; avoid `Nullable` unless needed.
- Use `TTL` for retention instead of DELETE jobs.
- Materialized views for incremental pre-aggregation into a target table (`CREATE MATERIALIZED VIEW ... TO target`); they trigger on insert only.

## Security

- Parameterized queries (`{name:Type}` server-side parameters or client binding); never format user input into SQL.
- Separate users/roles for ingestion (INSERT only on specific tables), reporting (SELECT), and DDL; set quotas and `readonly` profiles for BI users.
- Credentials from Kubernetes Secrets; TLS on HTTP/native ports; restrict network access with NetworkPolicies.
- Set `max_execution_time`, `max_memory_usage`, `max_result_rows` per profile to contain runaway queries.

## Performance

- **Batch inserts**: thousands to hundreds of thousands of rows per insert, roughly ≤ 1 insert/second per table. Frequent small inserts create too many parts ("Too many parts" errors). If producers are chatty, use `async_insert=1` or a buffering writer.
- **Avoid mutations** (`ALTER TABLE ... UPDATE/DELETE`): they rewrite whole parts. Model changes as new rows (ReplacingMergeTree, versioned rows) or use lightweight deletes sparingly.
- **No `SELECT *`**: columnar storage reads only selected columns; select what you need.
- Filter on the sorting-key prefix; use `PREWHERE` for selective filters (often automatic).
- Approximate functions (`uniq`, `quantileTDigest`) when exact results are not required.
- Avoid large `JOIN`s on the right side; use dictionaries for dimension lookups.
- `FINAL` is expensive; use it only when needed, or aggregate with `argMax`.

## Testing

- Integration tests on a ClickHouse container: apply migrations, insert fixtures in one batch, assert query results.
- For ReplacingMergeTree logic, test with `FINAL`/`OPTIMIZE ... FINAL` in tests (never in Prod code paths).
- Benchmark critical queries on realistic volumes; check `read_rows` in `system.query_log`.

## Pitfalls

- Using ClickHouse as an OLTP store (point updates, per-row inserts).
- Wrong `ORDER BY` key (high-cardinality UUID first) → full scans.
- Over-partitioning (by hour or by id).
- Expecting uniqueness or immediate deduplication from ReplacingMergeTree.
- Forgetting that materialized views do not process data inserted before their creation (backfill explicitly).

## Example

```sql
CREATE TABLE analytics.events
(
    tenant_id   UInt32,
    event_type  LowCardinality(String),
    event_time  DateTime64(3, 'UTC'),
    user_id     UInt64,
    payload     String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (tenant_id, event_type, event_time)
TTL toDateTime(event_time) + INTERVAL 13 MONTH;
```
