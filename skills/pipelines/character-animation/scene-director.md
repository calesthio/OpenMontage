# Scene Director - Character Animation Pipeline

## Goal

Produce a `scene_plan` where each scene is feasible for rigged character
animation.

## Scene Planning Fields


### Reference-aware v1.1 handoff

When a `video_analysis_brief@1.1` or `video_analysis_bundle@1.1` is present for a reference-driven run, carry the brief's `analysis_id`. For a bundle, carry the IDs in the selected concept's `reference_analysis_refs` (a non-empty subset is valid), not every member by default, in
`reference_analysis_refs` and emit `scene_plan@1.1`. Use plural `script_section_ids`
when one character scene realizes multiple script sections. Keep character-specific
acting in `character_actions` and populate the five visual plan fields explicitly when
the reference informs them. See `docs/VIDEO_ANALYSIS_CONTRACT_V1_1.md`.

For each scene, include:

- character IDs,
- emotional beat,
- action sequence,
- camera/framing,
- background,
- props,
- effects,
- required assets,
- transition notes.

Use `type: "character_scene"` for rigged character acting scenes. Store
character-specific detail in `character_actions`; do not put per-scene acting
data in arbitrary metadata because the shared `scene_plan` schema rejects
unknown per-scene fields.

## Complexity Budget

Prefer fewer, stronger shots:

- one establish,
- one action beat,
- one reaction beat,
- one resolution beat.

Avoid scenes that require many unique views or complex physical contact unless
the user approved that complexity.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
