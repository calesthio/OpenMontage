# Stickman OpenMontage Integration Plan

Concrete extension plan. **Audit + architecture only; no implementation until separate approval.** Existing P0–P5 modules are reused, not rewritten. No second renderer. No Gemini/gflow changes. No spend.

## 0. Ground rules

- Do not rewrite `lib/visual_director.py`, `lib/motion_engine.py`, `lib/render_engine.py`, etc. Extend via small additions and optional new modules.
- New modules live under `lib/` and follow the existing dataclass + `to_dict()` convention.
- Every new non-trivial module gets a test under `tests/lib/`.
- Zero-cost gate (`lib/zero_cost_gate.py`) unchanged; rig generation is local SVG/Canvas only.
- License: any code adapted from the audited repo (MIT) must retain the MIT copyright notice; Lucide ISC and OFL font notices retained if those assets are reused. We prefer **original** artwork to avoid third-party marks.

## 1. New modules to create

| Module | Purpose |
|---|---|
| `lib/stickman_rig.py` | `StickmanRig` dataclass + SVG emitter: parts, joints, pivots, poses, expressions, signature detail. Pure data + string emit; no rendering. |
| `lib/stickman_pose_library.py` | Named poses (angles + expression + prop slots) + mirror helper. |
| `lib/stickman_continuity.py` | Prop ownership tracking + adjacent-shot repetition check + signature-detail presence check. |
| `lib/stickman_render_adapter.py` (optional, gated) | SVG → PNG frame rasterizer using an already-available tool (Playwright/Remotion). Returns `None` + reason if unavailable; never installs deps. |

## 2. Existing modules to extend (minimal, additive)

### 2.1 `lib/character_consistency_manager.py`

- Add `StickmanRigProfile` dataclass: `rig_id`, `character_id`, `proportions` (dict of unit lengths), `signature_detail_id`, `accent_color`, `allowed_poses`, `allowed_expressions`, `min_height_heads`, `max_height_heads`.
- Add `register_stickman_rig(profile)` and `validate_rig_pose(character_id, pose_id, expression_id, view, signature_detail_present)`.
- Add `RigConsistencyIssue` issue types: `missing_signature_detail`, `invalid_proportion`, `unknown_pose`, `unknown_expression`, `frozen_expression_run`.
- Do not change existing `CharacterAnatomy`/`validate_scene_against_character` behavior.

### 2.2 `lib/visual_director.py`

- Add optional `stickman_aware: bool` flag to `VisualDirector.__init__`.
- When enabled, add directives metadata: `rig_pose_hint`, `rig_expression_hint`, `prop_continuity_note`. These are hints only; poses are finalized in edit stage.
- Add a distant-section repetition check to the variety score: flag if the same (shot_size, character_placement, environment) triple repeats with only text swapped.
- Keep existing return shape; add fields, do not remove.

### 2.3 `lib/edit_decision_engine.py`

- Extend `EditDecision` with optional fields: `rig_pose_id`, `rig_expression_id`, `rig_view`, `prop_ids` (list), `rig_motion_events` (list of per-part keyframe dicts), `signature_detail_present` (bool).
- In `build_decisions`, accept optional `rig_plan: dict[str, dict]` keyed by sentence_id; populate the new fields when present, default to `None`/`[]`/`True` check.
- In `validate_one_to_one`, add (optional, non-blocking by default) check that adjacent decisions do not repeat `(rig_pose_id, rig_expression_id, rig_view)` unless a `motivated_hold` flag is set.
- In `to_edit_decisions_artifact`, include rig fields in each cut so the composer can render the rig.

### 2.4 `lib/motion_engine.py`

- Keep camera motion as-is.
- Add a separate `RigMotionSpec` concept? Prefer: store per-limb keyframes inside `EditDecision.rig_motion_events` (already a list of dicts). `MotionEngine` is not changed; rig motion is authored data, not camera motion.
- Add a helper `validate_rig_motion_events(events)` in `lib/stickman_rig.py` that checks key times increasing, angles finite, no global-only motion masquerading as limb motion.

### 2.5 `lib/production_timeline.py`

- `TimelineEntry` gains optional rig fields mirroring `EditDecision` (`rig_pose_id`, `rig_expression_id`, `rig_view`, `prop_ids`, `signature_detail_present`).
- Builder copies them from edit decisions when present; no new validation beyond what edit engine does.

### 2.6 `lib/render_engine.py`

- No core change. Add an optional hook: if a cut carries `rig_pose_id`/`rig_motion_events`, the render path may use a pre-rasterized rig frame path (`rig_frame_path`) if present; otherwise treat the cut's `source` image as authoritative (current behavior). This keeps FFmpeg path intact and makes rig rendering an upstream concern (Remotion/HyperFrames or the optional adapter).
- Do not add a second renderer.

