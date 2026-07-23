# Mocap provenance & licensing

All bundled clips derive from the **CMU Graphics Lab Motion Capture Database**
(http://mocap.cs.cmu.edu), which is **free for all uses, research and commercial**.
BVH files are fetched from the `una-dinosauria/cmu-mocap` mirror; `clips.js` /
`clips/*.json` are 2D derivations produced by `bvh2clip.mjs`. Per-clip source trial
IDs live in `catalog.json` (e.g. `wave` = CMU 141_16, `shuffle` = CMU 77_29).
See `../THIRD_PARTY_NOTICES.md` for the full attribution.

## Add a motion (self-extending — no code changes)

```
node add-motion.mjs <name> <cmu-id|url|path> [category] "[description]"
# e.g.  node add-motion.mjs backflip 90_01 dance "a backflip"
```

This fetches the BVH, converts it (auto-mapping fair1 / CMU / Mixamo skeletons),
rebundles `clips.js`, and updates `catalog.json`. CMU has thousands of clips
(walk, run, dance, wave, jump, …). Prefer CMU for anything shipped — it keeps the
library license-clean. Different skeletons may need an alias added to the `ALIAS`
table in `bvh2clip.mjs`, and `--axis xy|zy` to pick the projection plane.
