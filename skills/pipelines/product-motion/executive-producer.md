# Executive Producer — Product-Motion Pipeline

## When to Use

You are orchestrating a **product-motion** run: the user pointed OpenMontage at
a product's source repository and wants polished-SaaS product screen
animations — the product's real UI, rebuilt faithfully, assembling on glass
surfaces with spring motion and sound effects.

This pipeline is **beta** — say so when the user selects it.

## The quality bar that rules this pipeline

**Fidelity is a first-class deliverable.** A gorgeous animation of a UI the
product doesn't have is a failed run. The provenance chain is the mechanism:

```
repo file+line → design_system token → replica scene component
repo source_files → ui_inventory screen → scene_plan scene → asset provenance
```

Any stage that breaks a link in this chain gets sent back, budget permitting.

## Stage flow

`repo_analysis → proposal → script → scene_plan → assets → edit → compose → publish`

Gates (from the manifest, binding): repo_analysis, proposal, script,
scene_plan, assets (the fidelity gate), publish. edit and compose
auto-proceed.

## Orchestration duties

1. **Init the workspace** (`init_project`) and open the Backlot board before
   any stage. The repo under analysis is *input*, never workspace — nothing is
   ever written into the user's product repo.
2. **Preflight** per AGENT_GUIDE: `provider_menu_summary()`, present the
   capability menu. This pipeline needs: a TTS provider (narration), Remotion
   or HyperFrames (composition), and optionally `sfx_gen` + `music_gen`
   (ELEVENLABS_API_KEY) for sound. `repo_design_extractor` is always
   available (local). If no SFX provider is configured, surface it at
   proposal — the "with sound effects" promise degrades and the user must
   choose knowingly.
3. **Read the director skill before each stage** — no exceptions.
4. **Budget**: default $2.00. Narration (TTS) + music (1 track) + 4-6 SFX +
   render is typically well under this; repo analysis and composition
   authoring are token-cost, not API-cost.
5. **Escalate blockers** per the Decision Communication Contract — especially
   runtime unavailability at compose (never silently swap `render_runtime`).
6. **Send-backs**: max 3 per stage. A fidelity failure at the assets gate
   (replica doesn't match source) sends assets back, not scene_plan — unless
   the scene plan referenced a screen the inventory never had, which is a
   repo_analysis defect.

## What NOT to do

- Do not let the run proceed past repo_analysis if the design_system is
  unvalidated or tokens lack provenance.
- Do not substitute a live-URL capture (`website-to-video`) for repo
  extraction without telling the user — different grounding, different truth.
- Do not allow stock scene-type assembly (`cut.type` catalog) — this pipeline
  composes via the atelier path; the `_ATELIER_STOCK_IMPORT_RE` guardrail in
  `video_compose` will fail the render anyway.
- Do not skip the per-scene snapshot review at the assets gate to save time.
