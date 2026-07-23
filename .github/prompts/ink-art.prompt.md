---
description: Hand-drawn ink-on-white doodle animation — a character that draws itself then walks/dances/waves, or a deadpan contraption explainer. Vector, deterministic, HyperFrames → MP4.
---

Read `skills/creative/ink-theater.md` and `ink-theater/README.md`, then build the hand-drawn ink animation the user asks for.

- Use the **Ink Theater** engine (`ink-theater/ink-theater.js`): variable-width ink strokes, seek-safe boil, closed-form spring eases, FABRIK IK, contraption grammar.
- For a **character that walks / dances / waves / jumps**, use the **Ink Puppet** mocap system: `InkPuppet.create` → `p.drawIn` (self-drawing reveal) → `InkPuppet.choreograph([{clip:'wave'},{clip:'twist'},…])` (names from `ink-theater/mocap/catalog.json`, 12 CMU-sourced moves). **Never hand-tune motion**; add moves via `node ink-theater/mocap/add-motion.mjs`.
- Captions = **HTML overlay `<div>`s** (HyperFrames doesn't apply webfonts to SVG `<text>`).
- Validate (`npx hyperframes lint` + `snapshot`) before rendering.
