# Asset Director — Product-Motion Pipeline

## When to Use

Fifth stage — where the replicas get built. You produce every asset: the
hand-authored replica scene components (with per-scene snapshot stills for
the gate), narration audio, music, and SFX. This stage ends at the **fidelity
gate**: the user reviews replica snapshots against the real product before
any motion/render work is locked in.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Layer 3 | `.agents/skills/glass-ui-motion/SKILL.md` (+ references) | The truthful-replica method, glass recipes, SFX generation |
| Meta | `skills/meta/bespoke-composition.md` | Atelier construction sequence and engine gotchas |
| Scripts | `scripts/scaffold_atelier_project.py`, `scripts/atelier_snapshots.py` | Project scaffold; per-scene stills |
| Tools | `tts_selector`, `music_gen`, `sfx_gen`, `image_selector`, `subtitle_gen` | Audio + support assets |
| Artifacts in | `scene_plan`, `design_system`, `ui_inventory` | What to build and the truth to build it from |

## Process

### 1. Scaffold the atelier project

`scripts/scaffold_atelier_project.py` under `projects/<id>/`. Generate
`tokens.ts` **from the design_system artifact** — every color/font/radius/
shadow/glass value as a named export. This module is the only place style
values may live; scene files import from it (the no-literal rule is
grep-audited at review).

### 2. Author replicas (the heart of the stage)

Per scene, per the glass-ui-motion method:

1. Open the repo `source_files` the scene plan cites. Read the real JSX/
   template.
2. Port the structure faithfully — field order, labels, button copy, icons —
   into a scene component under `projects/<id>/scenes/`. Simplify by
   omission, never substitution.
3. Style only from `tokens.ts`. Load the product's real fonts.
4. Wire the assembly choreography (build order, spring presets, staggers)
   from the scene plan — motion can be refined at edit, but entrances exist
   now so snapshots look real.
5. Never import from `remotion-composer/src/components` or the stock
   compositions — the atelier guardrail fails the render, and the doctrine
   fails the review.

### 3. Snapshot stills for the gate

`scripts/atelier_snapshots.py` renders one PNG per scene at its
most-assembled frame → `projects/<id>/assets/images/`. Register each in the
asset_manifest as `type: "image"`, `subtype: "scene_snapshot"`, with
**`provenance.source_files`** (the repo files replicated) and
**`provenance.design_tokens`** (token names used). Deviations →
`provenance.notes`.

### 4. Narration, music, SFX

- **Narration**: sample-first protocol (generate `sample_section_id`, play,
  approve, then batch) via `tts_selector` with the proposal's provider.
  Record `voice_performance` metadata per asset.
- **Music**: per the proposal's music decision (library / generated via
  `music_gen` with `force_instrumental: true` / none).
- **SFX**: generate one effect per cue class used by the scene plan (4-6
  total) via `sfx_gen`, prompts from `references/sfx-cues.md`. Listen to each
  once. Register as `type: "sfx"` with the generation prompt.

### 5. Validate, review, gate

Validate `asset_manifest`; run the grep-audit (no non-token literals in
`scenes/`); self-review against the manifest's review_focus. Checkpoint
`awaiting_human` and present **scene-by-scene**: snapshot still + the repo
source it replicates + provenance. Ask for corrections per scene. **End your
turn.**

## Failure modes

- A replica styled from memory of the screenshot instead of the source file —
  labels drift, spacing lies. Always re-open the source.
- Snapshot taken mid-assembly (elements missing) — the user can't judge
  fidelity. Snapshot at the most-assembled frame.
- SFX generated per-element instead of per-class — 20 assets where 5 belong.
