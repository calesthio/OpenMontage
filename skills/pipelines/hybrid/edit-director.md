# Edit Director - Hybrid Pipeline

## When To Use

This stage creates the layered edit logic for a source-led video with support elements. The order matters: anchor cut first, support layers second.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"`, `"hyperframes"`, or `"ffmpeg"`. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Source/support assets and timeline intent |
| Playbook | Active style playbook | Typography and motion consistency |

## Process

### 1. Lock The Anchor Cut First

The viewer should understand the story before support overlays are added. If the anchor cut is weak, support layers will not save it.

### 2. Add Support In Priority Order

Typical order:

1. subtitles,
2. speaker or context labels,
3. diagrams or stat cards,
4. optional inserts,
5. CTA elements.

### 3. Protect Readability

Never stack too many support layers in one moment. If subtitles, labels, charts, and overlays collide, simplify.

### 4. Use Metadata For Layering Logic

Recommended metadata keys:

- `anchor_cut_notes`
- `layer_order`
- `overlay_windows`
- `variant_edit_rules`

### 5. Quality Gate

- the anchor cut works on its own,
- support layers clarify instead of distract,
- mobile readability survives,
- variants remain consistent.

## Common Pitfalls

- Trying to fix a weak cut with extra graphics.
- Letting support layers compete with the source.
- Building each platform variant as a separate editorial philosophy.
