# Publish Director - Hybrid Pipeline

## When To Use

Package the hybrid outputs so the hero cut and its derivatives stay organized and the source/support mix remains clear.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Final outputs and hybrid framing |
| Playbook | Active style playbook | Tone consistency |

## Process

### 1. Distinguish Master And Variants

Group outputs as:

- master cut,
- short-form derivatives,
- format variants,
- chaptered or contextual variants.

### 2. Preserve Source Truth In Packaging

If the project uses interview footage, screen recording, or product footage as its anchor, the metadata should reflect that instead of packaging it like a pure generated piece.

### 3. Store Cross-Output Notes

Recommended metadata keys:

- `master_output`
- `derivative_outputs`
- `source_mix_notes`
- `platform_copy_map`

### 4. Quality Gate

- master and variants are clearly labeled,
- metadata matches the true source mix,
- export folders are organized by purpose,
- the package is ready to use without manual cleanup.

## Common Pitfalls

- Hiding which output is the hero cut.
- Packaging a source-led project like a generic generated asset.
- Losing platform-specific copy and labeling across variants.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
