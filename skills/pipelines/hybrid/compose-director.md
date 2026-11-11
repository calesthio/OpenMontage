# Compose Director - Hybrid Pipeline

## When To Use

Render the hybrid project so source media, support graphics, and audio all remain coherent across outputs.

## Runtime Routing (MANDATORY first step)

Read `edit_decisions.render_runtime`. Hybrid work typically sticks with Remotion because source footage + React support overlays compose cleanly in one pass:

- **`render_runtime="remotion"`** — default. Source footage via `<OffthreadVideo>`, support graphics as React components, one render.
- **`render_runtime="hyperframes"`** — pick only when the support layer is HTML/GSAP-native (e.g., animated text callouts, registry blocks). Source footage is still possible via `<video class="clip">` but lose some of the Remotion component stack. See `skills/core/hyperframes.md`.
- **`render_runtime="ffmpeg"`** — rare on this pipeline; implies no generated support layer.

Silent runtime swap is a CRITICAL governance violation. Escalate blockers per AGENT_GUIDE.md before substituting.

**Confirm `edit_decisions.metadata.proposal_render_runtime` is set** (the edit stage copies the runtime locked at idea into it). This pipeline has no proposal stage, so there is no `proposal_packet` to pass to `video_compose.execute()`; the in-tool swap check compares that metadata key with `edit_decisions.render_runtime` instead. Without it the check is `skipped` and you rely entirely on the reviewer skill to catch drift — send it back to the edit stage rather than patching `edit_decisions` here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Edit logic and support assets |
| Tools | `video_compose`, `audio_mixer`, `video_stitch`, `video_trimmer`, `color_grade`, `audio_enhance` | Final assembly and polish |
| Playbook | Active style playbook | Output consistency |

## Process

### 1. Verify Source And Support Balance

The final render should still look like a source-led video with support, not a collage of unrelated systems.

### 2. Check Variant Integrity

For each output variant, verify:

- crop safety,
- text safety,
- subtitle legibility,
- audio consistency.

### 3. Keep Audio Coherent

Source dialogue, narration, music, and effects should feel like one mix, not separate layers fighting for space.

### 4. Use Render Metadata

Recommended metadata keys:

- `variant_outputs`
- `balance_checks`
- `subtitle_checks`
- `audio_notes`

## Common Pitfalls

- Good master cut, broken platform variants.
- Support graphics clipping in vertical exports.
- Audio loudness shifting between source and generated sections.
