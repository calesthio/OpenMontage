# Rig Plan Director - Character Animation Pipeline

## Goal

Produce `rig_plan` and `pose_library` from `character_design`.

## Process

1. Convert each character into rig parts:
   - body,
   - head,
   - eyes/pupils,
   - brows,
   - mouth shapes,
   - limbs/wings,
   - tail/accessories,
   - props.
2. Define pivots for every moving part.
3. Define layer order.
4. Define constraints so limbs do not rotate into impossible positions.
5. Define named poses for the approved scenes.
6. Define action cycles only when reused at least twice or central to the story.

## Runtime Pattern

Character differences are data. The renderer should not need one-off code for a
mouse versus a bird. A bird may have `wing_left`; a mouse may have `tail`, but
both feed the same pose interpolation and timeline compiler.

## Quality Checks

- Every moving part has a pivot.
- Every required action has poses or a procedural strategy.
- Every pose names the changed parts.
- Risky actions are called out, not hidden.

## Tool Use

Use `svg_rig_builder` to draft rig data and `pose_library_builder` to draft the
initial pose library. The agent may revise their output before checkpointing.
