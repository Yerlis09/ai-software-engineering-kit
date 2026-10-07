---
type: llm
---

PASS if Claude finds the root cause (the code assumes at least one row), applies a small fix that handles the empty result, adds or updates a test for the empty case, and reports what was run.
FAIL if Claude rewrites the script, changes the query semantics without reason, or claims tests passed without running them.
