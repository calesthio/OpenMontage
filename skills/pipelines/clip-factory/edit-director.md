# Edit Director - Clip Factory Pipeline

## When To Use

This stage turns the approved clips into independent mini-edits. Each clip must work alone, but the collection should still feel like a coherent series.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"` or `"ffmpeg"` on this pipeline. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, layouts, transcripts |
| Playbook | Active style playbook | Transition and subtitle consistency |

## Process

### 1. Build A Shared Edit Template

Lock the batch defaults first:

- subtitle style,
- hook timing,
- lower-third timing,
- watermark behavior,
- audio fade lengths.

Then apply per-clip overrides only where necessary.

### 2. Optimize The First 2-3 Seconds

For every clip:

- start on motion, face, or result,
- show hook text immediately if needed,
- let subtitles begin with the first spoken word,
- avoid intros that delay the point.

### 3. Keep Boundaries Clean

- no cuts mid-word,
- no trailing silence after the point lands,
- no "setup for setup's sake" before the hook,
- no outro cards unless they earn the time.

### 4. Use Metadata For Multi-Variant Detail

Recommended metadata keys:

- `batch_template`
- `clip_variants`
- `hook_windows`
- `cta_windows`

### 5. Quality Gate

- each clip is self-contained,
- the first seconds hook fast,
- overlay stack is readable on mobile,
- the batch retains consistent styling and fades.

## Common Pitfalls

- Building one highlight reel instead of independent clips.
- Letting branding delay the hook.
- Overcrowding the screen with hook text, subtitles, watermark, and lower third simultaneously.
- Applying inconsistent transition timing across the batch.
