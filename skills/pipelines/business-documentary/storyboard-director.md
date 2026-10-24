# Storyboard Director - Business Documentary Pipeline

## When To Use

Stage 6 of 12. You turn the verified `script` into a `scene_plan`: ordered
scenes with durations, the visual job each scene does, concrete English search
queries, and an honest visual class for every slot.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `script`, `fact_check_report` (validated, status != blocked) | Narration + verdicts |
| Schema | `schemas/artifacts/scene_plan.schema.json` | Output validation |
| Registry | `diagram_gen`, `direct_clip_search` availability | What can actually be produced |

## Process

### 1. One scene per narration beat

Cut the script into scenes that each carry one visual job. A scene is not a
sentence; it is a shot idea with a duration.

### 2. Assign a visual class to every scene

| Class | Meaning | Rule |
|-------|---------|------|
| `literal` | Footage of the thing named | Strongest option; must be provenance-checked |
| `illustrative` | Footage that stands in for the idea | Must be labelled; never claimed as the named company/event |
| `archive` | Period footage/documents | Check third-party rights even on Archive.org/Wikimedia |
| `chart` | Data visualization from verified data | Carry units, dates and source |
| `map` | Geographic flow | Carry the source of the geography |
| `diagram` | Process/system explanation | Must explain something, never decorate |

If the narration names a specific company and the only available material is
`illustrative`, the scene stays illustrative and the edit must not imply
otherwise.

### 3. Write 2–4 concrete queries per scene

Queries follow **object + action + environment/period/scale**:

- good: `industrial laundry facility sorting linen conveyor`
- good: `warehouse pallet stacker forklift 2020s`
- bad: `business`, `laundry`, `logistics concept`

### 4. Decide where diagrams earn their place

Use `diagram_gen` when the film must show a flow or a number that narration
alone cannot carry (route density, margin stack, supply chain hop). Every
diagram carries its data source in the frame.

Check availability first:

```bash
python -c "from tools.tool_registry import registry; registry.discover(); print(registry._tools['diagram_gen'].get_info()['status'])"
```

### 5. Duration math

Scene durations must sum within 10% of `script.total_duration_seconds`. The
last scene carries the close.

### 6. Lock the render runtime plan

Record the intended runtime in `scene_plan.metadata.render_runtime` with the
shortlist you will present at compose (see the executive producer's runtime
rule). Do not silently default.

### 7. Quality gate

- Schema-valid `scene_plan`.
- Every scene: narration excerpt, visual class, 2–4 queries, duration.
- Sum of durations within 10% of script duration.
- `metadata.visual_classes` recorded per scene.
- No scene is classed `literal` unless real footage of that specific thing is
  actually obtainable.

## Common Pitfalls

- Writing queries from the topic instead of the shot.
- Classing generic B-roll as `literal` because the filename matched.
- Adding a diagram because the scene feels empty. Empty scenes are a script
  problem.
- Ignoring era mismatch (a 1970s factory clip under a 2024 claim).

---

## Gate Reminder (Binding)

`storyboard` gates on human approval. After review passes: checkpoint
`status="awaiting_human"`, present the scene table, and **END YOUR TURN**.
