# Compose Director - Business Documentary Pipeline

## When To Use

Stage 10 of 12. You assemble the film: footage, narration, diagrams, music and
subtitles into one rendered file, and record a `render_report` a reviewer can
verify.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `alignment_report`, `asset_manifest`, `scene_plan`, `narration_manifest` | Everything above |
| Schema | `schemas/artifacts/render_report.schema.json` | Output validation |
| Registry | `video_compose` (required), `audio_mixer`, `subtitle_gen`, `diagram_gen`, `video_trimmer`, `video_stitch` (optional) | Assembly |

## Process

### 1. Confirm the runtimes that are actually available

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
print(registry._tools['video_compose'].get_info().get('render_engines'))
"
```

**Present both composition runtimes** (AGENT_GUIDE.md → "Present Both
Composition Runtimes (HARD RULE)") whenever more than one is available on this
machine:

| Runtime | Best at | Tradeoff here |
|---------|---------|---------------|
| **ffmpeg** | deterministic cuts, trims, concat, subtitle burn | least expressive; no kinetic type or spring motion |
| **HyperFrames** | kinetic typography, charts/diagram scenes, motion-led promos | needs Node ≥ 22 + ffmpeg; rendered through `npx hyperframes` |
| **Remotion** | React scene catalog, spring physics, word-level captions | needs `remotion-composer/node_modules`; slowest to iterate |

Present each with a one-line plain-language tradeoff and a recommendation tied
to the brief, then record a `render_runtime_selection` `decision_log` entry
(`category: "render_runtime_selection"`) whose `options_considered` lists every
available runtime plus any unavailable one
(`rejected_because: "runtime not available on this machine"`). Silent
defaulting is a CRITICAL governance violation.

**HyperFrames note:** when HyperFrames is unavailable on this machine, say so
out loud ("HyperFrames isn't installed on this machine; I'm proceeding with
ffmpeg. Install HyperFrames if you want the alternative.") and record it as
rejected — never omit it from the shortlist.

### 2. Never swap the locked runtime at compose time

If the locked runtime is unavailable or fails, surface a structured blocker:
what was attempted, what failed, whether it is auth/provider/tool/quality,
the options, and your recommendation. Wait for approval. A silent swap from a
motion-led promise to a still-led Ken Burns version is forbidden.

### 3. Build a continuous timeline

- The timeline must cover the full narration duration: no gaps, no unintended
  overlaps, no scene without an asset.
- Every cut records its asset, in/out and the reason.
- Transitions stay within a small vocabulary.

### 4. Diagrams

Render only diagram slots the storyboard justified. Every diagram carries its
title, units and source reference. A decorative animation is a review finding.

### 5. Audio

- Narration first; music ducks under it.
- Verify no clipping and that speech level is adequate.
- If no legal music track is available, silence is allowed **only** when the
  brief recorded that decision. Never substitute a track with unknown license.

### 6. Subtitles

Generate from the narration manifest's timestamps. Verify they stay inside
frame, do not cover critical graphics, and are readable at mobile size.

### 7. Verify the output on disk

`ffprobe` the file: container, duration, resolution, FPS, video and audio
streams, codecs. Record measured values in `render_report.outputs` and
`metadata`. A report written without probing the file is a defect.

### 8. Quality gate

- Schema-valid `render_report`.
- Output exists and passes ffprobe validation.
- `metadata.render_runtime` equals the locked runtime.
- Timeline covers narration; every scene has an asset.
- Music/voice levels verified; subtitles generated from measured timestamps.

## Common Pitfalls

- Burning subtitles from estimated timings.
- Rendering before the narration manifest exists.
- Adding a music bed to hide thin pacing.
- Reporting a render that failed to write a file.

---

## Checkpoint Note

`compose` is auto-approved (`human_approval_default: false`): write the
checkpoint, self-review against `skills/meta/reviewer.md`, and continue to QA.
