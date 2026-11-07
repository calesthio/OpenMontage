---
name: kilo-self-improvement
description: Use when the user asks to improve Kilo Code, agent reliability, tool/skill usage, reduce context waste, create or update agent rules, analyze repeated failures, design evaluations, maintain an improvement backlog, or audit the coding-agent workflow.
license: MIT
---

# Kilo Self-Improvement

## Objective
Improve the coding-agent workflow through evidence-based changes to project instructions, Skills, MCP configuration, custom agents, test coverage, and documentation. Do not imply that the model weights are being trained.

## Workflow

1. **Inspect current state**: read `AGENTS.md`, project instructions, `kilo.jsonc`/`kilo.json` if present, installed Skills and MCP names, current Git status, tests, and any existing `docs/agent-improvement/` notes. Do not print secrets.
2. **Find evidence**: use concrete failed tasks, repeated user corrections, failed tests, tool failures, and known wasted context. Distinguish verified observations from hypotheses.
3. **Choose one bottleneck**: prioritize correctness and reliability first, then security, maintainability, latency, and token efficiency.
4. **Propose a minimal change**: name the file/config that would change, expected benefit, risk, rollback method, and a test that validates the claim. Avoid adding tools that duplicate existing capabilities.
5. **Baseline before changing**: record a few representative tasks and their pass/fail outcomes. When available, track test failures, tool calls, token/context usage, latency, and manual corrections. Never invent measurements.
6. **Implement in isolation**: use a branch or patch. Do not silently change global configuration, permission policies, credentials, or tool approvals.
7. **Evaluate**: rerun the same representative tasks from `docs/agent-improvement/EVALS.md` and automated tests. Check for regressions and security changes. Never modify global config, permissions, or skills automatically.
8. **Keep/revert**: retain the change only if objective results improve without unacceptable trade-offs. Otherwise revert and record what was learned.
9. **Document**: update `docs/agent-improvement/LESSONS.md` and `BACKLOG.md`; include date, issue, evidence, change, result, and rollback/commit reference.
10. **Report honestly**: separate facts, hypotheses, and untested proposals. List actual tools/Skills used; never claim an MCP server was used when it was merely configured.

## Quality bar

A rule should be generalizable and precise. A Skill should solve a recurring task, explain when it applies, include examples and safe failure behavior, and be tested against at least two representative cases. A new MCP server should justify its context cost and overlapping functionality. Prefer fewer, reliable tools over a large uncurated collection.

## Suggested improvement records

### `LESSONS.md`
- Date / task:
- Observed failure and evidence:
- Confirmed cause / uncertainty:
- Fix or proposed rule:
- Regression test:
- Result:

### `BACKLOG.md`
- Item / priority:
- Problem evidence:
- Proposed change:
- Expected benefit:
- Risks and cost:
- Validation task:
- Status / rollback:
