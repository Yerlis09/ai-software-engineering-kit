---
description: Existing FastAPI project - minimal change in the existing structure
tags: [routing, existing]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write]
---

Add an endpoint to get a single cell by id, returning 404 when it does not exist.
