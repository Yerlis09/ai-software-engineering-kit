# Troubleshooting — fastapi-demo

Document recurring problems here: symptom, cause, fix. Keep entries short.

| Symptom | Likely cause | Fix |
|---|---|---|
| `ai-project doctor` reports FAIL | A required file or check is missing | Follow the hint printed under the failing check |
| `*.kit-new` files after `ai-project update` | A kit file was customised locally | Merge by hand, delete the `.kit-new` file, move custom content to `.ai/custom/` |
