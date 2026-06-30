---
title: intent-analyst meta skill — intent decomposition + pipeline routing
description: >-
  Add a meta skill that decomposes any actionable video request into explicit +
  implicit sub-intents and routes to one or more pipelines before
  pipeline-selection. Instruction-only (markdown), no code/schema/tool changes.
status: completed
priority: P2
branch: main
tags:
  - meta-skill
  - routing
  - intent-analysis
  - videoagent-port
blockedBy: []
blocks: []
created: '2026-06-30T15:55:43.974Z'
createdBy: 'ck:plan'
source: skill
---

# intent-analyst meta skill — intent decomposition + pipeline routing

## Overview

Port the **Intent Analysis** pattern from HKUDS/VideoAgent into OpenMontage as a new instruction-only meta skill `skills/meta/intent-analyst.md`. It runs at AGENT_GUIDE Rule Zero step 1 (before "identify pipeline"), decomposes the request into explicit + implicit sub-intents, and emits an informal `intent_map` that routes to one or more pipelines (compound supported) plus capability needs. A fast-path keeps clear single-pipeline requests friction-free. The skill does not interrogate the user (ambiguities are deferred to `creative-intake`), produces no concept seeds, and reads the AGENT_GUIDE "Best For" table as the source of truth for routing.

Design source: [brainstorm report](../reports/brainstorm-260630-2346-intent-analyst-meta-skill-design-report.md).

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Author skill](./phase-01-author-skill.md) | Completed |
| 2 | [Wire integration](./phase-02-wire-integration.md) | Completed |
| 3 | [Validate scenarios](./phase-03-validate-scenarios.md) | Completed |

## Acceptance Criteria

1. `skills/meta/intent-analyst.md` exists, instruction-only, no JSON schema / reflection loop / concept seeds. **Concise — target ≤ ~120 lines** (read into context on every actionable request; the "always run" overhead must stay cheap). [A-len]
2. For an actionable request, the protocol yields an `intent_map` (explicit_intents, implicit_intents, routed_pipelines, capability_needs, open_ambiguities, confidence) **before** pipeline selection.
3. Confidence drives behavior, not decoration: **high → fast-path** (state route, proceed, no extra question); **medium/low → present route + brief confirm** in the SAME turn that transitions to creative-intake (no separate Q&A round). [A4, A5]
4. **v1 = single-pipeline routing.** A compound request (≥2 deliverables) is **detected and SUGGESTED as sequential manual runs** (each pipeline = its own full Rule Zero, reusing the same `projects/<name>/`), and **always confirmed regardless of confidence**. intent-analyst does NOT auto-orchestrate a chain. [A1, compound-always-confirm]
5. `capability_needs` is **provisional only** — intent-analyst never promises a capability; existing preflight (Rule Zero step 4, after intent-analysis is inserted at step 1) verifies availability. Skill must not claim a routed pipeline will run before preflight. [A2]
6. intent-analyst never asks the user directly; ambiguities go to `open_ambiguities` → handled by `creative-intake`.
7. No duplicated interrogation between intent-analyst and creative-intake.
8. Routing reads AGENT_GUIDE "Best For" table; no hardcoded pipeline list.
9. AGENT_GUIDE Rule Zero + reading order, creative-intake, onboarding, video-reference-analyst, INDEX all reference the new skill correctly.
10. **Trigger scope = NEW production-initiating requests only.** Refinement requests *during* an in-flight pipeline (e.g. "change the music", "make it longer") do NOT re-trigger intent-analyst — the active stage handles them. [scenario #1, High]
11. **No-match path defined.** If no pipeline fits (`routed_pipelines: []`, e.g. audio-only podcast, meme GIF), intent-analyst states this plainly and suggests the closest pipeline or that it is unsupported — never force-fits a wrong pipeline. [scenario #2, High]
12. **Multilingual input.** Skill parses non-English requests (Vietnamese is the user's default) and maps to English pipeline names; includes ≥1 worked Vietnamese example. [scenario #3, High]
13. **`confidence: high` is defined**, not vibes: exactly one pipeline fits AND platform/duration/visual-treatment are clear. Anything else = medium/low. [scenario #4]
14. Skill examples avoid hardcoding pipeline names as authoritative — examples are illustrative and the "read AGENT_GUIDE table at runtime" rule is restated so stale examples can't cause mis-routes. [scenario #7]

## Scope Boundary (OUT)

No JSON schema, no reflection loop, no concept-seed generation, no Python/tool changes, no new pipeline manifest. **Automated compound pipeline chaining (cross-pipeline data-flow orchestration) is explicitly v2** — deferred until the inter-pipeline handoff mechanism is designed (see Open Decisions). v1 only *detects + suggests* sequential runs.

## Open Decisions (resolved for v1, revisit for v2)

- **A1 — compound data-flow (v2 design, resolved via predict --chain reason):** v1 defers automated chaining. **v2 = shared `projects/<name>/` + an informal `chain.json` ledger** at project root (NOT schema-validated): ordered list of pipelines, each entry `{pipeline, source_input, status}`. Pipeline N+1 consumes pipeline N's `render_report.output` as its source. Each pipeline still runs full Rule Zero + its own approval gate. Optimization: if pipeline N already produced a reusable `script`/`scene_plan`, clip-factory skips re-transcribe/re-detect. Ledger enables resume if the chain is interrupted. Distinct from per-stage checkpoints (those are intra-pipeline; chain.json is cross-pipeline).
- **A2 — ordering vs preflight:** intent-analyst runs at Rule Zero step 1 (before preflight). capability_needs provisional; preflight authoritative.
- **A3 — success metric (resolved via predict --chain reason): two-tier, no new infra.** Tier 1 (v1): qualitative gate in Phase 3 — no routing regression vs current judgment + surfaces ≥1 implicit intent. Tier 2 (ongoing): count **user route-overrides** as a one-line journal/checkpoint note whenever the user corrects the proposed pipeline; an override = mis-route signal. Promote to a curated request→expected-pipeline eval set ONLY if override rate proves mis-routing is a real problem (YAGNI until signal exists).
- **A4/A5 — confidence + UX:** thresholds and single-turn confirm folded into AC #3.

## Dependencies

No cross-plan dependencies. Standalone instruction change. Related-but-independent: `plans/260630-0044-standard-video-production-pipeline-sop` (different area — production SOP, not routing).
