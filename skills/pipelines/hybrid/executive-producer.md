# Executive Producer — Hybrid Pipeline

## When to Use

You are the **Executive Producer (EP)** for a hybrid video that combines source footage with designed or generated support assets. You orchestrate the pipeline serially with quality gates focused on **source/support balance, overlay density, and cross-medium coherence**.

**No pre-production stages.** The user provides direction and source material. The EP ensures generated support layers enhance rather than eclipse the source.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/hybrid.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |

## Cumulative State

```
EP_STATE:
  pipeline: hybrid
  playbook: <selected>
  target_duration_seconds: <from brief>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Hybrid-specific
  anchor_medium: null         # source footage type (interview, product, screen, etc.)
  support_layers: []          # planned support types (diagrams, overlays, graphics, etc.)
  source_to_support_ratio: null  # target balance (e.g., 70/30 source/support)

  artifacts:
    idea: null
    script: null
    scene_plan: null
    assets: null
    edit: null
    compose: null
    publish: null

  revision_counts: {}
  issues_log: []
```

## EP-Specific Cross-Stage Checks

### After IDEA stage:
```
CHECK: Anchor medium clarity
  - Is the anchor medium explicitly identified?
  - Are support layers justified (filling real gaps, not decorating)?
  - Is the source inventory realistic?
```

### After SCRIPT stage:
```
CHECK: Source/support beat separation
  - Are source-led and support-led beats clearly separated?
  - Does the script avoid relying on unsupported assets?
  - Is narration/dialogue plan realistic?
```

### After SCENE_PLAN stage:
```
CHECK: Source primacy
  - Does source footage remain visually primary where intended?
  - Are overlay and support layers not overloading the frame?
  - Max concurrent overlay layers: 2

CHECK: Variant planning
  - If platform variants planned: are they realistic?
  - Do aspect-ratio variants maintain readability?
```

### After ASSETS stage:
```
CHECK: Source/support quality match
  - Do generated support assets match the quality level of source footage?
  - Are shared template assets reused across scenes?
  - Budget gate: 90% threshold warning
```

### After EDIT stage:
```
CHECK: Anchor-cut coherence
  - Is the anchor cut coherent BEFORE support layers are added?
  - Do support visuals clarify rather than distract?
  - Is variant logic consistent across deliverables?
```

### After COMPOSE stage:
```
CHECK: Output validation
  - ffprobe: duration, resolution, codec
  - Source and support layers remain balanced in the final render
  - Audio stays coherent across footage and generated elements
  - Aspect-ratio variants preserve readability
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Anchor medium, support justification | Revise |
| G2 | script | Source/support separation, narration plan | Revise |
| G3 | scene_plan | Source primacy, overlay density, variants | Revise |
| G4 | assets | Quality match, reuse, budget | Revise |
| G5 | edit | Anchor-cut coherence, support clarity | Revise |
| G6 | compose | Balance, variants, audio coherence | Revise or send-back |
| G7 | publish | Metadata, source-mix labeling | Revise |
| FINAL | all | Source/support balance, readability | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | manifest `orchestration.max_revisions_per_stage` |
| Max send-backs per stage pair | 1 (guidance; no manifest field) |
| Max total send-backs | manifest `orchestration.max_send_backs` |
| Max total budget | The run budget from `tools/cost_tracker.py::resolve_budget_usd`: the amount the user approved (record it with `python -m tools.cost_tracker budget <project-id> --usd <amount>`), else manifest `orchestration.budget_default_usd` capped at `config.yaml` `budget.total_usd`. Enforcement follows `config.yaml` `budget.mode`: `observe` records only, `warn` records and flags overruns, `cap` refuses a paid call that does not fit the remaining budget |
| Max total wall-time | manifest `orchestration.max_wall_time_minutes` |

Read the manifest-backed values from `pipeline_defs/hybrid.yaml` at the start of the run; never substitute numbers of your own.

After any limit is hit: **proceed with warnings**, never block indefinitely. A limit never approves a human-gated stage (any stage with `human_approval_default: true` in the manifest): write `awaiting_human` with the warnings attached, end the turn, and let the user decide.

## Common Pitfalls

- **Support eclipsing source**: Generated graphics should not dominate. Source footage is the anchor.
- **Overlay overload**: Max 2 concurrent overlay layers. More creates visual noise.
- **Inconsistent quality**: If source is 1080p handheld and support is slick 4K graphics, the mismatch is jarring.
- **Ignoring variant readability**: Text overlays that work at 16:9 may be unreadable at 9:16.
