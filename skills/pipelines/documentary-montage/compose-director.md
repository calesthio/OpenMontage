# Compose Director - Documentary Montage Pipeline

## When To Use

The timeline exists. Every cut has an in/out, transitions are
chosen, the music bed is locked. You now have to render the piece
and apply the register-smoothing pass (uniform crop + LUT + audio
mix) that makes a mixed-era corpus feel like one film.

The output is a single mp4 plus a `render_report` artifact.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["edit"]["edit_decisions"]` | Cuts, transitions, music, metadata hints |
| Prior artifact | `state.artifacts["assets"]["asset_manifest"]` | File paths, durations, providers |
| Tool | `video_compose` (Remotion-first + FFmpeg fallback) | Primary render engine |
| Tool | `audio_mixer` | Music fade, silence window, L-cuts |
| Tool (optional) | `color_grade` | Uniform LUT across mixed-era clips |
| Tool (optional) | `video_trimmer`, `video_stitch` | Lower-level helpers if needed |

## Mental Model

Most pipelines treat compose as a boring export step. For
documentary montage it is a creative step: the last pass where grade
and mix reconcile footage from radically different sources into one
piece.

Three things must happen here that cannot happen earlier:

1. **Uniform aspect and letterbox.** Pexels 1920x1080, Prelinger
   640x480 4:3, NASA 1280x720 all need to land on one canvas.
2. **Uniform color grade.** A single LUT across the whole timeline
   is what makes the 1962 home movie sit next to the 2023 kitchen
   without jumping out.
3. **Audio mix.** Music level, silence window, L-cut ambient
   carries, final fade — done in one pass with the timeline in hand.

## Process

### 0. Hard Requirement Check

Read `brief` and `edit_decisions.metadata` for any hard requirements.
If the brief said "no narration" and a narration track somehow
appeared in the edit, STOP and ask. Do not render over a contract
violation.

Also confirm that `edit_decisions.renderer_family` is locked to
`documentary-montage` and that the chosen render engine preserves that
decision. For this repo's governance model, `video_compose` is
Remotion-first on `operation="render"`, even for footage-led pieces.

- If Remotion is available, use the normal `render` path and keep the
  approved renderer family.
- If Remotion is unavailable, do NOT quietly drop to FFmpeg. Surface
  the engine change and get approval before using a lower-level
  FFmpeg-only path.

### 1. Resolve The Canvas

Read `brief.target_platform`:

| Target | Canvas | Letterbox |
|--------|--------|-----------|
| `social_short` (Instagram/TikTok) | 1080x1920 (9:16) | Top/bottom crop; center-anchor each clip |
| `youtube` / `generic` | 1920x1080 (16:9) | None; optionally 2.35:1 top/bottom bars for cinematic feel |
| `linkedin` | 1920x1080 (16:9) | None |

Every clip in the timeline must be scaled/cropped to this canvas.
For `social_short`, this usually means center-cropping 16:9 footage.
For `youtube` with the cinematic 2.35:1 bar treatment, pad 140px
black top and bottom on a 1920x1080 canvas.

Commit this in `render_report.metadata.canvas` and
`render_report.metadata.letterbox`.

### 2. Build The Concat Plan For `video_compose`

The edit artifact gives you a list of cuts with in/out, transitions,
and source asset_ids. Walk the asset_manifest to resolve each
asset_id to a real file path. Then build the render plan.

For a pipeline this simple, the cleanest path is:

```python
video_compose.execute({
    "operation": "render",
    "output_path": "projects/<name>/renders/final.mp4",
    "edit_decisions": edit_decisions_with_renderer_family,
    "asset_manifest": asset_manifest,
})
```

The exact field names come from the live `video_compose` schema at
render time — consult the tool's `agent_skills` if available before
writing the call. Do not invent parameters.

`edit_decisions_with_renderer_family` means the normal edit artifact
with `renderer_family = "documentary-montage"` preserved intact.

### 3. Apply Grade Via LUT, Not Per Clip

Read `edit_decisions.metadata.grade_profile`. Map it to a LUT file:

| Profile | LUT | Suits |
|---------|-----|-------|
| `warm_film_100` | vintage film warmth, slight lift | elegiac, dreamlike |
| `cool_archive_60` | cool highlights, crushed blacks | urgent, wry |
| `neutral_doc_20` | barely-there neutral balance | reverent |
| `bleach_bypass_80` | desaturated, high contrast | wry, documentary-harsh |

If the profile isn't in the styles library, use `neutral_doc_20` and
note it in `warnings`. Do not try to auto-grade — the LUT is the
whole point of the register-smoothing pass.

Apply the LUT at the composition level, not per clip. One LUT, one
timeline, one consistent look. This is what makes a 1962 Prelinger
clip and a 2023 Pexels clip feel like the same film.

### 4. Mix The Audio Once, In Compose

The edit artifact already decided volumes, fades, silence windows,
and L-cut sfx layers. Your job is to execute them faithfully:

- Music bed at `edit_decisions.audio.music.volume` (default 0.7).
- Fade in per `fade_in_seconds`, fade out per `fade_out_seconds`.
- Silence window = ducked to 0.0 for the window's duration, ramp
  back up with a 0.2s hold-off.
- L-cut SFX layers = mix at 0.5-0.7 volume, under music.
- No narration unless explicitly present in `edit_decisions.audio.narration`.

**Music is MANDATORY.** If the edit has no music entry, check the brief:

- `brief.metadata.music_plan.source == "none"` with an `opt_out_reason` →
  the user explicitly opted out. Render silent and note it in
  `render_report.warnings`.
- Anything else → STOP. This is a contract violation. Surface it to
  the user before rendering. A silent render on a music-mandatory brief
  is the loudest failure mode in this pipeline.

Do NOT add ambient noise "to fill the gap".

### 4b. Render The End-Tag Via Remotion

The end-tag is rendered **separately** from the FFmpeg body via
Remotion. This keeps the two render engines (FFmpeg for footage,
Remotion for typography) cleanly separated. The compositing method
depends on `brief.metadata.end_tag_plan.mode`.

Read `brief.metadata.end_tag_plan`:

```json
{
  "text": "WE BUILT BOTH WITH THE SAME HANDS.",
  "palette": "warm_ivory_on_black",
  "duration_seconds": 5.5,
  "render_engine": "remotion",
  "component": "EndTag",
  "mode": "overlay"
}
```

#### Path A — Overlay Mode (default)

The tag fades in over the final scenes of the body footage. This is
the default and produces a more cinematic result — the typography
appears on top of live footage rather than cutting to a black card.

**Execution:**

1. Compose the body via FFmpeg (cuts + LUT + music + silence window).
   Save as `projects/<name>/renders/body.mp4`. Note the body fps.
2. Compute `durationInFrames = round(duration_seconds × body_fps)`.
3. Render the end-tag with alpha via Remotion CLI:
   ```bash
   npx remotion render src/index.tsx EndTagOverlay \
     projects/<name>/renders/end_tag_overlay.mov \
     --codec=prores --prores-profile=4444 \
     --pixel-format=yuva444p10le --image-format=png \
     --props='{"text":"...","palette":"...","overlay":true,
               "fadeInSeconds":1.0,"holdSeconds":3.0,"fadeOutSeconds":1.5}'
   ```
   Use the `EndTagOverlay` composition with `overlay: true`. This
   produces a ProRes 4444 MOV with a real alpha channel
   (pix_fmt=yuva444p12le). Canvas must match body canvas.
4. Compute the overlay offset:
   - Read `edit_decisions.end_tag.offset_seconds` if present.
   - Otherwise auto-compute: `offset = body_duration - tag_duration`.
     The tag's fade-out should align with the body's closing fade-out.
5. Composite via FFmpeg overlay with `-itsoffset`:
   ```bash
   ffmpeg -y \
     -i body.mp4 \
     -itsoffset {offset} -i end_tag_overlay.mov \
     -filter_complex "[0:v][1:v]overlay=0:0:format=auto:eof_action=pass[v]" \
     -map "[v]" -map "0:a" \
     -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
     -c:a aac -b:a 192k \
     projects/<name>/renders/final.mp4
   ```
   `eof_action=pass` means the body video continues after the overlay
   ends. The overlay's own alpha handles the fade-in/hold/fade-out.

**Verification:** Extract a frame from the overlay region (e.g.
`offset + 2s`) and confirm text is visible over footage, not over
black. If the frame shows a black background behind the text, the
alpha channel was lost — re-render with `--image-format=png`.

#### Path B — Concat Mode

Classic tail-card: opaque black card appended after the body. Use
this only when `end_tag_plan.mode == "concat"`.

**Execution:**

1. Compose the body as above.
2. Render the end-tag as opaque MP4:
   ```bash
   npx remotion render src/index.tsx EndTag \
     projects/<name>/renders/end_tag.mp4 \
     --props='{"text":"...","palette":"...","durationInFrames":132}'
   ```
   (5.5s at 24fps = 132 frames). Canvas must match body canvas.
3. Concat body + end_tag:
   ```bash
   ffmpeg -f concat -safe 0 -i list.txt -c copy final.mp4
   ```
   Or re-encode if codecs don't match.

#### Common Rules (Both Modes)

**End-tag is MANDATORY.** The ONLY way to skip it is an explicit user
opt-out recorded as `end_tag_plan: null` with an `end_tag_opt_out_reason`.
If the brief has an end-tag plan but you skipped rendering it, that is
a contract violation. Stop and surface before finalizing.

Record in `render_report`:
- `end_tag_rendered: true | false`
- `end_tag_mode: "overlay" | "concat"`
- `end_tag_path: "projects/<name>/renders/end_tag_overlay.mov"` (or `.mp4` for concat)
- `end_tag_offset_seconds: <number>` (overlay mode only)
- `end_tag_text: "..."` (for audit trail)

If the brief says "no music" and the edit correctly has no music
entry AND `music_plan.source == "none"` with an opt-out reason, render
silent. Do NOT add ambient noise "to fill the gap".

### 5. Render At Documentary Spec

Recommended encoder settings for doc montage:

| Field | Value | Why |
|-------|-------|-----|
| Codec | `libx264` (H.264) | Universal, small |
| Pixel format | `yuv420p` | Universal compatibility |
| CRF | `18` | Visually lossless for final deliverables |
| FPS | `24` | Cinematic. Do NOT upconvert 24->30. |
| Audio codec | `aac` | Universal |
| Audio bitrate | `192k` | Music-bed friendly |

If the source clips are 30fps and the canvas is 24fps, let the render
pipeline drop frames evenly — don't blend. Motion interpolation on
mixed-source footage looks awful.

### 6. Post-Render Verification

After the render succeeds, actually probe the output file and check:

- **Duration.** Should match `sum(out - in for cut in cuts) + fade
  in/out` within ±0.5s.
- **Resolution.** Should match the canvas.
- **Audio presence.** If music was in the plan, the output must
  have an audio stream. If silence was planned, confirm.
- **First and last frame.** Open the file, seek to 0s and to
  duration-0.1s. The first frame should be a fade-in. The last
  frame should be (or be fading to) black.
- **Silence window.** Seek to the silence_window start. Audio level
  should drop visibly in the waveform.

Record verifications in `render_report.verification_notes`.

### 7. Emit The Render Report

```json
{
  "version": "1.0",
  "outputs": [
    {
      "path": "projects/<name>/renders/final.mp4",
      "format": "mp4",
      "codec": "h264",
      "audio_codec": "aac",
      "resolution": "1920x1080",
      "fps": 24,
      "duration_seconds": 89.8,
      "file_size_bytes": 18234112,
      "platform_target": "youtube"
    }
  ],
  "render_time_seconds": 42.3,
  "warnings": [],
  "verification_notes": [
    "Duration within +0.2s of planned",
    "First frame is black fade-in as specified",
    "Silence window 54-56s confirmed (music -60dB)",
    "Last frame fades to black at 89.0s"
  ],
  "render_grammar": "documentary-montage",
  "metadata": {
    "pipeline": "documentary-montage",
    "canvas": { "width": 1920, "height": 1080 },
    "letterbox": "2.35:1",
    "lut": "warm_film_100",
    "music_present": true
  }
}
```

### 8. Quality Gate

- Output file exists and plays.
- Duration within ±1s of `brief.duration_seconds` (body + end-tag inclusive).
- Resolution matches `target_platform` canvas.
- LUT was applied (or a warning logged).
- **Music is present** unless `brief.metadata.music_plan.source == "none"` with an explicit opt-out reason.
- **End-tag MP4 was rendered and concatenated** unless `brief.metadata.end_tag_plan` is null with an explicit opt-out reason. Last frame of final MP4 must be the end-tag card in that case.
- First and last frames verified.
- Silence window (if any) verified in the waveform.
- No narration unless brief-approved.
- `render_report.warnings` lists every substitution.
- `render_report.metadata.music_mixed = true` and `render_report.metadata.end_tag_rendered = true` (or explicit opt-out recorded).

## Common Pitfalls

- **Letting mixed-era clips render un-graded.** The piece will look
  like a PowerPoint slideshow of internet clips. The LUT is
  non-negotiable.
- **Upscaling to match the canvas instead of letterboxing.**
  Prelinger 640x480 upscaled to 1920x1080 looks pixelated and wrong.
  Center it with letterbox bars, or embrace the squared crop as a
  design choice.
- **Narration or ambient SFX added "to fill the gap".** Major
  change, needs user approval.
- **Per-clip color grading.** One LUT across the whole piece. Do
  not try to balance each clip individually — it takes 10x the time
  and makes the register LESS consistent, not more.
- **Quiet FFmpeg downgrade.** If Remotion is blocked and you route to
  FFmpeg without surfacing it, you've changed the approved render path.
  Stop and surface that downgrade before rendering.
- **Overriding edit decisions at render time.** If you find yourself
  adjusting volumes, fades, or trims in the render call, you're
  editing during compose. Go back to the edit stage, fix the
  decisions, re-emit the artifact, then re-render.
- **Skipping verification.** A render that "succeeded" but is
  actually silent, or fades wrong, or clips the last hero frame, is
  worse than a failure. Open the file.

## When The Render Fails

If `video_compose` returns an error:

1. Check the error category per the Decision Communication Contract
   (auth / provider / tool bug / plan quality).
2. If it's a path error, validate every asset_id → path resolution
   in the asset manifest. A single missing file fails the whole render.
3. If it's a codec error, the input clips may have exotic containers
   (Archive.org sometimes serves Matroska). Try running each input
   through `video_trimmer` first to normalize to mp4/h264.
4. If it's a memory or timeout error, split the render into halves
   with `video_stitch` at the end.
5. Surface to the user before swapping to a lower-fidelity path.
   This pipeline is footage-led; there is no generated-stills
   fallback.
