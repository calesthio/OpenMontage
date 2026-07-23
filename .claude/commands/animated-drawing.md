---
description: Animate a SUPPLIED drawing/photo of a character with real motion capture (Meta AnimatedDrawings) → raster GIF/MP4 of that drawing moving. To CREATE a vector doodle from scratch, use /ink-art.
argument-hint: [path to drawing] [motion: dance|walk|jump|wave]
---

Read `skills/creative/animated-drawing.md`, then set up and run Meta's open-source **AnimatedDrawings** to animate the supplied drawing with the requested motion.

- Use this only when the user *has* a humanoid drawing/photo to animate. To create a vector doodle from scratch that draws itself → use `/ink-art` instead.
- Output is **raster** (the original drawing warped) — no vector, no draw-on reveal. Confirm the input is a single humanoid on a plain light background.
- Prefer the turnkey bundled-character path first; the auto-rig path needs Docker + ~670 MB models.

Drawing + motion: $ARGUMENTS
