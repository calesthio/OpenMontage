# Character Design Director - Character Animation Pipeline

## Goal

Produce `character_design`: a small cast with clear silhouettes, roles,
emotions, actions, and style anchors.

## Process

1. List every character with `id`, role, body type, and style.
2. Identify the minimum emotional range needed by the story.
3. Identify the minimum action list needed by the story.
4. Decide required views: front, 3/4, side, back. Keep MVPs to one or two views.
5. Note props attached to characters, such as scarf, feather, bag, glasses.

## Constraints

- One or two characters is the MVP sweet spot.
- Animal characters need species-specific parts and action cycles.
- More views multiply asset and pose requirements.
- Do not invent more poses than the approved duration can use.

## Tool Use

Use `character_spec_generator` for structured drafts. Use `image_selector` only
after the visual style and character sheet requirements are explicit. Before
using image generation, read the tool's Layer 3 skills from the registry.

## Quality Bar

A character design is ready only when an animator or tool can infer what parts,
expressions, and actions must exist.
