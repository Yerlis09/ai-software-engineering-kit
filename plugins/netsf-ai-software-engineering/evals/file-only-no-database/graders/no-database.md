---
type: llm
---

PASS if the solution processes the file without introducing a database, ORM, tables or persistence, and without Docker, Kubernetes or CI files, and includes tests.
FAIL if a database (SQLite, PostgreSQL, ClickHouse...), an ORM, Docker, Kubernetes or a CI pipeline is added.
