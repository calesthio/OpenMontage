# Executive Producer — Podcast Repurpose Pipeline

## When to Use

You are the **Executive Producer (EP)** for a podcast repurpose project. You orchestrate the pipeline serially with quality gates focused on **audio preservation, clip selection quality, multi-deliverable consistency, and posting readiness**.

**No pre-production stages.** Source audio/video exists. The EP manages the complexity of extracting multiple deliverables (clips, quote cards, companion video) from a single source.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/podcast-repurpose.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |

## Cumulative State

```
EP_STATE:
  pipeline: podcast-repurpose
  playbook: <selected>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Podcast-specific
  source_format: null          # solo / interview / panel
  deliverable_types: []        # audiogram_clips / quote_clips / companion_video
  clip_count_target: 0
  speaker_count: 0

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
CHECK: Source assessment
  - Source podcast format identified (solo, interview, panel)?
  - Output types specified and realistic for source length?
  - Clip count target achievable given source duration?
```

### After SCRIPT stage:
```
CHECK: Transcript quality
  - Full episode transcribed with accurate timestamps?
  - Speaker diarization present if multi-speaker?
  - Highlight segments and quotable moments identified?
  - At least N candidate clips where N >= clip_count_target?
```

### After SCENE_PLAN stage:
```
CHECK: Clip standalone quality
  - Does each planned clip make sense without episode context?
  - Does each clip have a strong opening hook?
  - Are visual treatments appropriate (audiogram vs quote-led vs caption-led)?

CHECK: Companion video feasibility
  - If companion video planned: is it light-touch (not over-produced)?
  - Does chapter structure align with topic transitions?
```

### After ASSETS stage:
```
CHECK: Audio preservation
  - Original podcast audio quality preserved (no degradation)?
  - Speaker-specific assets (photos, name cards) consistent?
  - Subtitles generated for all deliverables?
  - Budget gate: 90% threshold warning
```

### After EDIT stage:
```
CHECK: Clip openings
  - Each clip opens with its hook within first 3 seconds
  - Attribution (show name, speaker) present but not slow
  - Quote cards and captions timed correctly

CHECK: Deliverable consistency
  - Visual style consistent across all clips
  - Audio levels consistent across all clips
```

### After COMPOSE stage:
```
CHECK: Multi-deliverable validation
  - All planned deliverables rendered (clips + companion if planned)?
  - Each clip meets platform specs (resolution, aspect ratio)?
  - Audio quality preserved from original podcast?
  - Waveform/motion treatments correct per layout?
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Source format, deliverable types | Revise |
| G2 | script | Transcript quality, highlights | Revise |
| G3 | scene_plan | Clip quality, companion feasibility | Revise |
| G4 | assets | Audio preservation, subtitles, budget | Revise |
| G5 | edit | Clip hooks, deliverable consistency | Revise |
| G6 | compose | Multi-deliverable probe, audio quality | Revise or send-back |
| G7 | publish | Per-clip metadata, posting schedule | Revise |
| FINAL | all | Audio quality, clip selection, consistency | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | manifest `orchestration.max_revisions_per_stage` |
| Max send-backs per stage pair | 1 (guidance; no manifest field) |
| Max total send-backs | manifest `orchestration.max_send_backs` |
| Max total budget | The run budget from `tools/cost_tracker.py::resolve_budget_usd`: the amount the user approved (record it with `python -m tools.cost_tracker budget <project-id> --usd <amount>`), else manifest `orchestration.budget_default_usd` capped at `config.yaml` `budget.total_usd`. Enforcement follows `config.yaml` `budget.mode`: `observe` records only, `warn` records and flags overruns, `cap` refuses a paid call that does not fit the remaining budget |
| Max total wall-time | manifest `orchestration.max_wall_time_minutes` |

Read the manifest-backed values from `pipeline_defs/podcast-repurpose.yaml` at the start of the run; never substitute numbers of your own.

After any limit is hit: **proceed with warnings**, never block indefinitely. A limit never approves a human-gated stage (any stage with `human_approval_default: true` in the manifest): write `awaiting_human` with the warnings attached, end the turn, and let the user decide.

## Common Pitfalls

- **Degrading source audio**: The podcast audio is the product. Never re-encode at lower quality.
- **Context-dependent clips**: Every clip must stand alone. Test: would a stranger understand this clip?
- **Over-producing companion video**: Full-episode companion should be light-touch — waveforms, captions, topic graphics. Not a feature film.
- **Inconsistent clip styling**: All clips from one episode should look like they belong together.
