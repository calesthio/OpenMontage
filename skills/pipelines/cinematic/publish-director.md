# Publish Director - Cinematic Pipeline

## When To Use

Package the cinematic piece and any cutdowns so the hero version stays clear and the distribution intent is obvious.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["proposal"]["proposal_packet"]`, `state.artifacts["research"]["research_brief"]`, `state.artifacts["script"]["script"]` | Final outputs and beat map |
| Playbook | Active style playbook | Tone and naming consistency |

## Process

### 1. Separate Hero And Derivatives

Typical deliverables:

- hero trailer or brand film,
- teaser cut,
- social cutdown,
- poster-frame or thumbnail concept.

### 2. Match Metadata To Tone

Packaging should reflect the actual mood:

- dramatic,
- premium,
- mysterious,
- reflective,
- urgent.

### 3. Preserve Editorial Truth

Store in `publish_log.metadata`:

- `hero_output`
- `derivative_outputs`
- `poster_frame_notes`
- `distribution_notes`

### 4. Quality Gate

- hero export is clearly identified,
- derivative exports are labeled by purpose,
- metadata fits the tone,
- the package is usable without manual cleanup.

## Editorial Hand-off (FCPXML)

`export_bundle` packages the **finished render** for platform upload. When the user
wants to keep cutting — colour grading, finishing, or reworking the edit in DaVinci
Resolve or Final Cut Pro — also run `fcpxml_export`, which emits an **editable
timeline** instead of a locked flat file:

```
registry.get("fcpxml_export").execute({"project_dir": "projects/<project-id>"})
```

Offer it whenever the brief mentions grading, finishing, or "I'll edit it myself".
The two are complementary, not alternatives — a hand-off usually ships both.

Things worth telling the user:

- **Grid scenes survive** as multi-track connected clips, so a 2-up or 3-up stays
  editable per-cell. Only 2-up and 3-up have verified Resolve transforms — wider
  grids raise rather than emit a silently-wrong timeline.
- **The sequence format follows the footage** (frame rate and resolution of the
  first source clip). Pass `fps`/`width`/`height` to override when the deliverable
  differs from the source.
- **Check `sdr_substitutions` in the result.** Any clip listed there points at a
  transcoded SDR copy rather than the original Dolby Vision file — mention it, since
  the editor will want to relink to the originals before grading.

## Common Pitfalls

- Mixing teaser and hero outputs without clear naming.
- Writing generic metadata that ignores the mood.
- Treating all cutdowns as interchangeable.
- Shipping only the flat render when the user asked to finish the edit themselves.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
