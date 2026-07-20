# Idea Director - Localization Dub Pipeline

## When To Use

Use this pipeline when the user has a source video and wants translated deliverables: subtitles, dubbed audio, or localized videos in one or more target languages.

Your first responsibility is to define what kind of localization is actually required, because subtitle-only, dubbed-audio, and lip-synced translation are different jobs.

## Runtime Selection (MANDATORY — present the constraint, don't silently pick)

Lock `render_runtime = "remotion"` (composed deliverables with per-locale caption burn / lip-sync) or `"ffmpeg"` (pure subtitle-burn over source with no composition). **HyperFrames is NOT a valid runtime on this pipeline in Phase 1** — localization depends on Remotion's caption stack and, for dubbed-with-lip-sync, on the Remotion TalkingHead pipeline.

Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": do NOT silently default to remotion. Tell the user: "HyperFrames is available, but localization-dub depends on Remotion caption + TalkingHead parity that isn't there yet in Phase 1 — remotion is the only viable choice". Record a `render_runtime_selection` decision with hyperframes `rejected_because: "caption + lip-sync parity deferred on localization-dub"`.

## Reference Inputs

- `docs/localization-dubbing-best-practices.md`
- `skills/creative/short-form.md`
- `skills/creative/long-form.md`

## Process

### 1. Define The Localization Scope

Capture:

- source language,
- target languages,
- review owner,
- whether glossary or legal review is required,
- whether the user needs subtitles, dubbed audio, lip-sync, or a mix.

### 2. Classify The Source

Record the source mode:

- `single_speaker`
- `multi_speaker`
- `voiceover_led`
- `speaker_led_on_camera`

Also record whether on-screen text or motion graphics will need manual replacement or coverage.

### 3. Pick Deliverables That Match Reality

Possible deliverables:

- subtitle package only,
- dubbed video without lip sync,
- lip-synced localized video,
- per-language export bundle.

### 4. Build The Brief

Recommended metadata keys:

- `source_language`
- `target_languages`
- `deliverable_mode_map`
- `glossary_terms`
- `protected_terms`
- `review_requirements`
- `timing_risks`

### 5. Quality Gate

- localization scope is explicit,
- target outputs are realistic,
- glossary and review requirements are captured,
- risk increases from speaker count or visible mouths are surfaced.

## Common Pitfalls

- Calling every translation request a dubbing request.
- Ignoring glossary control until after audio is generated.
- Promising lip sync on visually difficult source footage without warning.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
