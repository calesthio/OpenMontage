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

## Runtime Selection (required field — `render_runtime`)

Read `skills/meta/animation-runtime-selector.md` and `skills/core/hyperframes.md`
for the decision matrix, and `AGENT_GUIDE.md` → "Present Both Composition Runtimes
(HARD RULE)" for the governance contract.

**MANDATORY workflow — present both runtimes, don't silently default:**

1. Query `video_compose.get_info()["render_engines"]`. If both `remotion` and
   `hyperframes` are `True`, proceed to step 2.
2. Present both runtimes to the user with brief-specific analysis:
   - **Remotion** — best when the final composition needs deterministic
     React-rendered video, captions, audio, scene JSON, and final MP4 governance.
     One line on fit, one line on tradeoff.
   - **HyperFrames** — best when the character scene is HTML/SVG/GSAP-heavy and
     benefits from web-native authoring, lint, validate, and registry blocks.
     One line on fit, one line on tradeoff.
3. Recommend one with rationale tied to the brief's action complexity, rig style,
   and approved tone. FFmpeg is post-processing only — never the primary runtime
   for character acting.
4. Wait for explicit user approval. Do NOT write `render_runtime` into
   `proposal_packet.production_plan` before approval.
5. Log a `render_runtime_selection` decision in `decision_log` with BOTH runtimes
   in `options_considered` plus `ffmpeg` if it was a realistic option.

A `render_runtime_selection` decision with only one option considered when both
were available is a CRITICAL reviewer finding.

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
