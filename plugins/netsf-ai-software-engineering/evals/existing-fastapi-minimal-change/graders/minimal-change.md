---
type: llm
---

PASS if the endpoint is added inside the existing app/api/cells.py router (or the existing structure), existing code and tests are preserved, tests for the found and 404 cases are added, and the report lists the files changed.
FAIL if the project is restructured, unrelated files are refactored, existing tests are deleted or weakened, or tests are reported as passing without being run.
