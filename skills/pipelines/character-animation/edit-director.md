# Edit Director - Character Animation Pipeline

## Goal

Produce `edit_decisions` and `action_timeline`.

## Process

1. Carry `render_runtime` forward from the approved proposal — exactly
   `production_plan.render_runtime`, with `renderer_family` (and
   `composition_mode` when set) beside it, `version: "1.0"`, and
   `metadata.proposal_render_runtime` / `metadata.delivery_promise` copied from
   the proposal. The schema rejects `edit_decisions` without `version`, `cuts`,
   and `render_runtime`, and `video_compose` refuses to render without
   `render_runtime` and `renderer_family`.
2. Convert scene beats into timed character actions.
3. Add anticipation, hold, action, and follow-through where appropriate.
4. Align mouth/gesture beats to dialogue or music.
5. Keep action density readable.

## Timing Pattern

Most acting beats need:

```text
anticipation -> action -> hold/reaction -> settle
```

Do not animate everything continuously. Holds are part of acting.

## Tool Use

Use `action_timeline_compiler` for a first pass, then revise the timeline if the
acting or rhythm is weak.

## Quality Bar

Every scene has timed actions. Every action maps to a pose, action cycle, or
procedural effect that the renderer can understand.
