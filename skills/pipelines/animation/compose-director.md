# Compose Director - Animation Pipeline

## When To Use

Render the animation with an emphasis on text sharpness, timing integrity, and consistent output cadence. For `image_animation` approach, this stage also includes building the composition JSON, sourcing music, running pre-render validation, and performing post-render self-review.

## Runtime Routing (MANDATORY first step)

Before any other work, read `edit_decisions.render_runtime`. It was locked at proposal and MUST NOT be changed silently. The rest of this skill assumes `render_runtime="remotion"` (the default for this pipeline). If the proposal locked a different runtime:

- **`render_runtime="hyperframes"`** — HTML/CSS/GSAP render. Do NOT follow the Remotion-specific sections below (public/ staging, Remotion composition JSON). Instead:
  1. Read `skills/core/hyperframes.md` for the full routing model.
  2. Read `.agents/skills/hyperframes/SKILL.md` and `.agents/skills/hyperframes-cli/SKILL.md` for authoring contract and CLI usage.
  3. Call `video_compose` with `edit_decisions.render_runtime="hyperframes"` — it delegates to `hyperframes_compose`, which owns workspace materialization under `projects/<name>/hyperframes/` and returns the MP4 path.
  4. **HyperFrames gate (what `hyperframes_compose` actually runs):** a templated workspace (scaffolded from `edit_decisions`) goes `lint → validate → render`; a `validate` failure always blocks the render, but `lint` findings block it only with `strict: true` — otherwise they are logged under `steps.lint` and the render continues, so pass `strict: true` on the final render. An authored (atelier) workspace (`composition_mode: "atelier"`) goes `hyperframes check → render --strict` instead, and `check` must pass. `skip_contrast: true` is for iteration only, never for final delivery.
- **`render_runtime="ffmpeg"`** — simple concat/trim with no composition. Call `video_compose` directly; it will not auto-upgrade to Remotion.
- **Runtime unavailable** — do NOT silently swap to a different engine. Surface the blocker to the user per AGENT_GUIDE.md > "Escalate Blockers Explicitly" and wait for approval (recorded as a `render_runtime_selection` decision in decision_log) before switching.

The post-render self-review (final_review) is identical across runtimes — same ffprobe probe, frame sampling, audio spotcheck, and promise preservation checks. `final_review.checks.promise_preservation.render_runtime_used` must equal the runtime that actually ran.

**Pass `proposal_packet` to `video_compose.execute()`** when you invoke it. That lets the tool directly compare the proposal-locked runtime against the runtime recorded in `edit_decisions` and flip `runtime_swap_detected=true` if they diverge. Without it the tool falls back to `edit_decisions.metadata.proposal_render_runtime` (the edit stage copies it there); only when both are missing is the check `skipped`, and the reviewer skill has to catch swaps via cross-artifact comparison instead.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Timing plan and asset files |
| Tools | `video_compose`, `audio_mixer`, `video_stitch` | Final assembly |
| Tools | `composition_validator` | Pre-render validation (MANDATORY) |
| Tools | `audio_probe` | Music duration check |
| Playbook | Active style playbook | Render consistency |
| Reference | `skills/core/remotion.md` | Remotion patterns, anime_scene type, critical constraints |

## Process

### 1. Reference Assets by Their Real Paths

Remotion reads files through `staticFile()`, which resolves from its public dir. You do not copy anything there yourself: `video_compose` (`operation: "render"`) copies every existing file named by `source`, `src`, `images`, `backgroundImage` or `backgroundVideo` into a per-render public dir and rewrites the reference. Give those keys the real paths, e.g. `projects/<name>/assets/images/scene1-a.png` (repo-relative or absolute). A path that is not an existing file is treated as relative to `remotion-composer/public/`.

**A path that exists nowhere renders as a missing file or a black frame.**

### 2. Build the Composition JSON (image_animation approach)

For `anime_scene` compositions, build a JSON file at `projects/<name>/artifacts/remotion_composition.json`. This is the Remotion composition object described in `skills/core/remotion.md` ("Flat props format"): it carries the Remotion-only fields (`type`, `images`, `particles`, Remotion `overlays`, `audio.music.src`) that the closed `edit_decisions` schema rejects. The canonical `edit_decisions` artifact is not modified — it keeps schema fields only.

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
      "images": ["projects/<project>/assets/images/<image-a>.png", "projects/<project>/assets/images/<image-b>.png"],
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
  "audio": { "music": { "src": "projects/<project>/assets/music/music.mp3", "volume": 0.15, "fadeInSeconds": 2, "fadeOutSeconds": 3 } }
}
```

**Prop name reference (JSON field → AnimeScene prop):**

| JSON Field | Type | Values | Required |
|------------|------|--------|----------|
| `type` | string | `"anime_scene"` | YES |
| `images` | string[] | 1-4 image paths (real file paths; see section 1) | YES |
| `animation` | string | `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `ken-burns`, `drift-up`, `drift-down`, `parallax`, `static` | No (default: `ken-burns`) |
| `particles` | string | `fireflies`, `petals`, `sparkles`, `mist`, `light-rays` | No |
| `particleColor` | string | Hex color | No (default: `#FFE082`) |
| `particleCount` | number | 1-50 | No (default: 20) |
| `particleIntensity` | number | 0-1 | No (default: 0.6) |
| `backgroundColor` | string | Hex color for scene background | No (default: `#0A0A1A`) |
| `vignette` | boolean | Cinematic vignette overlay | No (default: true) |
| `lightingFrom` | string | Starting gradient color (`rgba(...)` or `transparent`) | No |
| `lightingTo` | string | Ending gradient color | No |

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

