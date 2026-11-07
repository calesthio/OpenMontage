# Script Director - Cinematic Pipeline

## When To Use

This stage builds the beat map, selected lines, title-card copy, and reveal structure for the cinematic piece. You are shaping rhythm, not writing a dense explainer.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` (legacy) or `schemas/artifacts/versions/script/1.1.schema.json` (reference-aware) | Artifact validation |
| Prior artifact | `state.artifacts["proposal"]["proposal_packet"]` | Emotional arc and source truth |
| Tools | `transcriber`, `scene_detect` | Optional dialogue mining and source review |


### Reference-aware v1.1 handoff

When a `video_analysis_brief@1.1` or `video_analysis_bundle@1.1` is present for a reference-driven run, carry the brief's `analysis_id`. For a bundle, carry the IDs in the selected concept's `reference_analysis_refs` (a non-empty subset is valid), not every member by default, in
`reference_analysis_refs` and emit a `script@1.1` artifact. Use plural
`narrative_profile_refs` because profiles compose; use namespaced `beat_role` values
rather than inventing a universal beat enum. Each section should expose `evidence_refs`
(even when empty for purely original material), semantic `visual_intent`, and
`audio_intent`. Camera, framing, and asset execution belong in `scene_plan`, not in the
script's semantic intent. See `docs/VIDEO_ANALYSIS_CONTRACT_V1_1.md`.

## Process

### 1. Build A Beat Map First

Use a simple structure:

- hook,
- escalation,
- reveal,
- landing.

If the piece is longer, add one midpoint turn. Do not let it become essay-shaped.

### 2. Use Dialogue Sparingly

If source speech exists, use `transcriber` to find:

- strong standalone lines,
- emotional phrases,
- concise declarations,
- reveal phrases.

If there is no useful dialogue, keep the script title-led or narration-led and say so in metadata.

### 3. Keep Title Cards Short

Title-card copy should feel trailer-like:

- fewer words,
- more contrast,
- more whitespace,
- more timing precision.

### 4. Store Beat Truth In Metadata

Recommended metadata keys:

- `beat_map`
- `dialogue_selects`
- `title_card_copy`
- `music_turns`
- `silence_windows`

### 5. Quality Gate

- the beat map escalates cleanly,
- dialogue and title cards do not explain the same thing twice,
- the reveal lands distinctly,
- the landing gives the viewer a final feeling or action.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- Writing full explanatory paragraphs instead of beats.
- Using too many title cards.
- Revealing the best moment too early.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
