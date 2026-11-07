---
name: youtube-factory-self-improvement
description: Use after recurring bugs, failed renders, rights errors, slow jobs, high costs, poor QA, or whenever improving the OpenMontage Factory workflow, agent instructions, Skills, MCPs or architecture.
---

# Evidence-based factory improvement

1. Capture a reproducible example and sanitized logs.
2. Classify the failure: requirements, research, rights, asset download, timeline, rendering, QA, API, configuration or model/tool selection.
3. Record current behavior and metric in `docs/agent-improvement/LESSONS.md`.
4. Propose a small change in `docs/agent-improvement/BACKLOG.md` with expected benefit, risk, cost and rollback.
5. Add or update a regression test before changing behavior where practical.
6. Re-run the same benchmark task from `docs/agent-improvement/EVALS.md`.
7. Compare failure rate, human correction time, render time, cost per finished minute, rights coverage and output quality.
8. Do not claim improvement unless measured. If data is too small, say inconclusive.
9. Never silently install MCP servers/plugins, broaden permissions, change secrets, alter global config or publish videos.
10. Request human review for dependency/license changes, external services, permission changes, migrations or destructive actions.
11. Update docs only after the improvement passes tests; retain a changelog and rollback path.
