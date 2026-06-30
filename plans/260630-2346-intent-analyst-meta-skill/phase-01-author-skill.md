---
phase: 1
title: Author skill
status: completed
effort: M
---

# Phase 1: Author skill

## Overview

Write `skills/meta/intent-analyst.md` — the instruction-only meta skill that decomposes an actionable request into explicit + implicit sub-intents and emits an informal `intent_map`. This is the core deliverable; phases 2-3 wire and validate it.

## Requirements

- Functional: protocol that takes any actionable production request → `intent_map` with fields `explicit_intents`, `implicit_intents`, `routed_pipelines`, `capability_needs`, `open_ambiguities`, `confidence` (enum: high|medium|low).
- Functional: confidence-driven behavior — high → fast-path (state route, proceed); medium/low → present route + brief confirm folded into the same turn as the creative-intake transition (NOT a separate Q&A round). [A4, A5]
- Functional (v1): **single-pipeline routing**. Compound requests (≥2 deliverables) are *detected and suggested as sequential manual runs* (each its own Rule Zero, shared `projects/<name>/`), **always confirmed regardless of confidence**; intent-analyst does NOT auto-orchestrate a chain. [A1]
- Functional: `capability_needs` provisional only — never promise a capability; preflight (Rule Zero step 4, after intent-analysis at step 1) verifies. [A2]
- Non-functional: instruction-only markdown; match tone/structure of existing `skills/meta/*.md`; no JSON schema, no reflection loop, no concept seeds, no user interrogation. **Concise — target ≤ ~120 lines** (read on every request). [A-len]

## Architecture

`intent_map` is informal context (like `creative-intake`'s `intake_brief`), not a schema-validated artifact. Routing reads the AGENT_GUIDE "Best For" pipeline table at runtime — no hardcoded pipeline list. Hard rule: intent-analyst marks `open_ambiguities` but does NOT ask the user; creative-intake resolves them later.

Section outline for the skill file:
1. **When to Use** — every NEW production-initiating request, at Rule Zero step 1, before pipeline selection. **Explicitly excludes:** (a) refinement requests during an in-flight pipeline ("change the music", "make it longer") → handled by the active stage, not re-routed [scenario #1]; (b) pure exploratory "what can you do" → onboarding, not intent-analyst [scenario #12]; (c) pure transcript fetch / non-production utility requests.
2. **Role boundary** — table delineating intent-analyst vs onboarding / video-reference-analyst / creative-intake (from brainstorm §5.1). State the "does not ask user" rule.
3. **intent_map structure** — the 6 fields with 1-line descriptions + a filled example.
4. **Protocol** — (a) detect explicit intents, (b) infer implicit intents (platform→aspect ratio, hook, music, duration norms, narration), (c) map to routed_pipelines via AGENT_GUIDE "Best For" — **if nothing fits, set `routed_pipelines: []` and state plainly + suggest closest / unsupported [scenario #2, no-match path]**, (d) list capability_needs against capability registry families, (e) mark open_ambiguities, (f) set confidence. Works on requests in any language (Vietnamese is the user default) → map to English pipeline names. [scenario #3]
5. **Confidence + fast-path** — **`high` is defined as: exactly one pipeline fits AND platform/duration/visual-treatment clear** [scenario #4]; anything else = medium/low. high → state route + proceed (no question); medium/low → present route + brief confirm folded into the creative-intake transition turn. State capability_needs as provisional (preflight verifies).
6. **Compound (v1 = detect + suggest, NOT orchestrate)** — detect ≥2 deliverables → SUGGEST running pipelines sequentially as separate manual runs (each its own full Rule Zero, reusing `projects/<name>/`); always confirm regardless of confidence. State explicitly that automated chaining is out of scope for v1.
7. **Handoff** — pass intent_map to pipeline selection + creative-intake; creative-intake consumes open_ambiguities, does not re-decompose.
8. **Anti-patterns** — don't interrogate, don't generate concepts, don't hardcode pipelines, don't slow clear requests, don't duplicate creative-intake questions.

## Related Code Files

- Create: `skills/meta/intent-analyst.md`
- Reference only (read, do not modify in this phase): `skills/meta/creative-intake.md`, `skills/meta/onboarding.md`, `skills/meta/video-reference-analyst.md`, `AGENT_GUIDE.md` (Rule Zero + "Available Pipelines" table)

## Implementation Steps

1. Re-read `skills/meta/creative-intake.md` and `skills/meta/onboarding.md` to match house style (heading shape, "When to Use", "Anti-Patterns").
2. Re-read AGENT_GUIDE "Available Pipelines" table to confirm the pipeline names/Best-For the skill will route against.
3. Draft `skills/meta/intent-analyst.md` per the 8-section outline above.
4. Include worked `intent_map` examples: one simple request (fast-path, high confidence), one compound (detect + suggest-sequential, v1), and **≥1 in Vietnamese** [scenario #3], grounded in the user's domain (e.g., meditation long-form + shorts). Concrete, not abstract.
5. State the source-of-truth rule (reads AGENT_GUIDE table at runtime) explicitly so it cannot drift; **mark examples as illustrative, not an authoritative pipeline list** [scenario #7].
6. Keep the file ≤ ~120 lines; trim prose, prefer one tight example per branch over verbose explanation.

## Success Criteria

- [ ] `skills/meta/intent-analyst.md` created, instruction-only, no schema/reflection/concept-seed content, ≤ ~120 lines.
- [ ] Contains role-boundary table delineating from the 3 existing skills + explicit "does not ask user" rule.
- [ ] Documents all 6 `intent_map` fields with a filled fast-path example and a filled compound (detect+suggest) example.
- [ ] Confidence thresholds (high→fast-path, medium/low→confirm) and single-turn confirm specified; high-confidence definition explicit; compound always confirms.
- [ ] capability_needs stated as provisional (preflight authoritative); skill never promises a capability.
- [ ] v1 single-pipeline scope explicit; automated compound chaining marked OUT (v2).
- [ ] Trigger scope excludes intra-pipeline refinement + exploratory requests.
- [ ] No-match path defined (`routed_pipelines: []` → closest/unsupported).
- [ ] Handles Vietnamese input with ≥1 worked VI example; examples marked illustrative.
- [ ] Routing instruction reads AGENT_GUIDE "Best For" at runtime; no hardcoded pipeline list.
- [ ] Style consistent with sibling `skills/meta/*.md`.

## Risk Assessment

- **Overlap with creative-intake** → mitigated by the role-boundary table + "does not ask user" rule. Verified in Phase 3 scenario 4.
- **Drift if pipeline list hardcoded** → mitigated by source-of-truth rule (read AGENT_GUIDE).
- **Scope creep into concept generation** → explicitly listed as anti-pattern + OUT of scope.
