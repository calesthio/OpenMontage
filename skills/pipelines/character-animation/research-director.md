# Research Director - Character Animation Pipeline

## Goal

Ground the character-animation plan in real references and current technique.
For reference videos, start from `video_analysis_brief`: content, pacing, motion
classification, keyframes, color, and production complexity.

## Process

1. Identify what the reference actually uses:
   - rigged local animation,
   - frame-by-frame traditional animation,
   - video generation,
   - still-image motion,
   - mixed techniques.
2. Research 3-5 relevant examples or techniques.
3. Separate what the pipeline can reproduce locally from what requires manual
   illustration, video generation, or a larger asset library.
4. Record reusable animation primitives:
   - walk cycle,
   - blink,
   - head turn,
   - reach,
   - wing flap,
   - squash/stretch,
   - camera pan/parallax,
   - particles/weather.

## Output Guidance

The `research_brief` should include:

- `character_animation_fit`: high/medium/low,
- `reference_motion_type`,
- `required_character_actions`,
- `rig_complexity`,
- `manual_asset_risks`,
- `local_runtime_candidates`.

## Quality Bar

Be explicit when a reference is hand-drawn or frame-by-frame. The user can still
choose an inspired local rigged style, but the proposal must not imply exact
traditional-animation quality from an automatic rig.
