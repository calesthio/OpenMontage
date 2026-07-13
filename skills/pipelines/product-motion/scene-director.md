# Scene Director — Product-Motion Pipeline

## When to Use

Fourth stage. Script approved. You turn each script section into a concrete
scene spec: which screen, which elements assemble in what order, on what
beats, with what SFX intents.

## Prerequisites

Read `.agents/skills/glass-ui-motion/SKILL.md` and its
`references/assembly-choreography.md` — build-order semantics, stagger math,
and settle-frame rules live there. Bring `design_system` and `ui_inventory`
into context; scenes reference them constantly.

## Process

1. **One scene per flagship surface** (plus open/close). Each scene carries:
   - `screen_id` from `ui_inventory` (the manifest review checks this),
   - the **element build order** — the scene's `ui_elements` in semantic
     assembly order (container → chrome → fields → content → focus),
   - **assembly beats**: which narration phrase each element group lands on,
   - **SFX intents** per the cue taxonomy (whoosh/tick/click/shimmer/pop) —
     intents only; frames are computed at edit,
   - duration from the section's narration length + a 12-18 frame hold.
2. **Required assets per scene** must list the repo `source_files` to
   replicate (from the ui_inventory screen/components) — this is the link the
   asset director builds from, and the manifest's success criterion.
3. **Glass staging plan**: how many panels, what sits on glass vs. on the
   ambient background, one camera move max per scene — per the
   glass-ui-motion recipes, themed by `design_system.tokens.glass`.
4. **Density discipline**: information_density and motion_intensity from the
   proposal's `taste_profile` cap simultaneous motion and callouts. One focus
   beat per scene, maximum.
5. Validate (`scene_plan` schema), self-review, checkpoint `awaiting_human`,
   present per-scene: screen, build order, beats, SFX intents. **End your
   turn.**
