# Edit Director — Product-Motion Pipeline

## When to Use

Sixth stage (auto-proceeds). Replicas and audio approved. You lock the
timing: scene sequence, narration alignment, the SFX cue sheet, and the
`bespoke` block that routes the atelier render.

## Process

1. **Timing map**: order scenes per the scene plan; set each scene's
   `durationInFrames` from its narration segment's real audio duration
   (ffprobe the generated files — never the estimate) + the 12-18 frame hold.
   Nothing may still be moving at a cut.
2. **Compute settle frames** for every choreographed element
   (`measureSpring` per `references/assembly-choreography.md`) and derive the
   **SFX cue sheet** per `references/sfx-cues.md`: first/last-sibling rule,
   density cap ~1 per 0.7s, focus beat always cues. Write the cue sheet into
   the atelier `props.json` (`sfx_cues[]` with scene_id/element/frame/
   asset_id/volume). Cues reference only asset_manifest sfx ids.
3. **Audio plan**: narration + music stay on the post-mix path — build
   `edit_decisions.audio` (narration segments with start times, music with
   fade/loop and the playbook volume). SFX are in-composition and do NOT go
   into `audio.sfx[]` (that field is the post-mix fallback only — using both
   double-fires every cue).
4. **The bespoke block** (routes `video_compose._render_via_atelier`):

   ```json
   "composition_mode": "atelier",
   "render_runtime": "<carried from proposal_packet — unchanged>",
   "bespoke": {
     "entry": "projects/<id>/src/index.ts",
     "composition_id": "<CompositionId>",
     "props_path": "projects/<id>/artifacts/props.json",
     "public_dir": "projects/<id>/assets",
     "art_direction": "projects/<id>/artifacts/art-direction.md"
   }
   ```

   `render_runtime` is carried from `proposal_packet` **unchanged** — if the
   proposal locked `hyperframes`, the bespoke path is the HyperFrames
   equivalent and this block adapts per `skills/core/hyperframes.md`; a
   silent swap either direction is a CRITICAL violation.
5. Validate `edit_decisions`, self-review (manifest review_focus), checkpoint
   `completed` (no human gate) — but surface the timing map in your progress
   note so the board shows it.