**Music under narration.** The `Explainer` composition ducks `audio.music` only when it carries `"ducking"` (`true`, or `{"duckedGain": 0.35, "attackSeconds": 0.15, "releaseSeconds": 0.4, "mergeGapSeconds": 0.6}` — `remotion-composer/src/lib/ducking.ts`), using the word `captions` for speech timing. Follow `edit_decisions.metadata.audio_mix_plan`:

- `composition` — add `"ducking": true` to the `audio.music` block above, at its normal bed `volume` (e.g. 0.3), and keep the word `captions` in the composition JSON. Without captions this is only a constant lower level; use `premix` instead.

- `premix` — run `audio_mixer` with `operation: "full_mix"`: each narration take as a `role: "speech"` track with its `start_seconds`, the music as a `role: "music"` track, `ducking: {"enabled": true, "music_volume_during_speech": 0.15}`, `target_duration` set to the video length, `normalize: true`. Put the mixed file in the composition JSON as `audio.narration.src` (volume 1) and leave `audio.music` out, so the bed is not played twice. `audio_mixer` has no in-point or loop option (`target_duration` only pads with silence or trims), so apply the recommended offset — and any looping — to the music file with FFmpeg before mixing (e.g. `ffmpeg -ss <offset> -i music.mp3 music_from_offset.wav`).
- `flat` (or a music-only piece) — keep the `audio.music` block above with `volume` at 0.08–0.12 when narration plays over it.

### 4. Pre-Render Validation (MANDATORY — NO EXCEPTIONS)

Run `composition_validator` before every render:

```python
from tools.analysis.composition_validator import CompositionValidator
result = CompositionValidator().execute({
    "composition_path": "projects/<name>/artifacts/remotion_composition.json",
    "assets_root": "remotion-composer/public",
})
# result.data["valid"] MUST be True before proceeding
```

This catches:
- Missing files named by `cuts[].source`, `cuts[].backgroundImage`, `audio.narration.src`, and `audio.music.src`
- Invalid cut timings (out ≤ in)
- Narration longer than the video (music shorter than the video is only a warning)

It does **not** check `anime_scene` images: those cuts carry `"source": ""` and list their files in `images[]`, which the validator never reads. Before rendering, confirm every `images[]` path exists yourself (e.g. a short loop over the composition JSON with `Path(...).exists()`) — a missing image renders as a black frame, not an error.

**If validation fails, fix the issue BEFORE rendering. Do not render an invalid composition.**

### 5. Preserve Motion Timing

Do not let export settings or careless composition change the perceived timing of holds, stagger, or scene transitions.

### 6. Protect Text And Diagram Sharpness

Animation often fails on export through soft text, muddy thin lines, or cramped mobile framing.

### 7. Render

Do not shell out to `npx remotion render`: call `video_compose` (`skills/core/remotion.md`, "Render Invocation"). It stages the media, runs the render and returns the `final_review`.

```
{
  "operation": "render",
  "edit_decisions": <the remotion_composition.json object from section 2>,
  "asset_manifest": <asset_manifest artifact>,
  "proposal_packet": <proposal_packet artifact>,
  "scene_plan": <scene_plan.scenes — the list>,
  "profile": "youtube_landscape",
  "output_path": "projects/<name>/renders/final.mp4",
  "narration_transcript_path": "<word-level transcript JSON from transcriber>",
  "script_text": "<the narration script>"
}
```

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

- **Naming a file that does not exist** — the #1 cause of render failures. `video_compose` stages only files that exist at the path given (section 1).
- Soft or aliased text after rendering.
- Compression choices that damage diagrams.
- Scene cadence changing between preview and final.
- **Skipping `composition_validator`** — catches missing `source`/`backgroundImage`/audio files, bad timings, and narration overrun before you waste render time. It does not look at `images[]`, so check `anime_scene` image paths yourself.
- **Not extracting frames for self-review** — a rendered video is not "done" until frames are visually inspected. Black frames, missing particles, or invisible images are not always obvious from file size alone.
- **Using `durationInFrames` from `useVideoConfig()` for scene-level timing** — this returns the FULL composition duration, not the scene's Sequence duration. See `skills/core/remotion.md` Critical Constraints.
