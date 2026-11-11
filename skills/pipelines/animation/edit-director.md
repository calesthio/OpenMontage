# Edit Director - Animation Pipeline

## When To Use

This stage turns the scene plan into an animatic-grade edit plan. Timing is the product.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, timing plan, and beats |
| Playbook | Active style playbook | Motion and typography rules |

## Runtime Carry-Forward (REQUIRED)

`edit_decisions` is schema-invalid without `version`, `cuts`, and `render_runtime`, and `video_compose` refuses to render when `render_runtime` or `renderer_family` is missing. All of these were locked at proposal — copy them from the approved `proposal_packet.production_plan`; never choose or default them here:

- `version` — `"1.0"`.
- `render_runtime` — exactly `production_plan.render_runtime` (`remotion`, `hyperframes`, or `ffmpeg`). A different value needs user approval and a `render_runtime_selection` entry in `decision_log`.
- `renderer_family` — exactly `production_plan.renderer_family` (animation work is normally `animation-first`). Copy `composition_mode` as well when the proposal set it.
- `metadata.proposal_render_runtime` — the same locked runtime again. `video_compose` falls back to it for runtime-swap detection when it is not handed the `proposal_packet`.
- `metadata.delivery_promise` — a verbatim copy of `production_plan.delivery_promise` (keep `promise_type`). `video_compose` checks the cuts against it before rendering and again in `final_review`; without it the promise check is skipped with a warning.

## Process

### 1. Protect Hold Time

After key reveals, plan enough time for the viewer to process the frame. Do not stack every scene edge to edge with motion.

### 2. Stagger Secondary Elements

Primary element first, supporting elements second. The edit decisions should reinforce hierarchy.

### 3. Keep Motion Meaningful

Motion should signal:

- emphasis,
- transition,
- transformation,
- contrast.

### 4. Use Metadata For Timing Detail

Recommended metadata keys (top-level `edit_decisions.metadata` — cuts and overlays are closed in the schema and reject extra keys):

- `hold_windows`
- `stagger_rules`
- `transition_map`
- `scene_timing_notes`
- `audio_mix_plan` — `"composition"`, `"premix"` or `"flat"` (see below)

The Remotion-only cut props the Compose stage needs (`type: "anime_scene"`, `images`, `particles`, ...) are not `edit_decisions` fields either: they come from `scene_plan.metadata.tool_path_map` and go into the Compose stage's Remotion composition JSON (compose-director section 2).

**Music under narration.** The Remotion `Explainer` composition ducks the music only when the Compose stage's composition JSON sets `audio.music.ducking`, taking speech timing from the word `captions` (no captions → the whole video counts as speech, one constant lower level). `audio_mixer` ducks on any render path; HyperFrames and FFmpeg renders do not duck by themselves. When narration and music overlap, choose and record `metadata.audio_mix_plan`:

- `"composition"` (recommended on the Remotion path when word captions exist) — keep `audio.music.ducking.enabled: true`; the Compose stage sets `audio.music.ducking` in the composition JSON.
- `"premix"` (recommended otherwise) — keep `audio.music.ducking.enabled: true`; the Compose stage mixes narration + music with `audio_mixer` (`operation: "full_mix"`) and renders that single track.
- `"flat"` — set `audio.music.ducking.enabled: false` and keep `audio.music.volume` at 0.08–0.12 so the bed never competes with the voice.

### 5. Quality Gate

- key information has enough dwell time,
- movement clarifies hierarchy,
- transitions stay consistent,
- the edit remains readable on the target platform.

## Common Pitfalls

- Overcrowding the timeline with continuous motion.
- Revealing all elements at once.
- Letting stylistic motion reduce readability.
