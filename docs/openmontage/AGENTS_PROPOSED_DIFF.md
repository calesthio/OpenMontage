# Proposed additive rules block for project AGENTS.md (M1)

**Status:** PROPOSED ONLY. Do not apply to real `AGENTS.md`. This is a diff for owner review.

**Constraint:** max ~25 lines. Additive; no silent changes to config/MCP/permissions; load only relevant skills; report only skills/tools actually used.

```diff
diff --git a/AGENTS.md b/AGENTS.md
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -126,6 +126,18 @@
 ### Self-improvement
 - Record repeatable failures in `docs/agent-improvement/LESSONS.md`.
 - Propose changes in `docs/agent-improvement/BACKLOG.md`; do not silently change global config or install new MCP/plugins.
+- **Subagent roles are inline, not independent:** every subagent proposes; the orchestrator verifies; the owner approves. Never treat subagent output as verified fact.
+- **Load only relevant skills** for the task; do not load all skills on every request.
+- **Report only skills and tools actually read/used**; never claim a skill/MCP was used when it was merely configured or present.
+- **No silent changes:** do not modify global `~/.config/kilo`, `kilo.json`/`kilo.jsonc`, MCP config, permissions, or skills automatically. Propose changes via `docs/agent-improvement/BACKLOG.md` and require human review.
 ### Completion response
 Report: files changed, commands run, tests and results, skipped checks, rights/security risks, and the next smallest useful step. Distinguish implemented code from plans and unverified assumptions.
```

**Rationale:**
- `AGENTS.md` already covers LESSONS/BACKLOG/EVALS self-improvement, relevant-skill loading, actual-skills-used reporting, and no-silent-global-changes (§Self-improvement, §Required startup routine, §Completion response).
- The additive block makes explicit: (1) subagent roles are inline not independent; (2) load only relevant skills; (3) report only actually-used skills/tools; (4) no silent changes to global config/MCP/permissions — propose via BACKLOG.md with human review.
- These are already implicit in AGENTS.md and MERGE_AUDIT.md; the diff is for owner review, not auto-application.
