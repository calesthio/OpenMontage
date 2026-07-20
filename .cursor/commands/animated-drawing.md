# /animated-drawing — animate a supplied drawing with real mocap

Turn a user-supplied drawing/photo of a humanoid into a raster GIF/MP4 of that drawing moving (dance / walk / jump / wave), via Meta's open-source AnimatedDrawings. To *create* a vector doodle from scratch that draws itself, use `/ink-art`.

Read `skills/creative/animated-drawing.md`, then set up and run AnimatedDrawings on the user's drawing with the requested motion.

- Only for animating an *existing* humanoid drawing/photo (single figure, plain light background).
- Output is **raster** (original drawing warped) — no vector, no draw-on reveal.
- Prefer the turnkey bundled-character path; auto-rig needs Docker + ~670 MB models.
