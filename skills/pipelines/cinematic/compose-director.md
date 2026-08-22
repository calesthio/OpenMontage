# Compose Director - Cinematic Pipeline

## When To Use

Render the cinematic piece with careful attention to grade, audio dynamics, and frame treatment. This is not a generic export step.

## Runtime Routing (MANDATORY first step)

Read `edit_decisions.render_runtime`. Cinematic work routes to:

- **`render_runtime="remotion"`** — default for video-led trailers using `CinematicRenderer`. Keeps video clips, transitions, and ambient overlays in one React-based pass.
- **`render_runtime="hyperframes"`** — for kinetic title cards, HTML/GSAP-driven trailers, launch-reel-style compositions, or explicit Three.js world fly-throughs. See `skills/core/hyperframes.md`. `hyperframes check` must pass before render.
- **`render_runtime="ffmpeg"`** — simple source-footage concat with no composition.

For a Blender world film, FFmpeg is the approved packager for the numbered
Blender image sequence and audio. It must not synthesize camera motion or replace
missing Blender frames with pan/zoom effects.

`delivery_promise.motion_required=true` means the locked runtime is a commitment. Silent swap to another runtime (including FFmpeg Ken Burns) is a CRITICAL governance violation. If the locked runtime fails, escalate per AGENT_GUIDE.md > "Escalate Blockers Explicitly."

**Pass `proposal_packet` to `video_compose.execute()`** so the tool's `runtime_swap_detected` check compares directly against `proposal_packet.production_plan.render_runtime`. Without it the swap check is skipped in-tool and only the reviewer skill catches the drift.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Edit plan and media assets |
| Tools | `video_compose`, `audio_mixer`, `video_stitch`, `video_trimmer`, `color_grade`, `audio_enhance` | Render and finishing |
| Playbook | Active style playbook | Finish consistency |

## Process

### 0. Check Hard Requirements Before Rendering

If the approved brief or scene plan makes motion a hard requirement, verify that the render path still preserves that promise.

- If Remotion is required and unavailable or failing, stop and bubble the issue to the user immediately.
- Do not switch to an FFmpeg-only still-image fallback for a motion-led trailer, teaser, or agent video.
- Do not convert the piece into an animatic unless the user explicitly approves that downgrade.
- If the render engine changes materially, tell the user before rendering and explain why.

**Mandatory Remotion preflight (run before every render when the scene plan includes any Remotion scene type — title cards, stat cards, anime/hero_title, end-tag, overlays):**

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
info = registry.get('video_compose').get_info()
print('Render engines:', info.get('render_engines'))
print('Remotion note:', info.get('remotion_note'))
"
```

If Remotion is not in the available render engines, stop and report to the user per the Decision Communication Contract. Do not substitute a reduced-fidelity render path without approval.

### 1. Use Frame Treatment Deliberately

Only use letterbox, 24fps intent, or heavy grading if they help the piece. Do not apply them because the pipeline name says cinematic.

### 2. Preserve Audio Dynamics

The mix should allow:

- quiet moments,
- impact moments,
- clear dialogue or narration,
- controlled music swells.

### 3. Verify The Final Mood

Check:

- opening frame,
- reveal beat,
- final landing,
- subtitle readability where relevant.

### 4. Use Render Metadata

Recommended metadata keys:

- `frame_treatment`
- `grade_profile`
- `mix_notes`
- `variant_outputs`

### 5. State The Frame Rate When It Is Not 30

The FFmpeg compose path normalizes every segment to one frame rate, because
concat with `-c copy` requires a consistent fps across segments. That rate
defaults to **30**, so say otherwise when the footage is not 30fps:

```json
"metadata": {
  "compose_target": {"width": 832, "height": 480, "fit": "pad", "fps": 64}
}
```

(or pass `fps` directly to `video_compose.execute()`, which takes precedence).

Getting this wrong is quiet rather than loud. Interpolated 64fps footage
composed at 30 is decimated back to half its frames -- the smoothness that was
just paid for is discarded. Generative 16fps footage composed at 30 is padded by
uneven frame duplication at a 1.875 ratio, which reads as judder rather than as
a wrong setting.

### 6. Asset Paths Resolve Against The Project Directory

`asset_manifest` asset paths are, per the schema, relative to the project
directory -- `assets/video/shot1.mp4`, not a repo-relative or absolute path.
Cut sources are looked up first relative to the process working directory and
then relative to the project directory inferred from `output_path`, so both
conventions work. If a source cannot be found the error lists every base that
was tried; read it before assuming the file is missing.

## Common Pitfalls

- Composing non-30fps footage without setting `compose_target.fps` -- see step 5.
- Flattening the audio so the piece loses dynamics.
- Applying letterbox to footage that needs every pixel.
- Letting grading or sharpening damage faces or text.
- Silently swapping a blocked Remotion render for a lower-fidelity still-image export.
