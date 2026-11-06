# Stickman Rig v1 — Implementation

## Files created

- `lib/stickman_rig.py` — rig core: `RigProfile`, `RigFrame`, `Keyframe`, `RigMotionEvent`, forward kinematics, SVG emitter, validation helpers, content-addressed cache key.
- `lib/stickman_pose_library.py` — 11 parametric poses (idle, walking, running, pointing, explaining, thinking, surprised, examining, holding, looking_through_lens, interacting), mirror helper, pose→frame factory.
- `lib/stickman_continuity.py` — `StickmanContinuityChecker`: repeated-composition detection, missing signature detail, prop teleport.
- `lib/production_metrics.py` — operational metrics collector (no invented prices).

## Files extended (additive only)

- `lib/character_consistency_manager.py` — `StickmanRigProfile`, `RigConsistencyIssue`, `register_stickman_rig`, `validate_rig_pose`.
- `lib/visual_director.py` — `stickman_aware` flag, rig hints on directives, distant-section repetition check.
- `lib/edit_decision_engine.py` — rig fields on `EditDecision`, `rig_plan` input, adjacent rig-repetition check in `validate_one_to_one`.
- `lib/production_timeline.py` — rig fields on `TimelineEntry`, copied from edit decisions.
- `lib/render_engine.py` — `rig_overlay_path` awareness + warning when overlays not composited in FFmpeg path.
- `lib/preview_system.py` — `rig_signature_detail` and `rig_motion_meaningful` checks.
- `lib/final_qc.py` — `rig_signature_detail_present`, `rig_proportion_consistency`, `rig_no_frozen_limbs`, `rig_prop_continuity`; verdict updated to propagate only blocking NOT_RUN.

## Character

- Original scientific researcher "Researcher" (codename RIG-1).
- Signature detail: magnifying-glass lens (teal accent `#2a9d8f`) on the right temple.
- Monochrome ink body (`#1f2320`), 4.0–4.5 heads tall, slender, single-stroke limbs.
- 8 expressions: neutral, curious, surprised, determined, concerned, happy, frustrated, focused.
- 4 views: front, three_quarter, profile, back.
- 11 poses, all mirrorable, all carry the signature detail.

## Integration with existing pipeline

- Background image (one per sentence) remains the unique scientific illustration; the rig is a separate programmatic layer (`rig_overlay_path`/`rig_motion_events`), never replacing the background.
- Edit decisions carry rig fields through to timeline and render; FFmpeg path renders background + motion as before; rig overlay compositing is delegated to Remotion/HyperFrames (no second renderer).
- Cache keys include rig state (pose, expression, view, motion events) so only affected shots invalidate.

## Metrics

`lib/production_metrics.py` records image count, regenerations, sentence count, render duration, output size, output duration, production duration, and cost only when explicitly provided (never invented).

## Tests

See `docs/STICKMAN_RIG_TEST_REPORT.md`.

## License

No third-party code copied. Rig is original. MIT notice retained for the project. No Lucide/OFL assets reused in the rig (original primitives only).
