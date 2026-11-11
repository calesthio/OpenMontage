# Publish Director - Character Animation Pipeline

## Goal

Package the final character-animation deliverable with honest metadata and a
strong character-forward thumbnail concept.

## Requirements

- Mention the actual visual treatment: local rigged character animation,
  procedural effects, Remotion/HyperFrames render, or mixed.
- Pick a poster frame where the main character's emotion is readable.
- If the output is a sample, label it as a sample.
- If the final is inspired by a reference, describe the inspiration without
  claiming duplication.

## Packaging

Use `export_bundle` (local and offline; it never uploads). Pass the final
`video_path` from `render_report`, the `title`, and the metadata you prepared.
It writes the export directory (`projects/<project>/exports/` for a video in the
project's `renders/`) and returns a schema-valid `publish_log` in
`data["publish_log"]`; persist that as the stage artifact. The schema is closed,
so the notes below go under `publish_log.metadata`. See
`skills/pipelines/explainer/publish-director.md` Step 5 for the full input list
and export layout.

## Output

Produce `publish_log` (notes under `metadata`) with:

- final video path,
- thumbnail/poster-frame notes,
- title ideas,
- description,
- platform-specific export notes,
- limitations or follow-up recommendations.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
