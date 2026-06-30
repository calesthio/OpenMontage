---
phase: 3
title: Validate scenarios
status: completed
effort: S
---

# Phase 3: Validate scenarios

## Overview

No code = no automated tests. Validation is a dry-run walkthrough of the skill against representative requests plus a consistency sweep over the edited files. Confirms the protocol behaves as designed and integration has no gaps or duplicated interrogation.

## Requirements

- Functional: walk 4 scenarios through `intent-analyst.md` by reading the skill and tracing the protocol; confirm expected `intent_map` shape and branch.
- Functional: grep sweep confirms all 5 wired files reference intent-analyst and flow is coherent.
- Non-functional: zero unresolved contradictions across plan + edited skills.

## Architecture

Validation is manual/dry-run since the artifacts are instructions consumed by the agent at runtime. The "test oracle" is the acceptance criteria in `plan.md`.

## Test Scenarios (dry-run by tracing the protocol)

1. **Clear single-pipeline (fast-path)** — "Make a 60s animated explainer about black holes." → confidence=high → fast-path; routed_pipelines=[animated-explainer]; capability_needs={tts, image_gen|video_gen, music} marked provisional; NO extra question.
2. **Implicit-heavy** — "Make something for our TikTok about our new app." → implicit_intents capture vertical 9:16, short duration, hook; routed_pipelines plausibly [animated-explainer or animation]; open_ambiguities lists topic depth / narration; confidence=medium → present route + brief confirm folded into the creative-intake transition (single turn, not two).
3. **Compound (v1 detect + suggest, NOT orchestrate)** — "Make a meditation long-form video and cut 3 shorts from it." → intent-analyst DETECTS 2 deliverables, SUGGESTS sequential runs (animated-explainer/animation, then clip-factory on the rendered long-form, shared `projects/<name>/`); **always confirms**; does NOT auto-build a chain; states automated chaining is v2.
4. **Overlap guard** — after intent-analyst marks open_ambiguities, creative-intake (per Phase 2 edit) resolves them WITHOUT re-decomposing intent or repeating questions.
5. **Ordering vs preflight [A2]** — request routes to a pipeline whose capability is unconfigured → intent-analyst lists it in capability_needs as provisional WITHOUT claiming the pipeline will run; preflight (Rule Zero step 4, after the intent-analysis + identify-pipeline steps) is where unavailability surfaces. Confirm the skill prose does not promise runnability pre-preflight.
6. **Intra-pipeline refinement [scenario #1]** — user mid-pipeline says "change the music" → intent-analyst does NOT fire/re-route; active stage handles it. Confirm "When to Use" excludes this.
7. **No-match [scenario #2]** — "make me an audio-only podcast" → `routed_pipelines: []`; intent-analyst states unsupported/closest, does not force-fit.
8. **Vietnamese input [scenario #3]** — "Làm video thiền 10 phút có nhạc nền" → parses VI, maps to EN pipeline name, confidence set correctly.
9. **High-confidence definition [scenario #4]** — verify a request with one clear pipeline + clear platform/duration/treatment = high (fast-path), and a one-clear-pipeline-but-vague-duration request = medium (confirm), per the defined rule.

## Related Code Files

- Read/verify (no modification): `skills/meta/intent-analyst.md`, `AGENT_GUIDE.md`, `skills/meta/creative-intake.md`, `skills/meta/onboarding.md`, `skills/meta/video-reference-analyst.md`, `skills/INDEX.md`

## Implementation Steps

1. Read `intent-analyst.md` and trace each of the 4 scenarios; record the produced intent_map per scenario.
2. Confirm fast-path triggers only for scenario 1; compound chain only for scenario 3.
3. Grep all 5 wired files for `intent-analyst` / `intent_map`; confirm references exist and read coherently.
4. Whole-plan consistency sweep: re-read plan.md + all phase files + edited skills for stale terms, contradictions, duplicated interrogation. Reconcile any found.
5. Record results inline in this phase (checklist) and report to user.

## Success Criteria

- [ ] All 9 scenarios produce the expected intent_map shape and branch.
- [ ] Fast-path fires only for the clear high-confidence request; compound is detect+suggest (no auto-chain) and always confirms.
- [ ] Scenario 5: skill never promises runnability before preflight; capability_needs provisional.
- [ ] Scenario 6: intra-pipeline refinement does not re-trigger intent-analyst.
- [ ] Scenario 7: no-match yields `routed_pipelines: []` + plain statement, no force-fit.
- [ ] Scenario 8: Vietnamese request parsed + mapped correctly.
- [ ] Scenario 9: high vs medium confidence assigned per the defined rule.
- [ ] Grep confirms all 5 wired files reference the new skill; flow coherent; preflight remains authoritative after routing; no dangling Rule Zero step-number refs.
- [ ] No duplicated interrogation between intent-analyst and creative-intake (scenario 4 passes); medium/low confirm is single-turn.
- [ ] intent-analyst.md ≤ ~120 lines.
- [ ] Zero unresolved contradictions in consistency sweep.

## Risk Assessment

- **Dry-run misses runtime behavior** → acceptable: these are agent instructions, exercised the same way at runtime; scenarios cover fast-path, implicit, compound, and overlap — the four risk areas.
- **Latent overlap not caught by trace** → scenario 4 specifically targets it; grep sweep backs it up.
