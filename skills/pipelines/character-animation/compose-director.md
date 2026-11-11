# Compose Director - Character Animation Pipeline

## Goal

Render the approved character animation and prove it was reviewed.

## Runtime Routing

First read `edit_decisions.render_runtime`. It must match the runtime locked in
proposal unless a `render_runtime_selection` decision explicitly changed it.

- `remotion`: stage assets into `remotion-composer/public`, build composition
  JSON, render via `video_compose`.
- `hyperframes`: materialize a HyperFrames workspace and let `video_compose`
  delegate to `hyperframes_compose`. **HyperFrames gate (what
  `hyperframes_compose` actually runs):** a templated workspace (scaffolded from
  `edit_decisions`) goes `lint → validate → render`; a `validate` failure always
  blocks the render, but `lint` findings block it only with `strict: true` —
  otherwise they are logged under `steps.lint` and the render continues, so pass
  `strict: true` on the final render. An authored (atelier) workspace
  (`composition_mode: "atelier"`) goes `hyperframes check → render --strict`
  instead, and `check` must pass. `skip_contrast: true` is for iteration only,
  never for final delivery.
- `ffmpeg`: only for post-processing or simple video assembly; not enough for
  character acting by itself.

## Review Workflow

1. Run `character_rig_renderer` to produce or refresh the HyperFrames package.
   The browser preview is a QA/debug artifact only, not the render path.
2. Verify the renderer emitted its handoff: `hyperframes_workspace` (the
   workspace directory — the input is called `workspace_path`, the output key is
   not), `composition_path` (the composition HTML), `preview_path`,
   `asset_manifest`, and `edit_decisions`. Know what that package is today:
   - The renderer always writes `edit_decisions.render_runtime: "hyperframes"`
     and `metadata.proposal_render_runtime: "hyperframes"`, whatever the
     proposal locked, and adds no `metadata.delivery_promise`. When the proposal
     locked `remotion`, do not hand this `edit_decisions` to `video_compose` —
     use the edit stage's own `edit_decisions` and the approved Remotion package.
     When it locked `hyperframes`, copy the proposal's `delivery_promise` into
     `metadata` before rendering.
   - It draws one built-in placeholder figure per character id (body, head,
     eyes, mouth, two arms; only the colours differ) with a fixed
     bounce/head-turn/arm/blink loop. It reads only the character ids from
     `rig_plan` and the duration from `action_timeline`; it does not read
     `pose_library`, rig parts such as `wing_left` or `tail`, or the timed
     actions. Treat it as a motion/visibility smoke test, not as the acted
     character animation, and say so if it is all that rendered.
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
