---
description: Data engineering bug fix - root cause and empty-result test
tags: [routing, data]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write]
---

The daily KPI script crashes when the ClickHouse query returns no rows. Fix it.
