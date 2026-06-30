# 2026-07-01 — intent-analyst meta skill (VideoAgent intent-analysis port)

**Type:** feature / routing · **Branch:** `feat/intent-analyst-meta-skill` · **Commit:** cd991cb

## What

Ported the **Intent Analysis** pattern from HKUDS/VideoAgent into OpenMontage as a new instruction-only meta skill, via a chained `/brainstorm → /ck-plan → /ck-predict --chain probe → /ck-predict --chain reason → /ck-scenario → /cook` workflow. Three phases, all complete:

1. **Author** — `skills/meta/intent-analyst.md` (124 lines): emits an informal `intent_map` (explicit/implicit intents, routed pipeline, provisional capability needs, open_ambiguities, confidence). Runs at Rule Zero step 1, before pipeline selection.
2. **Wire** — `AGENT_GUIDE.md` Rule Zero (new step 1 "Analyze intent", preflight renumbered to step 4 and kept authoritative); handoffs in `creative-intake`, `onboarding`, `video-reference-analyst`; registered in `skills/INDEX.md`.
3. **Validate** — 9 dry-run scenarios traced through the skill + grep/consistency sweep.

## Key decisions

- **Router, not interrogator.** intent-analyst never asks the user — unknowns go to `open_ambiguities`, which `creative-intake` consumes. This role-boundary table (vs onboarding / video-reference-analyst / creative-intake) was the main defence against becoming a fourth overlapping "understand-the-user" skill.
- **Scope cut from `/ck-predict --chain probe`.** Original design auto-orchestrated compound pipeline chains. Probe surfaced an undefined cross-pipeline data-flow (High risk) → **v1 reduced to single-pipeline routing**; compound is detect-and-suggest-sequential only. Automated chaining deferred to v2.
- **v2 + metric resolved via `/ck-predict --chain reason`.** A1 (compound data-flow) → shared `projects/<name>/` + informal `chain.json` ledger. A3 (success metric) → two-tier: qualitative gate now + count user route-overrides as the cheap ongoing signal, eval-set only if mis-routing proves real (YAGNI).
- **Six gaps patched from `/ck-scenario`.** Trigger scope excludes intra-pipeline refinement; no-match path (`routed_pipelines: []`); Vietnamese input + worked VI example; `confidence: high` given a hard definition; examples marked illustrative (anti-drift); grep step-numbers before renumbering Rule Zero.

## Verification

- 9/9 scenarios pass by tracing the skill (fast-path, medium-confirm, compound-suggest, overlap-guard, provisional-capability, refinement-excluded, no-match, Vietnamese, confidence-definition).
- Grep sweep: all 5 wired files reference intent-analyst; shipped files use "step 1" (intent) / "step 4" (preflight) correctly; zero dangling Rule Zero step-number refs.
- Consistency sweep across plan + skills: zero contradictions. No code/contract touched — markdown only.

## Friction / notes

- **1M-context subagent credits still unavailable on this machine** — same terminal "Usage credits required for 1M context" error as the prior session. Ran `/cook`'s code-review, validation, and this journal inline rather than via `code-reviewer`/`tester`/`journal-writer` subagents.
- Skill is 124 lines vs the ≤~120 target — within the tilde tolerance; trimmed twice but kept the two worked examples for clarity.

## Follow-ups

- v2 compound chaining: implement the `chain.json` ledger + clip-factory source-reuse optimization when a real multi-deliverable request appears.
- Wire the route-override counter into the journal/checkpoint note convention so the A3 Tier-2 signal actually accumulates.
- Branch `feat/intent-analyst-meta-skill` is unmerged — open a PR or merge to main when ready.
