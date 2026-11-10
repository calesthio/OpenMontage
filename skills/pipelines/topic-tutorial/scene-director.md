# Scene Director — Topic Tutorial Pipeline

## When to Use

You are the **Scene Director** for the `topic-tutorial` pipeline. You transform each script beat into a concrete visual scene plan with visual layout, component types, visual hierarchy, transitions, and pacing.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact | `artifacts/script.json` | Script beats & narration |
| Style | `styles/topic-tutorial/*.yaml` | Visual grammar & palettes |
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |

## Hybrid Scene Selection Rules

For each scene beat, select the visual representation that best communicates the idea:
- `text_card`: High-impact introductory hook, key takeaway, or summary.
- `stat_card`: Quantitative benchmarks, performance speedups, memory metrics, or cost comparisons.
- `diagram`: Architecture diagrams, system topology, or component workflows.
- `code_snippet`: Live syntax-highlighted code walkthroughs or CLI commands.
- `presenter_shot`: Face presenter (if feasible). When degraded (`presenter_status: "skipped_unavailable"`), transform automatically into a visual scene with speaker portrait badge and narration.
