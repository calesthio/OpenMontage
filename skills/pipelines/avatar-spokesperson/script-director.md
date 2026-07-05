# Script Director - Avatar Spokesperson Pipeline

## When To Use

Turn the approved brief into scene-safe spoken copy for an avatar presenter. The quality bar is not literary flourish. It is spoken clarity, believable pacing, and one clean point per scene.

## Reference Inputs

- `docs/avatar-spokesperson-best-practices.md`
- `skills/creative/storytelling.md`

## Process

### 1. Write For Speech, Not For Slides

Prefer:

- short sentences,
- direct verbs,
- one idea per beat,
- explicit transitions,
- conversational emphasis.

If the copy sounds like a brochure when read aloud, rewrite it.

### 2. Break Into Scene-Safe Chunks

Avatar scenes are easier to manage when each section is compact. A useful starting point is:

- hook,
- value statement,
- proof or feature beat,
- CTA.

### 3. Keep On-Screen Text Light

The presenter is already carrying attention. Use on-screen text only for:

- product names,
- short proof points,
- CTA copy,
- legal or compliance text that must appear.

### 4. Use Metadata For Delivery Notes

Recommended metadata keys:

- `scene_copy_map`
- `cta_language`
- `pronunciation_notes`
- `supplied_script_source`
- `legal_text_requirements`

### 5. Quality Gate

- the copy sounds spoken,
- scene lengths are realistic,
- CTA placement is clear,
- text overlays are restrained.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- Overstuffing one scene because the script reads well on paper.
- Duplicating the same sentence in speech and large text overlays.
- Writing humor or improvisational beats the avatar path cannot sell.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
