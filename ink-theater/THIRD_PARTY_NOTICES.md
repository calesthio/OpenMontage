# Third-party notices — Ink Theater

Ink Theater bundles two third-party assets. Both are free for any use, including
commercial, subject only to attribution.

## Patrick Hand (handwriting font) — SIL Open Font License 1.1

`assets/patrickhand.ttf`

Copyright (c) 2010-2012 Patrick Wagesreiter (mail@patrickwagesreiter.at).
Licensed under the SIL Open Font License, Version 1.1. The OFL permits bundling,
embedding, and redistribution (including commercially); it only forbids selling
the font by itself and requires that this notice and the license text ship with
it. Full license: `assets/OFL.txt`.

## Motion-capture clips — CMU Graphics Lab Motion Capture Database

`mocap/clips/*.json`, bundled into `mocap/clips.js`

The 2D motion clips are derived (via `mocap/bvh2clip.mjs`) from BVH files in the
**CMU Graphics Lab Motion Capture Database** (http://mocap.cs.cmu.edu), obtained
through the `una-dinosauria/cmu-mocap` mirror. The CMU database is **free for all
uses** ("This data is free for use in research and commercial projects
worldwide"). Per-clip source trial IDs are recorded in `mocap/catalog.json`
(e.g. `walk` = CMU 02_01, `wave` = CMU 141_16).

No Meta / FAIR (AnimatedDrawings) mocap is bundled. The separate `/animated-drawing`
capability documents Meta's AnimatedDrawings tool, but this engine's clip library
is entirely CMU-sourced.
