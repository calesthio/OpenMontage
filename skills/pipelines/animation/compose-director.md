# Compose Director - Animation Pipeline

## When To Use

Render the animation with an emphasis on text sharpness, timing integrity, and consistent output cadence. For `image_animation` approach, this stage also includes building the composition JSON, sourcing music, running pre-render validation, and performing post-render self-review.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Timing plan and asset files |
| Tools | `video_compose`, `audio_mixer`, `video_stitch` | Final assembly |
| Tools | `composition_validator` | Pre-render validation (MANDATORY) |
| Tools | `audio_probe` | Music duration check |
| Playbook | Active style playbook | Render consistency |
| Reference | `remotion-composer/public/demo-props/mori-no-seishin.json` | Composition JSON format reference |
| Reference | `skills/core/remotion.md` | Remotion patterns, anime_scene type, critical constraints |

## Process

### 1. Ensure Assets Are in Remotion's Public Directory

**CRITICAL:** Remotion can only access files via `staticFile()`, which resolves from `remotion-composer/public/`. Generated images and music files MUST be copied or symlinked into this directory before rendering.

```
Project structure:
  projects/<name>/assets/images/*.png     ← where images were generated
  remotion-composer/public/<name>/*.png   ← where Remotion reads them

Required: Copy or symlink images AND music into public/<project-name>/
```

Image paths in the composition JSON are relative to `remotion-composer/public/`:
```json
"images": ["deep-ocean/scene1-a.png", "deep-ocean/scene1-b.png"]
"src": "deep-ocean/ambient-music.mp3"
```

**If you skip this step, the render will fail with missing file errors or produce black frames.**

### 2. Build the Composition JSON (image_animation approach)

For `anime_scene` compositions, build a JSON file at `remotion-composer/public/demo-props/<name>.json`.

**Required structure:**

```json
{
  "cuts": [
    {
      "id": "scene-1-name",
      "source": "",
      "in_seconds": 0,
      "out_seconds": 5,
      "type": "anime_scene",
      "images": ["<project>/<image-a>.png", "<project>/<image-b>.png"],
      "animation": "<camera-motion>",
      "particles": "<particle-type>",
      "particleColor": "#HEXCOLOR",
      "particleCount": 20,
      "particleIntensity": 0.5,
      "backgroundColor": "#0A0A1A",
      "vignette": true,
      "lightingFrom": "rgba(r,g,b,a)",
      "lightingTo": "transparent"
    }
  ],
  "overlays": [...],
  "audio": { "music": { "src": "<project>/music.mp3", "volume": 0.15, "fadeInSeconds": 2, "fadeOutSeconds": 3 } }
}
```

**Prop name reference (JSON field → AnimeScene prop):**

| JSON Field | Type | Values | Required |
|------------|------|--------|----------|
| `type` | string | `"anime_scene"` | YES |
| `images` | string[] | 1-4 image paths relative to `public/` | YES |
| `animation` | string | `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `ken-burns`, `drift-up`, `drift-down`, `parallax`, `static` | No (default: `ken-burns`) |
| `particles` | string | `fireflies`, `petals`, `sparkles`, `mist`, `light-rays` | No |
| `particleColor` | string | Hex color | No (default: `#FFE082`) |
| `particleCount` | number | 1-50 | No (default: 20) |
| `particleIntensity` | number | 0-1 | No (default: 0.6) |
| `backgroundColor` | string | Hex color for scene background | No (default: `#0A0A1A`) |
| `vignette` | boolean | Cinematic vignette overlay | No (default: true) |
| `lightingFrom` | string | Starting gradient color (`rgba(...)` or `transparent`) | No |
| `lightingTo` | string | Ending gradient color | No |

**References:** See `mori-no-seishin.json` (Ghibli forest) and `deep-ocean.json` (underwater bioluminescence) for complete working examples.

### 3. Source Music and Find Optimal Offset

Use `tools/audio/pixabay_music.py` to find royalty-free ambient music matching the mood.

**After downloading, run audio energy analysis (MANDATORY):**

```python
from tools.analysis.audio_energy import AudioEnergy
result = AudioEnergy().execute({
    "input_path": "path/to/music.mp3",
    "video_duration_seconds": 30,  # your video duration
})
data = result.data
print(f"Recommended offset: {data['recommended_offset_seconds']}s")
print(f"Reason: {data['offset_reason']}")
print(f"Needs loop: {data['needs_loop']}")
```

