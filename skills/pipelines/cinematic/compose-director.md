# Compose Director - Cinematic Pipeline

## When To Use

Render the cinematic piece with careful attention to grade, audio dynamics, and frame treatment. This is not a generic export step.

## Runtime Routing (MANDATORY first step)

Read `edit_decisions.render_runtime`. Cinematic work routes to:

- **`render_runtime="remotion"`** — default for video-led trailers using `CinematicRenderer`. Keeps video clips, transitions, and ambient overlays in one React-based pass.
- **`render_runtime="hyperframes"`** — for kinetic title cards, HTML/GSAP-driven trailers, or launch-reel-style compositions where the visual grammar is HTML/CSS. See `skills/core/hyperframes.md`. `hyperframes check` must pass before render (it folds lint in).
- **`render_runtime="ffmpeg"`** — simple source-footage concat with no composition.

`delivery_promise.motion_required=true` means the locked runtime is a commitment. Silent swap to another runtime (including FFmpeg Ken Burns) is a CRITICAL governance violation. If the locked runtime fails, escalate per AGENT_GUIDE.md > "Escalate Blockers Explicitly."

**Pass `proposal_packet` to `video_compose.execute()`** so the tool's `runtime_swap_detected` check compares directly against `proposal_packet.production_plan.render_runtime`. Without it the swap check is skipped in-tool and only the reviewer skill catches the drift.

### Example `video_compose` call

`operation` is the one field the tool actually requires (`input_schema.required = ["operation"]`) — everything else is validated inside each operation handler, so a missing `edit_decisions` or `asset_manifest` fails late with a confusing error instead of a clean schema rejection. Use `operation="render"` for compose-director: per the tool's own schema description, `render` is "high-level — resolves asset IDs, auto-routes to Remotion for images/animations or FFmpeg for video-only. Preferred for compose-director." (`operation="compose"` is the low-level concat-only path — call it directly only for pure video pipelines like talking-head.)

This is the real call shape — `edit_decisions`, `asset_manifest`, and `proposal_packet` are the tool's actual fields, passed as full objects, not the invented `project_name`/`duration_seconds`/`scene_specifications` shape a prior run fabricated:

```json
{
  "tool": "video_compose",
  "inputs": {
    "operation": "render",
    "output_path": "renders/trailer_v1.mp4",
    "edit_decisions": {
      "render_runtime": "remotion",
      "cuts": [
        { "source": "asset_001", "start_seconds": 0, "end_seconds": 4.5 },
        { "source": "asset_002", "start_seconds": 0, "end_seconds": 3.0 }
      ],
      "subtitles": { "source": "renders/subs.ass" }
    },
    "asset_manifest": {
      "assets": [
        { "id": "asset_001", "path": "assets/video/hook_shot.mp4" },
        { "id": "asset_002", "path": "assets/video/reveal_shot.mp4" }
      ]
    },
    "proposal_packet": {
      "production_plan": { "render_runtime": "remotion" }
    },
    "profile": "youtube_landscape"
  }
}
```

`edit_decisions.render_runtime` here must match `proposal_packet.production_plan.render_runtime` (both `"remotion"` above) — that agreement is exactly what the tool's `runtime_swap_detected` check verifies.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit_decisions"]`, `state.artifacts["asset_manifest"]` | Edit plan and media assets |
| Tools | `video_compose`, `hyperframes_compose`, `audio_mixer`, `video_stitch`, `video_trimmer`, `color_grade`, `audio_enhance` | Render and finishing — `hyperframes_compose` is the delegate `video_compose` routes to (and can be called directly for `doctor`/lint checks) when `render_runtime="hyperframes"` |
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

## Common Pitfalls

- Flattening the audio so the piece loses dynamics.
- Applying letterbox to footage that needs every pixel.
- Letting grading or sharpening damage faces or text.
- Silently swapping a blocked Remotion render for a lower-fidelity still-image export.
