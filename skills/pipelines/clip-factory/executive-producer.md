# Executive Producer — Clip Factory Pipeline

## When to Use

You are the **Executive Producer (EP)** for a clip factory project. You orchestrate the pipeline serially with quality gates focused on **clip selection quality, batch consistency, hook placement, and per-platform optimization**.

**No pre-production stages.** Long-form source content exists. The EP manages the extraction of multiple independent short clips, ensuring each stands alone while maintaining series consistency.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/clip-factory.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |

## Cumulative State

```
EP_STATE:
  pipeline: clip-factory
  playbook: <selected>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Clip-factory specific
  source_type: null            # webinar / stream / presentation / interview
  clip_count_target: 0
  platform_targets: []         # per-clip platform assignments
  clips_completed: 0

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
CHECK: Source and targets
  - Source content type identified?
  - Clip count target realistic for source duration? (rule of thumb: 1 clip per 5-10 min source)
  - Platform mix defined?
  - Clip selection criteria clear?
```

### After SCRIPT stage:
```
CHECK: Transcript and ranking
  - Full transcription with accurate timestamps?
  - At least N candidate clips where N >= clip_count_target?
  - Each candidate is self-contained (standalone test)?
  - Clips ranked by quality/engagement potential?
```

### After SCENE_PLAN stage:
```
CHECK: Clip boundaries
  - Each clip has clean in/out points (no mid-sentence cuts)?
  - Platform-specific framing planned (vertical vs square vs landscape)?
  - No clip exceeds platform max duration?

CHECK: Batch diversity
  - Clips cover different topics/moments from the source?
  - Not all clips from one section of the source?
```

### After ASSETS stage:
```
CHECK: Batch consistency
  - Per-clip subtitles with correct time offsets?
  - Shared branding assets (title cards, hooks) prepared?
  - Audio normalized consistently across all clips?
  - Budget gate: 90% threshold warning
```

### After EDIT stage:
```
CHECK: Hook placement
  - Each clip has its hook within first 2-3 seconds?
  - Subtitle styling consistent across all clips?
  - Each edit is independent (no cross-clip dependencies)?

CHECK: Completeness
  - Edit decisions exist for every planned clip?
```

### After COMPOSE stage:
```
CHECK: Batch render validation
  - All clips rendered successfully?
  - Each clip meets target platform specs (resolution, aspect ratio)?
  - Audio levels consistent across clips?
  - No clip has rendering artifacts?
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Source assessment, clip targets | Revise |
| G2 | script | Transcript quality, clip ranking | Revise |
| G3 | scene_plan | Clip boundaries, batch diversity | Revise |
| G4 | assets | Batch consistency, audio normalization | Revise |
| G5 | edit | Hook placement, completeness | Revise |
| G6 | compose | Batch render probe, platform specs | Revise or send-back |
| G7 | publish | Per-clip metadata, posting order | Revise |
| FINAL | all | Clip quality, consistency, hooks | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | manifest `orchestration.max_revisions_per_stage` |
| Max send-backs per stage pair | 1 (guidance; no manifest field) |
| Max total send-backs | manifest `orchestration.max_send_backs` |
| Max total budget | The run budget from `tools/cost_tracker.py::resolve_budget_usd`: the amount the user approved (record it with `python -m tools.cost_tracker budget <project-id> --usd <amount>`), else manifest `orchestration.budget_default_usd` capped at `config.yaml` `budget.total_usd`. Enforcement follows `config.yaml` `budget.mode`: `observe` records only, `warn` records and flags overruns, `cap` refuses a paid call that does not fit the remaining budget |
| Max total wall-time | manifest `orchestration.max_wall_time_minutes` |

Read the manifest-backed values from `pipeline_defs/clip-factory.yaml` at the start of the run; never substitute numbers of your own.

After any limit is hit: **proceed with warnings**, never block indefinitely. A limit never approves a human-gated stage (any stage with `human_approval_default: true` in the manifest): write `awaiting_human` with the warnings attached, end the turn, and let the user decide.

## Common Pitfalls

- **Context-dependent clips**: Each clip must make sense alone. No "as I was saying" openings.
- **Slow hooks**: Social clips need to hook in 2-3 seconds. Front-load the interesting part.
- **Inconsistent audio levels**: Clips from different parts of the source have different audio levels. Normalize.
- **Missing platform optimization**: A YouTube clip and a TikTok clip need different aspect ratios.
- **All clips from one section**: Diverse clips from across the source perform better than 5 clips from the same 10 minutes.
