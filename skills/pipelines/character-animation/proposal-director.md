# Proposal Director - Character Animation Pipeline

## Goal

Present character-animation concepts that are honest about local rigged motion,
reuse, cost, and runtime choice.

## Required Proposal Elements

Each option must include:

- characters and roles,
- visual style,
- action complexity,
- rig reuse strategy,
- sample plan,
- audio architecture,
- music plan,
- render runtime options,
- cost estimate,
- honest limitation note.

Where these go in `proposal_packet`: each option is a `concept_options[]` entry,
which is closed in the schema (required `id`, `title`, `hook`,
`narrative_structure` from its enum, `visual_approach` — the visual style as
prose — `target_duration_seconds`, `why_this_works`). Characters, action
complexity, rig reuse strategy, sample plan, audio architecture, and the
limitation note go under `proposal_packet.metadata.concept_details.<concept id>`
(e.g. `character_count`, `rig_complexity`, `reuse_strategy`,
`audio_architecture`). The cost estimate is `cost_estimate`; the music plan is
`production_plan.music_source`; the locked runtime is
`production_plan.render_runtime`. `selected_concept` holds only `concept_id`,
`rationale`, and `modifications` — downstream stages read the chosen concept from
`concept_options[]` by that id.

## Runtime Selection

Read `skills/meta/animation-runtime-selector.md` before recommending a runtime.

When both Remotion and HyperFrames are available:

- Remotion: best when the final composition needs deterministic React-rendered
  video, captions, audio, scene JSON, and final MP4 governance.
- HyperFrames: best when the character scene is HTML/SVG/GSAP-heavy and benefits
  from web-native authoring, lint, validate, and registry blocks.
- FFmpeg: post-processing only. Do not pick FFmpeg as the primary runtime for
  character acting.

Present both Remotion and HyperFrames to the user before recommending one.
Record the alternatives considered in the decision log as
`render_runtime_selection`, including why `hyperframes` was accepted or rejected.
Wait for user approval before locking `render_runtime`.

## Sample-First Rule

Before full production, propose a 10-15 second sample containing:

- one main character,
- one expression change,
- one body action,
- one camera/background treatment,
- one audio/music cue if relevant.

Do not batch-generate all assets until this sample is approved.

## Cost Honesty

Local rigging is cheap at render time but expensive in authoring complexity.
Report the difference:

- asset generation cost,
- TTS/music cost,
- local render cost,
- manual complexity risk.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
