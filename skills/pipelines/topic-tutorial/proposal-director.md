# Proposal Director — Topic Tutorial Pipeline

## When to Use

You are the **Proposal Director** for the `topic-tutorial` pipeline. You translate the findings from `research_brief.json` and `fact_sheet.json` into differentiated concept options, production budgets ($0.00 for local runs), visual style recommendations, and the canonical `decision_log.json`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact | `artifacts/research_brief.json` | Grounding findings |
| Schema | `schemas/artifacts/proposal_packet.schema.json` | Artifact validation |
| Schema | `schemas/artifacts/decision_log.schema.json` | Decision tracking |

## Key Decisions Contract
1. **Present Both Composition Runtimes (HARD RULE):** Present both Remotion and hyperframes runtime options to the user before locking `render_runtime`. Record `render_runtime_selection` in `decision_log`.
2. **Present Composition Mode:** Templated vs Atelier.
3. **Presenter Treatment:** Announce whether local talking-head is feasible or degraded to narration-led visuals (`presenter_status: "skipped_unavailable"`).
4. **Style Preset:** Select the subject-specific visual style (e.g. `software-technical`, `ai-news-explainer`, `science-math`, `history-timeline`, `finance-data`).
