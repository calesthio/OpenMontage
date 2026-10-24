# Script Director - Character Animation Pipeline

## Goal

Write scripts as performable animation beats, not just narration.

## Process


### Reference-aware v1.1 handoff

When a `video_analysis_brief@1.1` or `video_analysis_bundle@1.1` is present for a reference-driven run, carry the brief's `analysis_id`. For a bundle, carry the IDs in the selected concept's `reference_analysis_refs` (a non-empty subset is valid), not every member by default, in
`reference_analysis_refs` and emit `script@1.1`. Keep action beats in the script, use
namespaced `beat_role` values when a narrative profile is selected, and attach
`evidence_refs` to reference-derived claims. See `docs/VIDEO_ANALYSIS_CONTRACT_V1_1.md`.

1. Lock audio architecture:
   - music-only,
   - narrator,
   - character dialogue,
   - narrator plus character sounds/dialogue.
2. Break the story into beats that can be acted with poses.
3. For each beat, state what changes visually:
   - emotion,
   - gaze,
   - body pose,
   - prop interaction,
   - camera,
   - environment.

## Writing Rules

- Prefer short visual beats with readable holds.
- Avoid action that needs many unique hand-drawn poses unless approved.
- Dialogue should be short enough for mouth-shape approximation.
- Silent/music-led scenes need stronger physical acting notes.

## Output Notes

In the `script` artifact metadata, include:

- `audio_architecture`,
- `character_beats`,
- `required_emotions`,
- `required_actions`.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
