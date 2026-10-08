---
type: llm
---

PASS if Claude asks which database to use (it may recommend ClickHouse as the organisation default) before implementing persistence, and does not ask the user to choose a programming language or framework.
FAIL if Claude silently picks SQLite, PostgreSQL or any other database, or asks the user to choose between frameworks such as FastAPI and Flask.
