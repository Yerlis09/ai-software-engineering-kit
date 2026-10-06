# Stack — MongoDB

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds MongoDB-specific guidance.

See `agents/03-database.md`. Choose MongoDB for document-shaped data with flexible schemas; prefer PostgreSQL when data is strongly relational or needs multi-entity transactions everywhere.

## Recommended tooling

- Python: `pymongo` (sync) or its async API / `motor` (legacy async); ODM optional (Beanie, MongoEngine) — keep it in the repository layer.
- Validation: Pydantic models in the application + `$jsonSchema` validators on collections.
- Migrations: versioned scripts (e.g. `mongodb-migrations`, `pymongo-migrate`) for indexes and data reshaping.
- Analysis: `explain("executionStats")`, profiler, Atlas/Ops Manager metrics if available.
- Tests: pytest + Testcontainers (`mongo` image at the Prod version); `mongomock` only for trivial unit tests.

## Project structure

```
src/<package>/
  domain/                 # Entities (no pymongo imports)
  repositories/           # Collection access, mapping documents <-> entities
  infrastructure/mongo/   # client factory (one MongoClient per process), settings
migrations/mongo/         # 001_create_indexes.py, ...
```

## Conventions

- Model for access patterns: embed data read together and bounded in size; reference data that grows unbounded or is shared.
- Keep documents well under the 16 MB limit; never grow arrays without bound.
- Enforce structure with `$jsonSchema` validation (`validationLevel: "moderate"` during transitions).
- Use a `schema_version` field to evolve documents; migrate lazily or with scripts.
- Create indexes explicitly via migrations, not ad hoc in application startup across all replicas.
- Use `datetime` in UTC; `Decimal128` for money.
- Multi-document transactions (replica set required) only where invariants demand them; keep them short.

## Security

- Never pass raw user JSON into queries: validate types so `{"$gt": ""}`-style **operator injection** is impossible; reject keys starting with `$` or containing `.`.
- Avoid `$where`, `$function` and server-side JavaScript.
- Enable authentication and TLS; least-privilege users per application (`readWrite` on one database only).
- Credentials from Kubernetes Secrets / vault, not in connection strings committed to git.
- Restrict network exposure (NetworkPolicies, no public bind); enable auditing where required.

## Performance

- Index to support queries following the ESR rule (Equality, Sort, Range) for compound indexes.
- Verify with `explain`: avoid `COLLSCAN` on large collections; aim for `totalDocsExamined ≈ nReturned`.
- Use projections (return only needed fields) — the equivalent of avoiding `SELECT *`.
- Range-based pagination (`_id > last_id`) instead of large `skip()`.
- `bulk_write` / `insert_many(ordered=False)` for batches.
- TTL indexes for expiring data; set `maxTimeMS` on queries.
- Read/write concerns: `w: "majority"` for important writes; read preferences deliberately.

## Testing

- Integration tests on a real MongoDB container (replica set if transactions are used).
- Apply index migrations in tests so query plans match Prod.
- Clean collections between tests (drop database per test session).

## Pitfalls

- Creating a new `MongoClient` per request (it is a pooled, thread-safe client — create once).
- Unbounded arrays and "one giant document" designs.
- Missing indexes discovered only at Prod volume.
- Treating "schemaless" as "no schema": inconsistent documents break consumers.
- Operator injection from unvalidated request bodies.

## Example

```python
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection


def orders_collection(client: MongoClient) -> Collection:
    coll = client["shop"]["orders"]
    coll.create_index([("customer_id", ASCENDING), ("created_at", ASCENDING)])  # run in migrations
    return coll


def recent_orders(coll: Collection, customer_id: str, limit: int = 20) -> list[dict]:
    if not isinstance(customer_id, str):
        raise ValueError("customer_id must be a string")  # blocks operator injection
    cursor = coll.find({"customer_id": customer_id}, {"_id": 1, "total": 1, "created_at": 1})
    return list(cursor.sort("created_at", -1).limit(limit).max_time_ms(2000))
```