This tool:
1. **Finds the best section** — analyzes per-second loudness and finds the N-second window with highest average energy. Ambient music tracks often have quiet intros (10-30s) before the main melody kicks in.
2. **Recommends loop** — if the music from the offset is shorter than the video, it tells you to enable looping.

**Apply the offset in the composition JSON:**

```json
"audio": {
  "music": {
    "src": "project/music.mp3",
    "volume": 0.15,
    "fadeInSeconds": 2,
    "fadeOutSeconds": 3,
    "offsetSeconds": 55,
    "loop": false
  }
}
```

- `offsetSeconds` — start playback from this point in the track (skips quiet intro)
- `loop` — set to `true` if the remaining music is shorter than the video

**If the tool says `needs_loop: true`:** set `"loop": true` in the composition JSON. Remotion will loop the audio seamlessly with the volume fade resetting per loop.

### 4. Pre-Render Validation (MANDATORY — NO EXCEPTIONS)

Run `composition_validator` before every render:

```python
from tools.analysis.composition_validator import CompositionValidator
result = CompositionValidator().execute({
    "composition_path": "remotion-composer/public/demo-props/<name>.json",
    "assets_root": "remotion-composer/public",
})
# result.data["valid"] MUST be True before proceeding
```

This catches:
- Missing image/audio files that would cause black frames or render errors
- Invalid cut timings (out ≤ in)
- Audio longer than video duration

**If validation fails, fix the issue BEFORE rendering. Do not render an invalid composition.**

### 5. Preserve Motion Timing

Do not let export settings or careless composition change the perceived timing of holds, stagger, or scene transitions.

### 6. Protect Text And Diagram Sharpness

Animation often fails on export through soft text, muddy thin lines, or cramped mobile framing.

### 7. Render

```bash
cd remotion-composer
npx remotion render Explainer \
  --props="public/demo-props/<name>.json" \
  --output="<output-path>/final.mp4" \
  --codec=h264 --crf=18
```

**Note:** The composition name is `Explainer` (not `ExplainerVideo`). Do NOT specify `src/index.ts` as entry point — Remotion auto-discovers it.

### 8. Post-Render Self-Review (MANDATORY)

After rendering, extract mid-scene frames and visually inspect:

```bash
# Extract one frame from the middle of each scene
ffmpeg -y -i final.mp4 \
  -vf "select='eq(n\,75)+eq(n\,225)+eq(n\,375)+eq(n\,525)+eq(n\,675)+eq(n\,825)'" \
  -vsync vfr frames/scene_%02d.png
```

**Check each frame for:**
- [ ] Images are visible (not black/dark frames)
- [ ] Particles are rendering (sparkles, fireflies, etc. visible)
- [ ] Camera motion is evident (framing differs from static)
- [ ] Overlays display at correct moments with clean text
- [ ] Color palette is consistent across scenes
- [ ] Vignette creates cinematic depth

**Also verify the output file:**
```bash
ffprobe -v quiet -print_format json -show_format -show_streams final.mp4
```
- Duration within ±5% of target?
- Resolution matches 1920×1080?
- Audio stream present?

**If issues are found:** identify the cause (missing images, wrong timing, rendering glitch) and fix before presenting to user.

### 9. Use Render Metadata

Recommended metadata keys:

- `render_fps`
- `sharpness_checks`
- `safe_zone_checks`
- `variant_outputs`

## Common Pitfalls

- **Forgetting to copy assets to `remotion-composer/public/`** — the #1 cause of render failures. Images generate to `projects/<name>/assets/` but Remotion reads from `public/`.
- Soft or aliased text after rendering.
- Compression choices that damage diagrams.
- Scene cadence changing between preview and final.
- **Skipping `composition_validator`** — catches missing files, bad timings, audio mismatches before you waste render time.
- **Not extracting frames for self-review** — a rendered video is not "done" until frames are visually inspected. Black frames, missing particles, or invisible images are not always obvious from file size alone.
- **Using `durationInFrames` from `useVideoConfig()` for scene-level timing** — this returns the FULL composition duration, not the scene's Sequence duration. See `skills/core/remotion.md` Critical Constraints.
