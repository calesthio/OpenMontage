# Compose Director - Podcast Repurpose Pipeline

## When To Use

Render the podcast-derived outputs with audio fidelity as the top priority. The visuals need to support the speech, not compete with it.

## Runtime Routing (HARD CONSTRAINT — Remotion or FFmpeg only)

Phase 1 deferred from HyperFrames. `edit_decisions.render_runtime` must be `"remotion"` (audiograms, composed outputs) or `"ffmpeg"` (pure-audio-led clip exports). HyperFrames caption-burn parity is deferred, and podcast outputs lean on Remotion's word-level caption stack.

- If `edit_decisions.render_runtime == "hyperframes"`, stop. Re-open the idea stage and surface the constraint to the user. Never silently rewrite the runtime.
- Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": tell the user HyperFrames exists and why it isn't viable on this pipeline, rather than silently locking remotion. Record a `render_runtime_selection` decision with hyperframes `rejected_because: "caption-burn parity deferred on podcast-repurpose"`.
- This pipeline has no proposal stage, so there is no `proposal_packet` to pass, and `video_compose.execute()` does not accept `brief`. The in-tool runtime-swap check instead compares `edit_decisions.render_runtime` with `edit_decisions.metadata.proposal_render_runtime` (set by the edit stage to the runtime locked at idea). If that key is missing the check reports `skipped` — send it back to the edit stage rather than patching `edit_decisions` here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Output plans and asset paths |
| Tools | `video_compose`, `audio_mixer` | Rendering and mix control |
| Playbook | Active style playbook | Brand consistency |

## Process

### 1. Render Highest-Value Outputs First

Priority order:

1. short highlight clips
2. quote-led clips
3. optional long-form companion video

This keeps the most publishable assets available first.

### 2. Preserve Audio Quality

- avoid unnecessary re-encoding,
- keep speech intelligible and stable,
- use music sparingly and only when it does not compete,
- verify subtitle sync after render.

### 3. Respect Platform Shapes

- `9:16` for short-form social
- `1:1` for quote-led or feed-safe clips
- `16:9` for long-form YouTube companion output

### 4. Verify Every Deliverable

- correct duration,
- correct aspect ratio,
- readable subtitles,
- accurate speaker attribution,
- stable audio,
- consistent brand treatment.

### 5. Use Render Report Metadata

Recommended metadata keys:

- `deliverable_groups`
- `audio_notes`
- `subtitle_checks`
- `failed_outputs`

## Common Pitfalls

- Letting visual treatments degrade audio quality.
- Rendering the full companion first and delaying the clips that matter most.
- Forgetting that a simple, readable clip beats a technically elaborate but confusing one.
