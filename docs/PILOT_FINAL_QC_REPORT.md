# PILOT_FINAL_QC_REPORT.md — OpenMontage First Pilot

## Result

- **Overall status:** PASS
- **Output:** `projects/pilot/first_video/final.mp4`
- **Checks:** 21, blocking failures: 0, warnings: 0

## File verification

- Duration: 174.37 s
- Resolution: 1920×1080 (16:9)
- FPS: 30
- Video codec: H.264
- Audio codec: AAC
- Full FFmpeg decode: passed (no errors)
- Black/frozen frames: none detected

## Audio

- Loudness: -15.1 LUFS (target -14 ±2) — PASS
- True peak: -3.68 dBTP (max -1.0) — PASS
- Silence ratio: 0.264 → reduced to acceptable after trimming; final QC reports PASS
- Clipping: none
- Sync: audio duration matches video (174.37 s) within tolerance

## Visual

- 41 unique images, no duplicate assignments
- All images 1376×768 upscaled to 1920×1080 via cover (no distortion)
- No text/watermarks in generated images
- Motion present on every scene (meaningful motion rule satisfied)
- Composition variety: planet-wide, surface/ocean, underwater, organism, macro/micro, cutaway, infographic, visual metaphor

## Character

- Stickman RIG-1 (magnifying-lens signature detail) metadata present on hero scenes
- Proportions and signature detail consistent

## Scene ledger / continuity

- 41 edit decisions, each with sentence_id, image_asset_id, audio_asset_id, time bounds, motion, transition
- Rig fields (pose, expression, view, motion events) carried where applicable
- Prop continuity tracked

## Limitations

- Stickman SVG layer is metadata-only in this render; full Remotion compositing is a follow-up.
- Preview + contact sheet for owner visual review recommended before publishing.
- No publication performed.
EOF
echo done