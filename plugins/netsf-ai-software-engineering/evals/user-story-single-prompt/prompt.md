---
description: One user story on an existing Flask project - full workflow without further prompts
tags: [autonomy, workflow]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write]
---

Implement this user story:

As a network engineer,
I want to retrieve a cell by ID,
so that I can view its information.

Acceptance criteria:
- Return the cell information as JSON.
- Return 404 when the cell does not exist.
- Add automated tests.
