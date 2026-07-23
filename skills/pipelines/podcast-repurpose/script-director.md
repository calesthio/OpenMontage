# Script Director - Podcast Repurpose Pipeline

## When To Use

This stage creates the transcript truth, speaker attribution, highlight set, and chapter structure that every later stage depends on.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["idea"]["brief"]` | Deliverable mix and source truth |
| Tools | `transcriber`, `audio_enhance` | Diarized transcript and cleanup |

## Process

### 1. Protect Transcript Quality

If the source audio is weak, use `audio_enhance` before or alongside transcription. Speaker diarization quality directly affects quote attribution and clip quality.

### 2. Produce A Speaker-Aware Transcript

Diarization is not optional for multi-speaker episodes. Verify speaker mapping early and store the richer diarization detail in `script.metadata`.

Recommended metadata keys:

- `speaker_map`
- `transcript_path`
- `chapter_candidates`
- `highlight_candidates`
- `rejected_highlights`

### 3. Rank Highlight Moments

Use the episode transcript to find:

- concise insights,
- surprising claims,
- emotional peaks,
- debates,
- practical advice,
- memorable phrasing.

Every highlight should be evaluated for:

- standalone clarity,
- hook strength,
- attribution confidence,
- platform fit.

### 4. Build Chapters For Long-Form Packaging

If the user wants a full-episode companion asset, identify the topic shifts now. These become chapter markers and later visual transition points.

### 5. Keep The Schema Clean

Use `sections[]` for the structured production-facing segments and put the richer highlight inventory in metadata.

### 6. Quality Gate

- speaker attribution is trustworthy,
- the highlight set is strong enough for the requested deliverables,
- weak clips are rejected instead of padded,
- chapter markers cover the long-form conversation cleanly.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- Treating diarization errors as minor when they change who said the quote.
- Selecting clips that need too much earlier context.
- Overfitting the batch to one section of the episode.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
