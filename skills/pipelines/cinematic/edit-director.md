# Edit Director - Cinematic Pipeline

## When To Use

This stage turns the beat map into a paced cinematic timeline. Rhythm and restraint matter more than effect count.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, hero frames, beat map |
| Playbook | Active style playbook | Typography and transition consistency |

## Runtime Carry-Forward (REQUIRED)

`edit_decisions` is schema-invalid without `version`, `cuts`, and `render_runtime`, and `video_compose` refuses to render when `render_runtime` or `renderer_family` is missing. All of these were locked at proposal — copy them from the approved `proposal_packet.production_plan`; never choose or default them here:

- `version` — `"1.0"`.
- `render_runtime` — exactly `production_plan.render_runtime` (`remotion`, `hyperframes`, or `ffmpeg`). A different value needs user approval and a `render_runtime_selection` entry in `decision_log`.
- `renderer_family` — exactly `production_plan.renderer_family` (cinematic work is normally `cinematic-trailer`). Copy `composition_mode` as well when the proposal set it.
- `metadata.proposal_render_runtime` — the same locked runtime again. `video_compose` falls back to it for runtime-swap detection when it is not handed the `proposal_packet`.
- `metadata.delivery_promise` — a verbatim copy of `production_plan.delivery_promise` (keep `promise_type`). `video_compose` checks the cuts against it before rendering and again in `final_review`; without it the promise check is skipped with a warning.

## Process

### 1. Cut By Emotion First

Cuts should follow:

- emotional emphasis,
- reveal timing,
- musical turns,
- visual contrast.

Do not optimize only for information density.

### 2. Protect Strong Moments

If a look, line, or gesture is doing the work, let it live. Do not over-cover it with extra inserts.

### 3. Use Sound To Push The Edit

Ambience, impacts, dropouts, and music changes should help create momentum between scenes.

### 4. Use Metadata For Timing Logic

Recommended metadata keys (top-level `edit_decisions.metadata` — cuts and overlays are closed in the schema and reject extra keys):

- `beat_timing`
- `audio_turns`
- `title_card_windows`
- `reframe_notes`

### 5. Quality Gate

- the emotional arc is intact,
- reveals land clearly,
- title cards are sparse and timed with intent,
- strong moments are not buried under coverage.

## Common Pitfalls

- Overcutting emotional material.
- Using speed ramps or flashy transitions by default.
- Letting title cards replace editorial clarity.
