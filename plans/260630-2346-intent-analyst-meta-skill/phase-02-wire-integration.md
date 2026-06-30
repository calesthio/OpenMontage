---
phase: 2
title: Wire integration
status: completed
effort: S
---

# Phase 2: Wire integration

## Overview

Wire `intent-analyst` into the existing flow so it actually runs before pipeline selection and hands off cleanly. Edits are small, surgical inserts into 5 existing files — no logic rewrites.

## Requirements

- Functional: AGENT_GUIDE Rule Zero step 1 invokes intent-analyst before "identify the pipeline"; reading order updated.
- Functional: creative-intake consumes `intent_map.open_ambiguities` and does NOT re-decompose intent.
- Functional: onboarding and video-reference-analyst hand off to intent-analyst when the user moves to an actionable request / after VideoAnalysisBrief.
- Functional: INDEX registers the new skill.
- Non-functional: edits minimal and consistent with surrounding prose; no behavior change to unrelated sections.

## Architecture

Flow after wiring: `onboarding`/`video-reference-analyst` (entry) → **`intent-analyst` (route, Rule Zero step 1)** → pipeline selection → **preflight (Rule Zero step 3, authoritative capability check)** → `creative-intake` (fill brief from open_ambiguities) → research. intent-analyst is the single universal pre-pipeline-selection step for actionable requests. **Ordering rule [A2]:** intent-analyst runs BEFORE preflight; its `capability_needs` is provisional and gets verified at preflight — the wiring must not let intent-analyst imply a pipeline is runnable before preflight confirms it.

## Related Code Files

- Modify: `AGENT_GUIDE.md` — Rule Zero step 1 (insert intent-analyst before "Identify the pipeline"); add intent-analyst to the reading-order / meta-skill references.
- Modify: `skills/meta/creative-intake.md` — add a short "Input: intent_map" note; instruct it to resolve `open_ambiguities` and not re-run decomposition.
- Modify: `skills/meta/onboarding.md` — add handoff line: once user gives an actionable request, run intent-analyst.
- Modify: `skills/meta/video-reference-analyst.md` — add handoff line: feed VideoAnalysisBrief into intent-analyst before pipeline selection.
- Modify: `skills/INDEX.md` — register `intent-analyst` under meta skills.

## Implementation Steps

1. Read each of the 5 files at the exact insert site before editing. **Before renumbering Rule Zero, grep the repo for references to Rule Zero step numbers** (e.g. "step 1", "step 3", "preflight (step") so the insert doesn't break cross-references elsewhere in docs/skills [scenario #10].
2. `AGENT_GUIDE.md`: in Rule Zero, prepend a step "0/1a. Read `skills/meta/intent-analyst.md` and produce an intent_map" ahead of "Identify the pipeline"; ensure the numbering/prose stays coherent and that preflight (step 3) remains the authoritative capability check AFTER routing. Add the skill to any meta-skill list / reading order.
3. `creative-intake.md`: add an "Input" note that an `intent_map` may already exist; consume `open_ambiguities`; do not duplicate decomposition.
4. `onboarding.md`: add one handoff sentence at the transition from orientation to an actionable request.
5. `video-reference-analyst.md`: add one handoff sentence after VideoAnalysisBrief → intent-analyst.
6. `INDEX.md`: add the registry line matching existing format.

## Success Criteria

- [ ] Repo grepped for Rule Zero step-number references before renumber; none left dangling.
- [ ] AGENT_GUIDE Rule Zero runs intent-analyst before pipeline identification; prose coherent.
- [ ] AGENT_GUIDE reading order / meta-skill references include intent-analyst.
- [ ] creative-intake references intent_map input + open_ambiguities; no re-decomposition.
- [ ] onboarding and video-reference-analyst each hand off to intent-analyst.
- [ ] INDEX lists intent-analyst.
- [ ] No unrelated sections altered.

## Risk Assessment

- **Breaking Rule Zero numbering/flow** → mitigated by reading insert sites first and keeping the insert additive (new step, renumber only if needed).
- **Double-interrogation regression** → creative-intake edit explicitly forbids re-decomposition; confirmed in Phase 3 scenario 4.
- **Missed reference** → Phase 3 grep sweep confirms all 5 files reference the skill.
