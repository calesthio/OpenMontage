# Compose Director - Character Animation Pipeline

## Goal

Render the approved character animation and prove it was reviewed.

## Runtime Routing

First read `edit_decisions.render_runtime`. It must match the runtime locked in
proposal unless a `render_runtime_selection` decision explicitly changed it.

- `remotion`: stage assets into `remotion-composer/public`, build composition
  JSON, render via `video_compose`.
- `hyperframes`: materialize a HyperFrames workspace and let `video_compose`
  delegate to `hyperframes_compose`. `hyperframes lint` and `validate` must pass.
- `ffmpeg`: only for post-processing or simple video assembly; not enough for
  character acting by itself.

## Review Workflow

1. Run `character_rig_renderer` to produce or refresh the HyperFrames package.
   The browser preview is a QA/debug artifact only, not the render path.
2. Verify the renderer emitted a HyperFrames `workspace_path`, composition HTML,
   `asset_manifest`, and `edit_decisions.render_runtime: "hyperframes"` handoff.
3. Run `character_animation_reviewer` against rig, poses, timeline, and preview.
4. Render final video through `video_compose` using the renderer handoff or the
   approved Remotion/HyperFrames package. The deliverable path is
   `projects/<project-name>/renders/final.mp4`, matching the standard
   OpenMontage project convention.
5. Run standard `final_review`: ffprobe, frame sampling, visual spotcheck, audio
   spotcheck, promise preservation.

## Browser QA

When Playwright is available:

- open the preview,
- capture opening/middle/end frames,
- check for console errors,
- verify characters are visible,
- compare frame deltas to ensure motion exists.

When Playwright is unavailable, use static artifact checks and FFmpeg frame
sampling, and report the reduced confidence.

## Quality Bar

Do not present the output as complete when `character_qa_report.status` is
`revise` or `fail`.
