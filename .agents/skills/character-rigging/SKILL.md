---
name: character-rigging
description: Build data-driven 2D character rigs for local animation: parts, pivots, layers, constraints, views, and reusable rig packages.
license: MIT
---

# Character Rigging

Use this skill when building OpenMontage `rig_plan` artifacts or renderer input
for local 2D character animation.

## Proven Patterns

- Keep runtime code generic; make each character a data package.
- Split characters into independently transformable parts.
- Define pivots in the same coordinate space as the artwork.
- Store constraints on moving parts to prevent impossible rotations.
- Keep layer order explicit; do not rely on SVG source order after generation.
- Start with one view and add views only when the shot list requires them.

## Rig Package

```json
{
  "character_id": "mouse",
  "rig_type": "svg_rig",
  "parts": [
    { "id": "body", "kind": "torso", "layer": 10 },
    { "id": "head", "kind": "head", "layer": 30, "parent": "body" },
    { "id": "arm_right", "kind": "limb", "layer": 40, "parent": "body" }
  ],
  "joints": {
    "head": { "pivot": [320, 180], "rotation": [-20, 20] },
    "arm_right": { "pivot": [390, 310], "rotation": [-70, 95] }
  }
}
```

## Quality Checklist

- Every moving part has a pivot.
- Every child part has a parent where hierarchy matters.
- Mouth shapes are separate assets or separate path groups.
- Eyes and pupils are separate when gaze needs to change.
- Props are separate if the character touches or carries them.

## Sources

- SVG transform-origin behavior is browser-defined and can be sensitive to
  coordinate space; prefer explicit SVG-coordinate pivots when using GSAP
  `svgOrigin`: https://gsap.com/docs/v3/GSAP/CorePlugins/CSS/
- Remotion animations must be frame-driven and deterministic via current frame:
  https://www.remotion.dev/docs/use-current-frame
