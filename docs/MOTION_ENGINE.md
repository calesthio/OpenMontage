# OpenMontage — Motion Engine (P4)

**Component:** `lib/motion_engine.py` (existing) + `lib/motion_variety.py` (existing) + `lib/edit_decision_engine.py` (new)  
**Status:** P4 complete — designed, implemented, and tested  
**Date:** 2026-11-03  
**Cost:** $0 (FFmpeg filter strings only, no generation, no credits)

---

## 1. Architecture

The Motion Engine produces per-scene motion specifications that the Render Engine converts into FFmpeg `scale`+`crop` filter chains (time-varying zoom/pan via `eval=frame`).

Existing modules reused (not duplicated):

| Module | Role |
|---|---|
| `lib/motion_engine.py` | MotionSpec + TransitionSpec datatypes, `spec_for_scene()` factory, seeded RNG for reproducibility |
| `lib/motion_variety.py` | `lint_variation()` — enforces no identical consecutive moves |
| `lib/visual_director.py` | Shot variety, composition, lighting, character placement rules |
| `lib/edit_decision_engine.py` | EditDecision + EditDecisionSet + `to_edit_decisions_artifact()` + `validate_one_to_one()` |

---

## 2. MotionSpec

Each scene gets a `MotionSpec`:

| Field | Meaning |
|---|---|
| `scene_id` | Sentence/scene ID |
| `move_type` | `pan_zoom` \| `detail_crop` \| `parallax` \| `static` \| `chapter_card` |
| `easing` | `linear` \| `easein` \| `easeout` \| `easeinout` |
| `direction` | `in` (zoom in) \| `out` (zoom out) \| `left` \| `right` \| `up` \| `down` |
| `start_scale` / `end_scale` | Zoom scale range (1.0 = native) |
| `pan_x` / `pan_y` | Pan offset |
| `crop_box` | `[x0,y0,x1,y1]` in 0..1 for detail_crop |
| `parallax_layers` / `parallax_drift` | Layered parallax (only when depth justified) |

Motion is chosen per-scene based on content, composition, duration, and scene type — **never identical across all images**. `lint_variation()` guarantees no identical consecutive moves.

---

## 3. Visual Rhythm

Per `MASTER_VISUAL_STYLE_GUIDE.md` and `lib/visual_director.py`:

| Shot type | Usage |
|---|---|
| Wide / establishing | Scene opens, context |
| Medium | Dialogue, character scenes |
| Close-up | Emotion, detail |
| Extreme close-up | Scientific detail, text |
| Scientific cutaway | Diagrams, charts, data |
| Comparison | Side-by-side, before/after |
| Infographic | Stats, charts, KPIs |
| Visual metaphor | Abstract concept illustration |
| Hero character | Narrative anchor (appears when needed, NOT every frame) |

The hero character appears only where it serves the narrative — never in every shot. `VisualDirector` enforces shot-size variety (no 3+ identical consecutive sizes, no single size >60% of scenes).

---

## 4. Transitions

Supported transitions: `cut` (default), `dissolve`, `fade`, `wipe`. Configurable `transition_duration` (default 0.5s). Each `EditDecision` carries `transition_in` / `transition_out`.

---

## 5. Edit Decision Engine (`lib/edit_decision_engine.py`)

Builds one `EditDecision` per sentence:

| Field | Source |
|---|---|
| `scene_id` / `sentence_id` | From P3 sentence timeline |
| `image_asset_id` / `image_path` | From P2 image generation engine (one per sentence) |
| `audio_asset_id` / `audio_path` | From P3 audio engine (one per sentence) |
| `start_ms` / `end_ms` / `duration_ms` | From P3 audio alignment (actual audio timing) |
| `motion_type` / `camera_parameters` | From MotionEngine |
| `transition` / `transition_duration` | From VisualDirector |
| `visual_effects` | Derived from motion type + hero moment |
| `narrative_role` | `establish_context` \| `deliver_payload` \| ... |
| `hero_moment` | Whether hero character appears |

**Rule enforced:** ONE SENTENCE = ONE UNIQUE IMAGE = ONE UNIQUE AUDIO FRAGMENT. `validate_one_to_one()` checks unique asset IDs, chronological non-overlapping order, and no gaps.

`to_edit_decisions_artifact()` produces the render-ready `edit_decisions.json` compatible with `lib/render_integration.py`.

---

## 6. Files created (P4 motion)

| File | Purpose |
|---|---|
| `lib/edit_decision_engine.py` | Edit decision engine (decisions, artifact, validation) |

**No existing modules were rewritten.** Motion engine, motion variety, visual director, and render integration were reused as-is.

---

## 7. Readiness for render

Output of the motion engine feeds directly into `lib/render_engine.py` (FFmpeg-based render) or `lib/remotion-composer/` (Remotion, available but not wired — Explainer.tsx is scene-specific, not a generic edit-decision renderer).
