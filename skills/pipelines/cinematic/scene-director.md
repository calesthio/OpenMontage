# Scene Director - Cinematic Pipeline

## When To Use

You are deciding how each cinematic beat will look and transition. This is where mood becomes a visual plan.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` (legacy) or `schemas/artifacts/versions/scene_plan/1.1.schema.json` (reference-aware) | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | Beat map and source truth |
| Tools | `frame_sampler`, `scene_detect` | Source inspection and reframing checks |
| Playbook | Active style playbook | Color and typography consistency |


### Reference-aware v1.1 handoff

When a `video_analysis_brief@1.1` or `video_analysis_bundle@1.1` is present for a reference-driven run, carry the brief's `analysis_id`. For a bundle, carry the IDs in the selected concept's `reference_analysis_refs` (a non-empty subset is valid), not every member by default, in
`reference_analysis_refs` and emit a `scene_plan@1.1` artifact. Use plural
`script_section_ids` when a scene realizes more than one script section. Populate the
five visual plan fields (`subject`, `subject_motion`, `scene`, `spatial_framing`, and
`camera`) explicitly; write `N/A — ...` rather than silently omitting an aspect. Keep
reference evidence in `evidence_refs`; do not treat timing overlap as a substitute for a
dangling explicit ID. See `docs/VIDEO_ANALYSIS_CONTRACT_V1_1.md`.

## Process

### 1. Make Hero Frames Explicit

Every cinematic piece needs a few memorable frames. Define them directly:

- opening image,
- reveal image,
- final image,
- any title-card hero moments.

### 2. Keep Source-Led Scenes Primary

If source footage exists, let it carry the piece. Generated inserts or text cards should support transitions, emphasis, or missing coverage, not dominate the timeline.

### 3. Limit Transition Vocabulary

Choose a small set:

- hard cut,
- fade to black,
- slow dissolve,
- restrained push or punch-in.

Too many transition types kill the mood.

### 4. Use Metadata For Visual Rules

Recommended metadata keys:

- `hero_frames`
- `transition_rules`
- `aspect_ratio_rules`
- `title_card_rules`
- `support_insert_rules`

### 5. 5-Aspect Scene-Plan Checklist

> Every scene beat — and especially every hero frame — must specify all five aspects. Cinematic relies on a small number of memorable frames; vague hero-frame specs are the single most common failure mode and produce unpredictable model output. Marking an aspect as N/A is allowed but must be explicit (e.g., "no subject — establishing scenery shot"). Silent omission is forbidden.
>
> 1. **Subject** — type + key visual attributes; if multiple, how to disambiguate. For hero frames, identity must be anchored verbatim across shots.
> 2. **Subject Motion** — actions in temporal order; subject↔object / subject↔subject interactions.
> 3. **Scene** — overlays (separately!) + POV + setting + time of day + scene dynamics.
> 4. **Spatial Framing** — shot size + position-in-frame + depth (FG/MG/BG) + camera-height-relative; and how those CHANGE across the beat.
> 5. **Camera** — playback speed → lens distortion → height → angle → focus/DoF → steadiness → movement.
>
> See `skills/creative/video-gen-prompting.md` for the primitive vocabulary.

> **Overlays callout.** Overlays (titles, subtitles, HUD, watermarks, framing graphics, lower-thirds, name plates, end-tag cards) are NOT part of the scene's foreground/midground/background depth axis. List them separately in scene metadata (`overlays: [...]`) with content and placement. Never describe an overlay as "in the foreground" — that confuses both downstream tools and any video-understanding model that re-analyzes the output.

### 6. Quality Gate

- every beat has a scene treatment,
- hero frames are identifiable AND fully specified across all 5 aspects,
- support inserts are justified,
- overlays are recorded under `overlays:`, never inside the depth/framing description,
- the visual language stays consistent across the piece.

## Common Pitfalls

- Using title cards as filler.
- Treating generated inserts like the primary story without saying so.
- Planning flashy transitions for every beat.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
