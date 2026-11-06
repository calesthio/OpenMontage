# OpenMontage Stickman Rig — Architecture

Design for a **permanent, original SVG stickman researcher** built programmatically (no per-pose image generation). Inspired by the production principles of Stickman Video Director (scene ledger, meaningful motion, 2.5 s inactivity rule, content-addressed caching) but **not** a copy of its 3-pose atlas or renderer. Fits into the existing P0–P5 pipeline; does not replace Remotion/HyperFrames/FFmpeg.

## 1. Character identity (fixed)

- **Working name (internal)**: `om-researcher` (codename `RIG-1`). Final display name is an owner decision.
- **Role**: scientist/explorer narrator-proxy; appears in biology, space, ocean, evolution scenes.
- **Anatomy (proportion guide, not a rigid measurement)**:
  - Head diameter = 1.0 unit.
  - Torso (single stroke) = 1.6 units.
  - Upper arm = 0.7, forearm = 0.7 (total arm 1.4).
  - Thigh = 0.8, shin = 0.8 (total leg 1.6).
  - Total upright height ≈ 4.0–4.5 heads (matches B1 slender standard).
  - Hands: small 3-finger or simple oval; feet: small ovals.
- **Signature detail (firmennaya detal)**: a small round magnifying-glass lens on a short handle, attached at the right temple and resting over the right eye. Rendered as two simple primitives (circle + short line). This is the only element that distinguishes the character from a generic stick figure and must be present in every pose, including back views (lens flips or is shown as a faint circle).
- **Palette**: ink `#1f2320` outlines; one accent `#2a9d8f` (teal) on the lens rim and on props the character actively holds. Environments are colorful; the character stays monochrome + single accent so it reads against any scene.
- **Line weight**: uniform medium (2.5 px at 1280-wide), slightly irregular hand-drawn feel is achieved by a fixed small waviness, not by regenerating.

## 2. Rig structure (SVG)

The character is a tree of SVG `<g>` groups, each with its own transform and pivot. Parts are independent so they can be keyed independently.

```
character (root group: translate x,y; scale s)
├── head (pivot: neck base)
│   ├── skull (circle)
│   ├── face (expression layer: eyes, brows, mouth)
│   └── lens (signature detail, pivot: temple)
├── torso (line; pivot: hip)
├── arm L (pivot: shoulder)
│   ├── upper (line)
│   └── forearm (pivot: elbow)
│       ├── lower (line)
│       └── hand (pivot: wrist)
├── arm R (same)
├── leg L (pivot: hip)
│   ├── thigh (line)
│   └── shin (pivot: knee)
│       ├── lower (line)
│       └── foot (pivot: ankle)
└── leg R (same)
```

- Each joint group exposes `pivotX/pivotY` (local anchor) and accepts `angle`, `scaleX/scaleY`, `x/y` offset.
- Parent alpha multiplies child alpha (per B3 rule).
- Drawing order is back-to-front; a foreground layer (e.g., a held prop) can occlude the arm.

## 3. Coordinate system and units

- Rig space: normalized 0..100, origin at feet center, Y up. Output scale applied at render time (uniform, no stretch) — same convention as the stickman runtime's 1280 design plane.
- All angles in radians (matches B3).
- Poses are stored as joint-angle sets + optional part offsets, not as bitmaps.

## 4. Pose library

Named poses (each = joint angles + expression + optional prop attachment):

- `idle`, `walk_a`, `walk_b` (2-frame cycle), `run`
- `point_left`, `point_right`, `point_up`
- `hold_prop` (right hand forward, palm up)
- `examine` (head down, magnifying lens over prop)
- `write` (left hand holds surface, right hand moves)
- `think` (chin on hand, head tilted)
- `excited` (arms up, open mouth)
- `concerned` (arms slightly raised, furrowed brows)
- `wave`
- `sit` (for lab stool scenes)

Each pose declares `required_joints` and `mirrorable: bool`. Mirroring is a transform, not a new pose.

## 5. Expressions

Expression layer swaps eyes/brows/mouth primitives:

- `neutral`, `curious`, `surprised`, `determined`, `concerned`, `happy`, `frustrated`, `focused`.

Expressions are independent of pose; any pose × expression combination is valid. QA rejects a single frozen expression across a whole film (B common rule).

## 6. Actions with props

- Prop attachment points: `hand_r`, `hand_l`, `head_lens` (fixed), `torso_back`.
- A prop is an independent SVG group positioned in the parent's local space with its own keyframes.
- Continuity rule: a prop held in scene N must remain attached through cuts unless an explicit "transfer" event is logged in the scene ledger (matches B2 physical-contact rule).

## 7. Keyframes and animation

- Per-part keyframes: `{t, x?, y?, angle?, scaleX?, scaleY?, alpha?, progress?}` with smoothstep interpolation, clamped endpoints (same semantics as the stickman runtime).
- Key times are shot-relative (not parent-group-relative), per B3 rule.
- Genuine motion requires authored per-part keyframes; global zoom/pan/fade alone is explicitly **not** sufficient (B common rule). The rig must emit per-limb motion events in the scene ledger.
- Camera motion (existing `motion_engine`) stays separate and orthogonal.

## 8. Rendering path (no new renderer)

- **Static frames**: rasterize SVG → PNG via an optional adapter. Prefer existing tooling already in the stack (Playwright headless screenshot or Remotion's SVG support) rather than adding `@napi-rs/canvas`. If neither is available, fall back to a Python SVG→PNG library only after owner approval (dependency gate).
- **Animated**: feed rig keyframes into Remotion (React components) or HyperFrames (SVG + GSAP), which are the two approved composition runtimes. FFmpeg remains the fallback for still-led renders.
- **Output**: same MP4 contract (H.264/AAC, 1920×1080, 30 fps, yuv420p, faststart).

## 9. Continuity and validation

- `character_consistency_manager` extended with a `StickmanRigProfile` (proportions, signature detail id, allowed poses/expressions, accent color).
- Validation checks:
  - signature detail present in every pose (including back view).
  - limb count = 4, proportions within tolerance.
  - no two adjacent shots reuse identical (pose, expression, viewpoint) triple unless a motivated hold is logged.
  - prop ownership continuity across cuts.
- `final_qc` adds: rig consistency check (proportions + signature detail), meaningful per-limb motion (not just pixel change), no frozen limbs > 2.5 s.

## 10. Caching

- Rig state (pose id, expression id, joint angles, prop ids) is part of the shot cache key, so a pose change invalidates only affected shots, not the whole film. Mirrors the stickman runtime's content-addressed shot cache.

## 11. What we deliberately do NOT take

- The 3-pose atlas (demo reference, not a library).
- The Node/`@napi-rs/canvas` renderer as a production runtime.
- The B1 grid/paper palette as our default (our style is colorful scientific worlds; character stays monochrome).
- Gemini voice defaults (we keep Kokoro `af_heart` / factory voice policy).
- Any third-party marks or provider media.
