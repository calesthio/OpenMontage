# Creator Video Compose Director

Render the final video from `edit_decisions` and `asset_manifest`.

Route by `edit_decisions.render_runtime`; do not silently switch runtime:

- `remotion`: use `video_compose` for the existing React scene stack, captions, title cards, and vertical creator videos.
- `hyperframes`: use the HyperFrames path when `render_runtime` was approved for HTML/GSAP kinetic motion.
- `ffmpeg`: use only when the approved plan is simple clip stitching or encoding.

If the approved `render_runtime` is unavailable, stop and surface a blocker. Any change requires a new `render_runtime_selection` decision. HyperFrames must be named in the blocker or decision whenever it was considered.
