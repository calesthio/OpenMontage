# Stickman Rig v1 — Test Report

## Test file

`tests/lib/test_stickman_rig.py` — 18 tests, all passing.

## Coverage

- Rig profile validation (proportions, signature detail).
- Pose library completeness (11 poses, all present).
- Pose→frame conversion carries signature detail; validates against profile.
- SVG emission contains joints, accent color, signature detail.
- Forward kinematics (head above hip).
- Pose mirroring swaps left/right.
- Keyframe validation (increasing times, supported fields, numeric values).
- Rig motion event validation.
- Character consistency manager rig registration and validation.
- Continuity: repeated composition detection, missing signature detail.
- Visual director stickman-aware hints + distant repetition.
- Edit decision engine rig fields + adjacent repetition detection.
- Production timeline copies rig fields.
- Final QC rig checks (signature, frozen limbs, prop continuity).
- Preview system rig checks.
- Production metrics collector.
- Real FFmpeg MP4 render with fake images + rig fields (status=rendered, non-empty file).

## Regression

- `tests/lib/test_p4_engine.py`: 3 passed.
- `tests/lib/test_p4_render.py`: 10 passed.
- `tests/lib/test_final_qc.py`: 8 passed.
- `tests/lib/test_audio_production_engine.py`: passed (part of 62-test run).
- `tests/lib/test_image_generation_engine.py`: passed.
- `tests/lib/test_image_uniqueness.py`: passed.
- `tests/lib/test_sentence_segmenter.py`: passed.

## Mock scale scenarios

The rig tests exercise 4/5/10/20-sentence equivalent decision sets. Full 30–45 and 100-sentence scale is covered by existing P4 render tests (10/50/250 sentences) which now also carry rig fields in the new test path. No real images generated; all use solid-color fake PNGs.

## Checks verified

- Character appearance preserved (signature detail present in all poses).
- Pose transitions validated via adjacent-repetition detection.
- Pivot points present in SVG (joint groups with transforms).
- Prop interaction tracked via continuity checker.
- Composition variety via visual director distant-section check.
- Timeline sync via production timeline builder.
- Recovery/caching: not re-tested separately (existing P4 cache tests cover content-addressed shot cache; rig state is part of cache key by design).
- Scene ledger: optional metadata fields added to edit decisions/timeline.
- Preview approval: existing checkpoint/preview system unchanged; rig checks added to preview QC.

## Limitations / not checked

- No Remotion/HyperFrames render of the rig layer (FFmpeg path only renders background); rig overlay compositing is a follow-up.
- No real image generation (zero-cost).
- No pilot video produced.
- SVG rasterization adapter not implemented (optional, gated).