### 2.7 `lib/preview_system.py`

- Add QC check `rig_motion_meaningful`: at least one per-limb motion event per shot of duration > 1.0 s, OR an explicit `motivated_hold` flag. Non-blocking warning by default.
- Add `rig_signature_detail`: check that all rig-bearing cuts have `signature_detail_present == True`. Blocking if any false.

### 2.8 `lib/final_qc.py`

- Add checks:
  - `rig_signature_detail_present`: every rig-bearing timeline entry has signature detail. Blocking.
  - `rig_proportion_consistency`: all rig-bearing entries reference the same rig profile (no mixed rigs). Blocking.
  - `rig_no_frozen_limbs`: reuse inactivity rule — no shot with rig motion events but zero events spanning > 2.5 s without `motivated_hold`. Warning/blocking per threshold config.
  - `rig_prop_continuity`: prop ids do not disappear between adjacent shots without a logged transfer. Warning.

## 3. Scene ledger extension

Reuse `production_manifest`/`edit_decisions` metadata; add optional fields (additive, schema-optional):

- `idea_to_communicate`
- `focal_subject`, `focal_action`, `focal_expression`
- `timed_picture_events` (list of `{t, event}`)
- `evidence_source`, `evidence_language`, `evidence_date`
- `caption_phrases`
- `sfx_event`
- `connection_to_next_shot`
- `motivated_hold` (bool)
- `prop_transfers` (list)

These mirror the B common scene ledger and are optional so existing artifacts stay valid.

## 4. Style integration

- Add a new style playbook `styles/stickman-researcher.yaml` (or extend an existing ink-sketch playbook) describing: monochrome character, teal accent, colorful scientific worlds, 2.5 s inactivity rule, meaningful per-limb motion. Validated by `schemas/styles/playbook.schema.json`.
- Add a director skill under `skills/pipelines/...` only if a dedicated pipeline is justified; otherwise reuse `character-animation` pipeline with the rig as the character backend.
- Do not create a second pipeline without owner approval.

## 5. Tests to add

| Test | Covers |
|---|---|
| `tests/lib/test_stickman_rig.py` | SVG emit, joint count, pivot presence, signature detail in every pose, mirror transform, keyframe validation. |
| `tests/lib/test_stickman_pose_library.py` | All named poses valid, no duplicate, mirrorable flag, required joints. |
| `tests/lib/test_stickman_continuity.py` | Prop ownership, adjacent repetition detection, signature detail presence. |
| `tests/lib/test_character_consistency_rig.py` | `register_stickman_rig`, `validate_rig_pose`, issue detection. |
| Extend `tests/lib/test_p4_engine.py` | Edit decisions carry rig fields; `validate_one_to_one` catches repeated pose without motivated_hold. |
| Extend `tests/lib/test_final_qc.py` | New rig checks PASS/FAIL paths. |

Tests use pure data/SVG strings; no network, no rendering, no spend. Optional adapter tests are skipped when no rasterizer is available (skip, not fail).

## 6. Implementation sequence (gated)

1. **S0 — Environment & license (no code)**: confirm no `@napi-rs/canvas` adoption; decide rasterizer (Playwright vs Remotion SVG). Record decision in `decision_log`. Keep MIT + Lucide + OFL notices.
2. **S1 — Rig core** (`stickman_rig.py`, `stickman_pose_library.py`) + tests. Pure data, zero cost.
3. **S2 — Continuity** (`stickman_continuity.py`) + character_consistency_manager extension + tests.
4. **S3 — Edit/timeline integration** (additive fields + validation) + tests.
5. **S4 — Visual director + scene ledger metadata** (additive) + tests.
6. **S5 — Preview + final QC rig checks** + tests.
7. **S6 — Style playbook + (optional) pipeline wiring** + owner review.
8. **S7 — Pilot** only after owner approval of master reference, voice, and (if any) cost.

Each step ends with: tests green, docs updated, checkpoint written, no commit unless explicitly requested.

## 7. What we explicitly do NOT do

- Do not install the stickman runtime as a second production renderer.
- Do not change `gflow-cli`, Nano Banana, or the generator path.
- Do not run Google Flow or spend credits.
- Do not copy the 3-pose atlas or bundled Gemini voice samples.
- Do not rewrite P0–P5 modules; extend only.
- Do not add dependencies without owner approval and a concrete need.

## 8. Open questions for the owner

1. Final display name for the researcher character.
2. Preferred signature detail if not the magnifying-glass lens (e.g., a small antenna tuft, a scarf, a notebook).
3. Accent color (proposed teal `#2a9d8f`).
4. Rasterizer choice for SVG frames: Playwright (already used for recordings) vs Remotion SVG vs a Python library (requires dependency approval).
5. Whether the rig ships as part of `character-animation` pipeline or needs a new pipeline manifest.
