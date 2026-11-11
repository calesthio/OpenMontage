# Compose Director - Localization Dub Pipeline

## When To Use

Render the localized outputs. The quality bar is intelligibility, timing coherence, and clear version labeling across every language package.

## Runtime Routing (HARD CONSTRAINT — Remotion or FFmpeg only)

Phase 1 deferred from HyperFrames. `edit_decisions.render_runtime` must be `"remotion"` or `"ffmpeg"`. Localization depends on Remotion's caption stack (per-locale subtitle burn) and, when dubbing with lip-sync, on the Remotion TalkingHead pipeline. HyperFrames has no parity for either in Phase 1.

- If `edit_decisions.render_runtime == "hyperframes"`, stop. Re-open the idea stage and surface the constraint — don't silently rewrite the runtime.
- Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": the pipeline's constraint does NOT skip the conversation. Present the constraint to the user so they know HyperFrames exists but isn't viable here. Log a `render_runtime_selection` decision with hyperframes `rejected_because: "caption + lip-sync parity deferred on localization-dub"`.
- This pipeline has no proposal stage, so there is no `proposal_packet` to pass, and `video_compose.execute()` does not accept `brief`. The in-tool runtime-swap check instead compares `edit_decisions.render_runtime` with `edit_decisions.metadata.proposal_render_runtime` (set by the edit stage to the runtime locked at idea). If that key is missing the check reports `skipped` — send it back to the edit stage rather than patching `edit_decisions` here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Locale-specific render instructions |
| Tools | `video_compose`, `audio_mixer`, `video_trimmer`, `audio_enhance` | Final render and audio finishing |
| Playbook | Active style playbook | Subtitle placement and output quality |

## Process

### 1. Render By Locale

Treat each target language as its own deliverable set. Keep names and output directories explicit.

### 2. Expect Timing Adjustments

Allow for:

- subtitle reflow,
- dub-audio duration drift,
- longer CTA holds,
- optional trims or coverage sections.

### 3. Verify Every Locale

Record important findings in:

- `render_report.verification_notes`
- `render_report.warnings`
- `render_report.metadata.locale_notes`

Check:

- intelligibility,
- subtitle fit,
- obvious sync drift,
- version labeling.

### 4. Quality Gate

- each locale output exists,
- the dub and subtitle timing are acceptable,
- labels and filenames are unambiguous,
- warnings are preserved.

## Common Pitfalls

- Rendering all locales as if they were timing-identical.
- Forgetting to re-check subtitle line length after translation.
- Naming outputs in ways that hide the locale or treatment mode.
