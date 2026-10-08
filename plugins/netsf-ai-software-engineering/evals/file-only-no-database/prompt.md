---
description: File-processing workflow: no database is introduced
tags: [policy, database, no-overengineering]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write]
---

Build a small API that receives an Excel file, processes it and returns a generated output file. It does not need to store anything.
