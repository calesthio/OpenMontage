# Script Director - Character Animation Pipeline

## Goal

Write scripts as performable animation beats, not just narration.

## Process

1. Lock audio architecture:
   - music-only,
   - narrator,
   - character dialogue,
   - narrator plus character sounds/dialogue.
2. Break the story into beats that can be acted with poses.
3. For each beat, state what changes visually:
   - emotion,
   - gaze,
   - body pose,
   - prop interaction,
   - camera,
   - environment.

## Writing Rules

- Prefer short visual beats with readable holds.
- Avoid action that needs many unique hand-drawn poses unless approved.
- Dialogue should be short enough for mouth-shape approximation.
- Silent/music-led scenes need stronger physical acting notes.

## Output Notes

In the `script` artifact metadata, include:

- `audio_architecture`,
- `character_beats`,
- `required_emotions`,
- `required_actions`.
