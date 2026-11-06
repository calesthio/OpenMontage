# PILOT V2 CREATIVE REVIEW — OpenMontage

**Video:** `projects/pilot/first_video/final_v2.mp4`
**Review date:** 2026-11-05

## Changes vs V1

1. **Stickman Rig-1 composited** into 11 scenes (every 4th scene) via PIL alpha-composite of rasterized SVG (Playwright). Teal accent pixels verified present in rendered frames (26k+ on S001). Poses: idle, explaining, holding, walking, thinking, looking_through_lens, running, surprised, interacting, pointing, examining. Expressions vary per scene.
2. **Motion improved**: all 15 formerly-static scenes changed to pan_zoom (zoom 1.0→1.15). Motion types now: pan_zoom (25), detail_crop (13), parallax (3). No static scenes remain.
3. **Sound design**: ambient documentary music bed (low-frequency drone, ducked under narration) added via ffmpeg amix + loudnorm. Narration normalized to -14 LUFS. SFX generated (chime, whoosh) but not mixed in this pass (timing deferred).
4. **Audio normalized** to -14 LUFS, true peak -2.0 dBTP.

## Render

- Duration: 174.37 s
- Resolution: 1920×1080 @ 30 fps
- Codec: H.264 + AAC
- File size: 36.6 MB
- QC: PASS (21 checks, 0 blocking, 0 warnings)

## Comparison V1 vs V2

| Metric | V1 | V2 |
|---|---|---|
| Duration | 174.37 s | 174.37 s |
| File size | 37.7 MB | 36.6 MB |
| Static scenes | 15 | 0 |
| Stickman in render | No (metadata only) | Yes (11 scenes, verified by pixel analysis) |
| Music bed | No | Yes (ambient drone) |
| QC status | PASS | PASS |
| True peak | -3.68 dBTP | -2.0 dBTP |

## Costs

- Monetary: $0
- Flow credits: 0 additional (no regeneration; all 41 images reused)
- New assets: 11 stickman PNG overlays (local SVG→PNG via Playwright), 1 ambient music WAV (local synthesis), 2 SFX WAVs

## Re-evaluation

| Criterion | V1 | V2 | Notes |
|---|---|---|---|
| Hook | 7 | 7 | Same opening; motion improved but still starts with slow push-in |
| Storytelling | 7 | 7 | Unchanged narrative |
| Visual Quality | 7 | 8 | Stickman adds character identity; composed frames verified |
| Animation | 4 | 7 | No static scenes; zoom/pan on all; stickman present (static pose per scene, not animated limbs) |
| Audio | 8 | 8.5 | Music bed added; narration still clear; loudness normalized |
| Scientific Quality | 8 | 8 | Unchanged |
| Overall Experience | 6 | 7.5 | Meaningful improvement; still lacks animated stickman limbs and SFX timing |

## QC improvements

Final QC extended with four new blocking checks:
- `missing_assets`: every edit decision image_path must exist on disk.
- `solid_color_frames`: sampled frames (1/5s) must not be near-solid (variance < 500); skipped for short test videos (< 10 sampled frames).
- `composition_repeats`: warns on exact (image, motion) duplicates.
- `timeline_mismatch`: timeline duration vs rendered duration drift must be <= 1.0 s.

New tests: `tests/lib/test_final_qc_v2.py` (5 passed). Existing P4/P5 regression tests still pass after the changes.

## Remaining limitations

- Stickman is a static overlay per scene (pose changes between scenes but no limb animation within a scene). Full keyframe animation of the rig requires Remotion compositing.
- SFX not timed to events (generated but not mixed).
- Infographic overlays (arrows, labels) not yet added.
- Image resolution remains 1376×768→1080p (cover upscale).

## Recommendation

V2 is a meaningful improvement over V1 (Animation +3, Visual +1, Audio +0.5, Overall +1.5). The stickman is now present and verified. For V3, prioritize: (1) Remotion-based animated stickman limbs, (2) timed SFX, (3) infographic overlays, (4) higher-resolution images.
EOF
echo done