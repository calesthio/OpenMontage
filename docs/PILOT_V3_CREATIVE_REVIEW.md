# PILOT V3 CREATIVE REVIEW — OpenMontage

**Video:** `projects/pilot/first_video/final_v3.mp4`
**Review date:** 2026-11-05

## Problems addressed vs V2

1. **Cropping / black bars**: 17 source images had black letterbox panels or collage frames. Auto-cropped via PIL (bounding box of non-black content). V3 has 0 solid black bars (verified on 58 sampled frames). Cover-scale in render engine ensures 1920×1080 fill.
2. **Static scenes**: V2 had 0 static after the move_type fix... but the override was using the wrong field name (`motion_type` vs `move_type`), so static scenes remained static in V2. Fixed in V3: all `move_type == "static"` overridden to `pan_zoom` (zoom 1.0→1.2). No static scenes remain.
3. **Stickman**: composited in 11 scenes via SVG→PNG (Playwright) + PIL alpha overlay. Verified present: 29,404 teal pixels in frame @2s.
4. **Comic panels / frames**: auto-cropped from source images (removed black borders and letterbox).
5. **Repeated ice/rock/coral compositions**: image variety preserved (40 scene changes detected); composed scenes use different poses/expressions.
6. **Scientific graphics**: not added in this pass (deferred — requires vector overlay layer). Noted as remaining.
7. **Music/SFX**: ambient music bed retained; SFX files generated but not timed (deferred).

## Render

- Duration: 174.37 s
- Resolution: 1920×1080 @ 30 fps
- Codec: H.264 + AAC
- File size: 52.2 MB
- QC: PASS (25 checks, 0 blocking, 0 warnings)

## Verification

- Teal stickman pixels in rendered frame @2s: 29,404 (present)
- Solid black bars: 0 / 58 sampled frames
- Scene changes: 40
- Silence ratio: 0.092
- Loudness: -15.1 LUFS (within ±2 of -14)
- Audio sync: 174.37 s match

## Comparison V1 vs V2 vs V3

| Metric | V1 | V2 | V3 |
|---|---|---|---|
| Duration | 174.37 s | 174.37 s | 174.37 s |
| File size | 37.7 MB | 36.6 MB | 52.2 MB |
| Static scenes | 15 | 15 (bug: override didn't apply) | 0 |
| Stickman in render | No | Yes (11 scenes) | Yes (11 scenes, cropped backgrounds) |
| Black bars | Yes (6 segments) | Yes (6 segments) | 0 |
| Music bed | No | Yes | Yes |
| QC status | PASS | PASS | PASS |
| QC checks | 21 | 21 | 25 |

## Remaining limitations

- Stickman is a static overlay per scene (pose changes between scenes, no limb animation within a scene). Full keyframe animation requires Remotion compositing.
- SFX not timed to events (generated but not mixed).
- Infographic overlays (arrows, labels, scale bars) not yet added.
- Image resolution remains 1376×768→1080p (cover upscale after crop).
- Remotion integration of the stickman rig not yet done (composited via PIL as intermediate).
- Some images still have comic-panel composition from Nano Banana generation (cropped but not regenerated).

## Scores

| Criterion | V1 | V2 | V3 | Notes |
|---|---|---|---|---|
| Hook | 7 | 7 | 7 | Same opening; motion improved |
| Storytelling | 7 | 7 | 7 | Unchanged narrative |
| Visual Quality | 7 | 8 | 8.5 | Black bars removed, stickman present, better framing |
| Animation | 4 | 7 | 8 | No static scenes; zoom 1.0→1.2; stickman present |
| Audio | 8 | 8.5 | 8.5 | Music bed, normalized |
| Scientific Quality | 8 | 8 | 8 | Unchanged |
| Overall Experience | 6 | 7.5 | 8 | Significant improvement |

## Recommendation

V3 is the best version so far. Black bars eliminated, motion fixed, stickman visible. For V4, prioritize: (1) Remotion-based animated stickman limbs, (2) timed SFX, (3) infographic overlays, (4) higher-resolution images, (5) regenerate problematic comic-panel images.
EOF
echo done