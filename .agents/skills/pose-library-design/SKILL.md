---
name: pose-library-design
description: Design reusable 2D character pose libraries, action cycles, and expression states for data-driven animation.
license: MIT
---

# Pose Library Design

Use this skill when producing `pose_library` artifacts.

## Pose Categories

- Neutral: idle, breathe, listening.
- Attention: look_up, look_down, look_left, look_right.
- Emotion: happy, sad, surprised, worried, determined.
- Action: reach, point, hold, jump, flap, walk_contact, walk_passing.
- Mouth: closed, small_o, wide_open, smile, frown, phoneme-ish shapes.

## Acting Pattern

Use timed pose sequences:

```text
anticipation -> action -> hold -> settle
```

Do not continuously animate every part. Holds make the acting readable.

## Pose Data Pattern

```json
{
  "pose": "surprised",
  "parts": {
    "head": { "rotation": -6, "y": -4 },
    "pupil_left": { "x": 4, "y": -6 },
    "mouth": "small_o"
  },
  "hold_frames": 18,
  "transition": "back.out"
}
```

## Quality Checklist

- Required emotions have poses.
- Required actions have poses or cycles.
- Reused cycles have contact and passing poses.
- Poses name only changed parts; defaults come from the rig.

## Sources

- GSAP timeline sequencing for readable multi-step poses:
  https://gsap.com/docs/v3/GSAP/Timeline/
- Remotion interpolation for frame-based transitions:
  https://www.remotion.dev/docs/interpolate
- Remotion spring for natural motion:
  https://www.remotion.dev/docs/spring
