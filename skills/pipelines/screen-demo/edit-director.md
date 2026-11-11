# Edit Director - Screen Demo Pipeline

## When To Use

This stage turns the plan into a concrete, schema-valid edit: trims, speeds, overlays, subtitles, and transitions. Keep the edit simple enough to execute with the current tooling and explicit enough that composition is predictable.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"`, `"hyperframes"`, or `"ffmpeg"`. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, visual plan, timing |
| Playbook | Active style playbook | Overlay and pacing rules |

## Process

### 1. Start With The Smallest Clear Edit

Screen demos get worse when over-edited. Build the timeline in this order:

1. trim or cut dead time,
2. apply speed changes,
3. place overlays,
4. set subtitle behavior,
5. define audio behavior,
6. capture detailed crop/ramp notes in `edit_decisions.metadata`.

### 2. Keep The Schema Clean

Use `cuts[]` for actual source segments and speed changes. Use `overlays[]`, `subtitles`, `music`, and `transitions` only for things the schema already models. Put screen-demo-specific detail in metadata:

- `crop_keyframes`
- `speed_plan`
- `subtitle_position_overrides`
- `audio_notes`
- `variant_notes`

### 3. Editing Rules

- the viewer should see useful motion or result within the first seconds,
- result moments stay at normal speed,
- typing, installs, and waiting should be accelerated or removed,
- no cut starts mid-word or ends before the payoff lands,
- do not introduce more motion through editing than the scene plan asked for.

### 4. Overlay Rules

- hook or step label can appear immediately,
- callouts should appear slightly before the action,
- blur masks must be treated as critical, not optional,
- subtitles and callouts must not compete for the same space.

### 5. Audio Rules

- keep primary speech clear and centered,
- mute or greatly reduce meaningless sped-up noise,
- only use background music if it adds value and survives ducking gracefully,
- if narration was generated, ensure it fits the tightened timeline.

### 6. Quality Gate

**Timeline integrity:**
- [ ] Cuts cover the full intended timeline
- [ ] No accidental black gaps
- [ ] Speed ramps don't overlap
- [ ] Effective duration matches the brief closely

**Overlay integrity:**
- [ ] Every planned callout or mask is represented
- [ ] No overlay collisions
- [ ] UI-anchored overlays are documented clearly enough to position during compose

**Audio integrity:**
- [ ] Primary audio or narration covers the entire timeline
- [ ] Speed-up segments have intentional audio treatment
- [ ] Music, if present, will not compete with instruction

**Subtitle integrity:**
- [ ] Subtitles are present for all narrated sections
- [ ] Position overrides protect important UI content
- [ ] Subtitle timing still works after planned speed changes

## Common Pitfalls

- Overbuilding the edit with cinematic transitions the workflow does not need.
- Letting sped-up audio become a wall of harsh clicks and typing.
- Forgetting that crop and speed plans live in metadata, not arbitrary schema fields.
