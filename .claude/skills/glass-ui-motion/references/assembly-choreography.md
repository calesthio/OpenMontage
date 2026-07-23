# Assembly choreography

How UI elements assemble on screen. The goal is the "product coming together"
feeling of polished SaaS launch films: deliberate, weighted, never busy.

## Build order — semantic, not spatial

Assemble in the order a user *understands* the surface:

1. **Container** — the glass panel / window chrome scales-fades in first and
   establishes the stage.
2. **Chrome** — nav, header, sidebar: the frame of reference.
3. **Fields / structure** — form fields, table headers, card grids, in
   reading order (top-left → bottom-right for LTR products).
4. **Content** — values, rows, chart data populating the structure. Numbers
   may count up; charts draw in.
5. **Focus** — the one interaction the scene is about: cursor arrives, field
   focuses, button presses, toggle flips. At most one focus beat per scene.

Never assemble in random or purely aesthetic order — the build order IS the
narration's visual argument.

## Spring vocabulary

Pick **2–3 presets for the whole video** and reuse them; per-element bespoke
springs read as jitter. Solid starting set (Remotion `spring()`):

```tsx
// containers / panels — weighty, no overshoot
const settle  = { damping: 200, stiffness: 120, mass: 1 };
// fields / cards — light pop with a hint of overshoot
const pop     = { damping: 18,  stiffness: 160, mass: 0.9 };
// focus accents (button press, toggle) — snappy
const snap    = { damping: 14,  stiffness: 260, mass: 0.6 };
```

Element entrances combine 2 of: translateY (12–24px), scale (0.96→1),
opacity (0→1), blur (4px→0). Pick one combination per element *class* (all
fields enter the same way).

## Stagger math

- Sibling elements (fields in a form, cards in a grid): stagger start frames
  by **4–7 frames** (@30fps). Under 3 reads as simultaneous; over 10 reads as
  a slideshow.
- Grids: stagger by `row * cols + col` order (reading order), or radially
  from the focus element for emphasis.
- Between build-order groups (chrome → fields), leave a **6–10 frame breath**.

## Settle frames — computed, not eyeballed

The settle frame is where the element visually stops; it is also the SFX cue
frame. For a spring started at `from` with config `c`:

```tsx
import {measureSpring} from "remotion";
const settleFrame = from + measureSpring({fps, config: c}); // frames until rest
```

Compute settle frames in the props-generation step and write them into the cue
sheet — do not hand-tune numbers scattered through scene files.

## Camera and parallax restraint

- The "camera" (a wrapper transform) may do ONE slow move per scene: a 2–4%
  scale drift or a gentle pan. Never both, never fast.
- Parallax between background blobs and the glass panel: ≤ 8px of relative
  drift. It sells depth; more sells seasickness.
- No 3D card flips, no rotations beyond ±2°, no bounce loops. Polished SaaS
  is weighted and calm.

## Timing against narration

- Scene assembly should complete within the narration beat that introduces it
  (from the scene plan's assembly beats). If narration for the form runs 6s,
  the form finishes assembling by ~5s and holds.
- Hold every completed scene 12–18 frames before the cut — nothing may still
  be moving at a scene boundary.
- Count-up numbers and chart draws end 0.5–1s before the cut so the viewer
  reads the final value.
