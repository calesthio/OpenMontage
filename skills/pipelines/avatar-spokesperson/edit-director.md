# Edit Director - Avatar Spokesperson Pipeline

## When To Use

Turn the planned presenter scenes and produced assets into a coherent spokesperson timeline. The quality bar is steady delivery, readable support layers, and a clear CTA landing.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"` on this pipeline. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Process

### 1. Cut The Presenter Track First

Assemble the core spokesperson performance before adding support layers. If the presenter cut is weak, extra graphics will not rescue it.

### 2. Add Support Layers Sparingly

Use overlays only where they help:

- short proof points,
- product names,
- pricing or feature cards,
- CTA reinforcement,
- subtitles.

### 3. Respect Spoken Rhythm

Keep pauses where they help emphasis. Do not trim so tightly that the avatar feels rushed or robotic.

### 4. Plan Deliverables Clearly

Recommended metadata keys:

- `hero_cut_order`
- `cta_frame_range`
- `overlay_timing_map`
- `variant_decisions`

### 5. Quality Gate

- the presenter remains the anchor,
- overlays are timed cleanly,
- scene transitions are calm and intentional,
- the CTA lands once and clearly.

## Common Pitfalls

- Overcutting to simulate energy.
- Letting captions, side panels, and lower thirds compete for the same area.
- Ending without a clean CTA hold.
