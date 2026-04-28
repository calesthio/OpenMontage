# Executive Producer - Character Animation Pipeline

## When To Use

Use this pipeline when the requested deliverable depends on reusable animated
characters: cartoon shorts, mascot explainers, music-led character scenes,
dialogue between simple characters, or reference-inspired local animation.

Do not use this pipeline for one-off motion graphics with no acting. Route those
to `animation`. Do not use it for avatar presenter lip-sync. Route that to
`avatar-spokesperson`.

## Contract

The pipeline produces local, deterministic character animation. It does not
silently substitute still-image motion for acting. If the character motion cannot
be built with the available rigs, assets, or runtime, surface a blocker.

## Stage Order

1. `research` - understand reference, technique, and feasibility.
2. `proposal` - present concepts, runtime options, cost, music plan, sample plan.
3. `script` - write action-friendly beats and dialogue/narration.
4. `character_design` - define characters, silhouettes, emotions, actions.
5. `rig_plan` - define parts, pivots, layers, constraints, poses.
6. `scene_plan` - map story beats to character scenes.
7. `assets` - produce or source character parts, backgrounds, props, audio.
8. `edit` - compile timed action timeline.
9. `compose` - render through the approved runtime and run QA.
10. `publish` - package the final output.

## Governance Rules

- Run registry preflight before proposal.
- If both Remotion and HyperFrames are available, present both before locking
  `render_runtime`.
- Produce a 10-15 second sample before full asset generation.
- Character differences belong in rig data, not one-off code paths.
- Every generated or runtime-authored asset must list Layer 3 skills read.
- Use `character_animation_reviewer` plus final `final_review` before delivery.

## Send-Back Triggers

- `character_design` lacks required actions or emotional range.
- `rig_plan` lacks pivots for moving parts.
- `pose_library` has no readable acting poses.
- `action_timeline` has actions that cannot be rendered by the rig.
- Compose used a runtime not approved in proposal.
