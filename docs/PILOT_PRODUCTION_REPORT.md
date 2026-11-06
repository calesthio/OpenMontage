# PILOT_PRODUCTION_REPORT.md — OpenMontage First Pilot

## Result

- **MP4 (final):** `projects/pilot/first_video/final.mp4`
- **Duration:** 174.37 s (2 min 54 s)
- **Resolution:** 1920×1080, 16:9
- **FPS:** 30
- **Video codec:** H.264 (libx264)
- **Audio codec:** AAC, 48 kHz, stereo
- **File size:** 37.7 MB (37,728,661 bytes)
- **QC status:** PASS (21 checks, 0 blocking failures, 0 warnings)

## Content

- Topic: speculative evolution / frozen alien ocean (Europa/Enceladus), based on `docs/openmontage/pilot/script.md` slice S001–S041.
- Sentences: 41, each with a unique prompt and image asset (ONE SENTENCE = ONE UNIQUE IMAGE).
- Unique images: 41 (Nano Banana 2.1 via gflow, 16:9).
- Audio: Kokoro-82M, voice `af_heart`, speed 1.0, normalized to -14 LUFS.
- Motion: per-scene camera motion via existing MotionEngine + RenderEngine (FFmpeg).
- Stickman: programmatic SVG rig (RIG-1) integrated as a separate layer concept; rig fields carried in edit decisions and timeline.

## Assets

- Script slice: `projects/pilot/first_video/script/pilot_script.md`
- Prompts: `projects/pilot/first_video/prompts/prompts.json` + per-sentence `.txt`
- Audio: `projects/pilot/first_video/audio/S001.wav` … `S041.wav`, `master_narration.wav`, `master_narration_norm.wav`
- Images: `projects/pilot/first_video/images/S001.jpg` … `S041.jpg` (41 files)
- Manifests: `slice.json`, `audio_manifest.json`, `image_manifest.json`, `sentence_timeline`, `edit_decisions`, `production_timeline`, `render_result`, `audio_mix` (n/a), `metrics.json`
- QC: `projects/pilot/first_video/qc/final_qc_report.json`
- Preview: `projects/pilot/first_video/technical_validation.mp4` (earlier validation render, retained)

## Business metrics

- Image count: 41
- Regenerations: 0 (all first-pass accepted)
- Render duration: ~4 min for final pass
- Flow credits: balance remained 50 throughout (image generation did not consume measurable credits in this account); reserve 5 credits untouched
- Monetary cost: $0 (no paid APIs/subscriptions/cloud)
- Production time: ~1 session (audio ~4 min, images ~10 min generation, render ~4 min)

## Limitations / next steps

- Stickman SVG layer is carried as metadata in edit decisions; full Remotion compositing of the rig layer is a follow-up (FFmpeg path renders background + motion only).
- Real image generation relied on gflow UI automation; profile-lock contention made generation slow/unreliable. All 41 images were ultimately obtained.
- No publication performed. Title/description/tags/thumbnail concept to be prepared separately with owner approval.
- Preview + contact sheet for owner review recommended before any publishing decision.
EOF
echo done