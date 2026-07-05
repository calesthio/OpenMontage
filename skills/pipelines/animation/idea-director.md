# Idea Director - Animation Pipeline

## When To Use

Use this pipeline when the video should be built primarily through designed motion: motion graphics, kinetic typography, diagram-led explainers, math visuals, or illustrative animation.

Do not use this pipeline when the project is really footage-led with a few overlays. That belongs in `hybrid`.

## Reference Inputs

- `docs/animation-best-practices.md`
- `skills/creative/animation-pipeline.md`
- `skills/creative/storytelling.md`
- `skills/creative/ink-theater.md` — for hand-drawn **ink "doodle"** briefs: a character that draws itself and performs, or a deadpan contraption explainer (Ink Theater engine + Ink Puppet mocap; command `/ink-art`). A stick/pencil character that walks or dances belongs in the `character-animation` pipeline.

## Process

### 1. Classify The Animation Mode

Choose the primary mode:

- `diagrammatic`
- `motion_graphics`
- `kinetic_type`
- `math_animation`
- `illustrative`
- `mixed_animation`

### 2. Decide The Visual Path Early

Figure out which tools are supposed to do the work:

- `diagram_gen`
- `math_animate`
- `code_snippet`
- `image_selector`
- `video_selector` or a concrete video provider tool
- source-provided art

If the requested mode depends on unavailable tools, say so in the brief metadata immediately.

### 3. Choose A Reuse Strategy

Animation gets expensive when every scene is unique. Define:

- recurring motifs,
- layout system,
- transition family,
- typography hierarchy.

### 4. Build The Brief

Recommended metadata keys:

- `animation_mode`
- `visual_path`
- `narration_strategy`
- `reuse_strategy`
- `timing_style`
- `blocked_capabilities`

### 5. Quality Gate

- the animation mode is explicit,
- the visual path is feasible,
- the project is designed for reuse,
- the brief is honest about missing tools.

## Common Pitfalls

- Treating all animation as one generic category.
- Planning bespoke visuals for every scene.
- Hiding missing tool paths until the asset stage.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
