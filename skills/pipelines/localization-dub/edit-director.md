# Edit Director - Localization Dub Pipeline

## When To Use

Translate the scene plan and localized asset kit into concrete timeline decisions for each language output. The goal is to preserve the source structure where possible without pretending all languages land on the same timing.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"` or `"ffmpeg"` on this pipeline. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Process

### 1. Preserve Structure By Default

Keep the original scene order and major timing unless the translated audio clearly requires extension, compression, or coverage.

### 2. Apply The Chosen Dub Mode

Per deliverable, decide where to:

- keep original picture with new subtitles,
- replace only the audio,
- use lip-sync output,
- cover mismatch with graphics or B-roll.

### 3. Keep Language Variants Organized

Separate timeline decisions by locale so versioning stays clear all the way into compose and publish.

### 4. Use Metadata For Variant Control

Recommended metadata keys:

- `locale_timeline_map`
- `timing_adjustments`
- `coverage_sections`
- `subtitle_strategy_by_locale`

### 5. Quality Gate

- language variants are explicit,
- timing changes are recorded,
- coverage decisions are deliberate,
- the original structure is only changed where necessary.

## Common Pitfalls

- Forcing every language to match source timing exactly.
- Mixing locale-specific notes into one ambiguous edit list.
- Hiding sections where the dub treatment is visually weak.
