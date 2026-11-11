# Compose Director - Avatar Spokesperson Pipeline

## When To Use

Render the final spokesperson outputs. The bar is simple: the presenter must look stable, speech must be clear, and subtitles or support cards must not crowd the frame.

## Runtime Routing (HARD CONSTRAINT — Remotion only)

Phase 1 deferred from HyperFrames. `edit_decisions.render_runtime` must be `"remotion"`. This pipeline depends on the Remotion `TalkingHead` composition and `remotion_caption_burn` — both have no HyperFrames parity in Phase 1.

- If `edit_decisions.render_runtime == "hyperframes"`, stop. Re-open the idea stage and surface the constraint. Silent rewrite is a governance violation.
- Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": the lock to remotion is NOT an excuse to skip the conversation. The user deserves to know that HyperFrames exists as a runtime and why it isn't viable for avatar-spokesperson. Log a `render_runtime_selection` decision with hyperframes `rejected_because: "TalkingHead + caption parity deferred on avatar-spokesperson"`.
- This pipeline has no proposal stage, so there is no `proposal_packet` to pass, and `video_compose.execute()` does not accept `brief`. The in-tool runtime-swap check instead compares `edit_decisions.render_runtime` with `edit_decisions.metadata.proposal_render_runtime` (set by the edit stage to the runtime locked at idea). If that key is missing the check reports `skipped` — send it back to the edit stage rather than patching `edit_decisions` here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | What to render |
| Tools | `video_compose`, `audio_mixer`, `video_stitch`, `audio_enhance` | Render and audio finishing |
| Playbook | Active style playbook | Typography and layout rules |

## Process

### 1. Render The Hero Cut First

Prefer one strong master before derivatives. Compose:

- presenter video,
- subtitles,
- lower-thirds,
- CTA cards,
- mixed narration.

### 2. Keep The Frame Clean

Subtitle and CTA placement matter more here than flashy transitions. Leave the face and mouth region unobstructed.

### 3. Verify Mouth Timing And Audio

If the avatar path used lip sync or audio-driven talking head, check:

- mouth timing,
- face artifacts,
- drift on long sections,
- audio clarity.

### 4. Verify Every Output

Record important findings in:

- `render_report.verification_notes`
- `render_report.warnings`
- `render_report.metadata.variant_notes`

### 5. Quality Gate

- the output file is valid,
- speech is clear,
- subtitles stay readable,
- the presenter remains visually stable.

## Common Pitfalls

- Letting subtitles cover the chin or mouth area.
- Shipping a long lip-sync render without spot-checking drift.
- Making derivative crops that cut off the presenter or CTA.
