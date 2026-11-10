# Compose Director — Topic Tutorial Pipeline

## When to Use

You are the **Compose Director** for the `topic-tutorial` pipeline. You render the final video composition using Remotion or HyperFrames and produce `artifacts/render_report.json` and `reports/render_manifest.json`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Tool | `video_compose` / `remotion` | Composition rendering |
| Artifact | `artifacts/edit_decisions.json` | Cut timeline & props |
| Schema | `schemas/artifacts/render_report.schema.json` | Report validation |

## Execution & Runtime Routing

1. Route composition by the approved `render_runtime` (`remotion` or `hyperframes`).
2. Build Remotion / HyperFrames composition inputs according to the selected runtime.
3. Render master video at 1080p@30fps (or opt-in 4K profile).
4. Verify output video with `ffprobe` (codec: h264, resolution: 1920x1080, fps: 30, audio: aac).
5. Save `artifacts/render_report.json`.
