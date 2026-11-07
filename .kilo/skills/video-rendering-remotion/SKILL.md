---
name: video-rendering-remotion
description: Use when creating template-driven or data-driven video compositions, motion graphics, animated text, captions, title cards, branded layouts or batch rendering with Remotion and React.
---

# Remotion production workflow

- First confirm whether Remotion's license permits the intended commercial use; some use cases require a company license.
- Keep the composition deterministic: same input manifest and pinned dependencies should produce the same intended edit.
- Separate content data, scene components, styling, audio, subtitles and render configuration.
- Define schema validation for every video input JSON.
- Build a preview composition and render a short sample before batch rendering.
- Avoid loading untrusted remote URLs at render time; download approved assets and verify their rights records first.
- Use documented fonts and include font license records.
- Render to a temporary path, verify output with ffprobe and only then mark the job complete.
- Use concurrency limits based on available RAM/CPU/GPU; do not launch unbounded parallel renders.
- Record Remotion version, browser/runtime version, output profile and failures.
- Prefer FFmpeg-only rendering for simple cuts when it is sufficient; use Remotion when templating and animation justify the complexity.
