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

### 4. Package The Export

Use `export_bundle` (local and offline; it never uploads) once per deliverable,
starting with the hero. Pass the `video_path` from `render_report`, the `title`,
and the metadata you prepared. It writes the export directory
(`projects/<project>/exports/` for a video in the project's `renders/`) and
returns a schema-valid `publish_log` in `data["publish_log"]`. Persist the hero's
as the stage artifact and add the fields above under its `metadata`. See
`skills/pipelines/explainer/publish-director.md` Step 5 for the full input list
and export layout.

### 5. Quality Gate

- hero export is clearly identified,
- derivative exports are labeled by purpose,
- metadata fits the tone,
- the package is usable without manual cleanup.

## Common Pitfalls

- Mixing teaser and hero outputs without clear naming.
- Writing generic metadata that ignores the mood.
- Treating all cutdowns as interchangeable.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
