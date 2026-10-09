# BGM Montage Compose Director

## Execution

Read the approved brief, then call bgm_montage with operation=run,
project_dir=projects/<project-id>, the approved BGM path, theme, duration,
ratio, source provider, and usage mode. Pass reference_dir and
local_library_dir explicitly when they are not the project defaults.

The tool owns the following bounded sequence:

1. music structure analysis and audiomap.json;
2. pre-download event-snapped timeline.json;
3. source acquisition or approved-manifest loading;
4. material matching and source-interval assignment;
5. FFmpeg render with the BGM Montage edit plan;
6. full-decode, black/freeze/silence/crop/sequence checks and evidence frames.

Do not call a second renderer for the same run or silently rewrite its
render_runtime. Preserve the raw BGM artifacts and use the returned
OpenMontage canonical artifacts for checkpointing.

This route locks `render_runtime=ffmpeg` because BGM Montage performs its own
FFmpeg render. Remotion and the HyperFrames (`hyperframes`) runtime are
intentionally not invoked; if the
approved brief requests either runtime, stop and resolve the pipeline choice
instead of silently rerouting through `video_compose`.

## Review

Before presenting a completed render:

- confirm the canonical render_report has a real output path, duration,
  resolution, and QA checks;
- inspect the returned validation frames and visual-review files;
- if status is awaiting_agent_visual_review, perform the visual review and
  resume the exact run ID instead of starting a duplicate run;
- verify every selected media asset has provenance, license, or an explicit
  unresolved-rights warning;
- play the final MP4 and verify that beat cuts, framing, and audio are present.

The output is incomplete when either programmatic QA or the required visual
review is missing.
