# Edit Director — Topic Tutorial Pipeline

## When to Use

You are the **Edit Director** for the `topic-tutorial` pipeline. You assemble audio durations, word captions, scene visual props, and transition timing into `artifacts/edit_decisions.json`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact | `artifacts/asset_manifest.json` | Generated audio and assets |
| Artifact | `artifacts/scene_plan.json` | Scene layouts and cut types |
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |

## Timing Alignment

1. Compute frame counts at 30 fps for each scene based on its narration audio duration:
   $$\text{frames} = \text{round}(\text{duration\_seconds} \times 30)$$
2. Align word captions with `{word: string, startMs: number, endMs: number}` formatting for Remotion compatibility.
3. Save `artifacts/edit_decisions.json` conforming strictly to the schema.
