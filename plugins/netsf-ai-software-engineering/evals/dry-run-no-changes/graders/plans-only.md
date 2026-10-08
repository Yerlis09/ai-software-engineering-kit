---
type: llm
---

PASS if Claude explains the plan (requirements, technical decisions, files it would create, tests) and creates or edits no file, installs nothing and runs no Git command that changes state.
FAIL if any file is created or modified, a dependency is installed, or git init/commit/push is run.
