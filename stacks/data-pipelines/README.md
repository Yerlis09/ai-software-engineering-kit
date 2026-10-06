# Stack — Data Pipelines

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Data Pipelines-specific guidance.

Python automation and data engineering jobs (ETL/ELT, syncs, exports, scheduled scripts). See `stacks/python/README.md`, `stacks/postgresql/README.md`, `stacks/clickhouse/README.md`, `agents/13-observability.md`.

## Recommended tooling

- Language/tooling: Python with `ruff`, `mypy`/`pyright`, `pytest`, `uv`.
- Data processing: Polars or pandas (Polars/DuckDB for larger-than-comfortable data), PyArrow/Parquet for intermediate files.
- Schema validation: Pydantic (records), Pandera (dataframes), or JSON Schema; data quality: Great Expectations / Soda / custom checks.
- Orchestration: Airflow or Prefect for multi-step DAGs; **Kubernetes CronJob** for simple scheduled jobs; plain cron only on legacy hosts.
- Retries: `tenacity` (exponential backoff with jitter).
- Observability: structured logs, Prometheus metrics (Pushgateway for batch jobs) or orchestrator metrics, alerts on failure and staleness.

## Project structure

```
src/pipelines/
  jobs/<job_name>.py     # Entry point (Controller): parse args, wire dependencies, run
  application/           # Pipeline steps: extract -> validate -> transform -> load
  domain/                # Record models, schemas, transformation rules (pure functions)
  repositories/          # Sources/sinks: DB, APIs, object storage
  infrastructure/        # Clients, settings, state/checkpoint store, metrics
dags/ | flows/           # Airflow DAGs / Prefect flows (thin: call application code)
deploy/cronjobs/         # Kubernetes CronJob manifests (base + staging + prod overlays)
```

Keep orchestration code thin: DAGs schedule and pass parameters; logic lives in testable application modules.

## Conventions

- **Idempotent jobs**: re-running a job for the same window produces the same result (upsert/merge on natural keys, or delete-and-replace a partition in one transaction). Never blindly append.
- **Incremental loads**: process by watermark (`updated_at`, monotonic id, CDC offset) or by logical date partition; support explicit backfill of a date range.
- **Checkpointing**: persist the last successfully committed watermark/offset *after* the load commits; resume from it on failure.
- **Schema validation** at ingestion: reject or quarantine invalid records (dead-letter table/file) with a reason; fail the run if the error rate exceeds a threshold.
- **Data quality checks** after load: row counts vs source, null/uniqueness constraints, referential checks, freshness.
- **Retries with exponential backoff + jitter** for transient errors only (timeouts, 5xx, 429); no retry on validation errors.
- **Batch sizing**: process in chunks (e.g. 1k–100k rows) to bound memory and transaction size; stream instead of loading everything.
- Parameterize by run date / window (`--start`, `--end`); never depend on "now" implicitly.
- One job = one responsibility; explicit dependencies between jobs in the orchestrator.

## Security

- Credentials for sources/sinks come from Kubernetes Secrets / vault / orchestrator connections — never in `.env` files, DAG code or notebooks.
- Least-privilege service accounts per pipeline (read on source, write on target schema only).
- Mask or pseudonymize personal data early; never log record payloads containing PII.
- Validate file inputs (size, type, path) and use parameterized SQL for loads.

## Performance

- Push filtering and aggregation down to the source database; select only needed columns.
- Bulk load paths: `COPY` (PostgreSQL), large batched inserts (ClickHouse), `fast_executemany` (SQL Server).
- Parallelize independent partitions with bounded concurrency; respect source rate limits.
- Columnar formats (Parquet) and partitioned storage for intermediate data.
- Kubernetes CronJob: set `concurrencyPolicy: Forbid`, `activeDeadlineSeconds`, `backoffLimit`, resource requests/limits.

## Testing

- Unit-test transformations as pure functions with small fixture datasets (including edge cases: nulls, duplicates, late data, timezones).
- Integration-test a full run against containerized source/target DBs; run it **twice** to prove idempotency.
- Contract tests on source schemas to detect upstream changes early.

## Pitfalls

- Non-idempotent appends causing duplicates after a retry.
- Updating the checkpoint before the load commits (silent data loss).
- Using wall-clock "now" instead of the logical run window (non-reproducible runs, gaps at boundaries).
- Swallowing errors so the orchestrator shows "success" with partial data.
- No alert on stale data (job silently not running).
- Loading entire tables into memory.

## Example

```python
from datetime import datetime

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential


@retry(retry=retry_if_exception_type(TransientError), wait=wait_random_exponential(max=60), stop=stop_after_attempt(5))
def fetch_batch(source: Source, since: datetime, limit: int) -> list[Record]:
    return source.fetch(updated_after=since, limit=limit)


def run(source: Source, target: Target, checkpoints: CheckpointStore, job: str, batch_size: int = 5000) -> None:
    watermark = checkpoints.get(job)
    while batch := fetch_batch(source, watermark, batch_size):
        valid, rejected = validate(batch)            # schema validation
        with target.transaction():
            target.upsert(valid)                     # idempotent merge on natural key
            target.quarantine(rejected)
        watermark = max(r.updated_at for r in batch)  # real code: keyset on (updated_at, id) to not skip ties
        checkpoints.set(job, watermark)              # only after commit
        metrics.rows_loaded.labels(job=job).inc(len(valid))
```
