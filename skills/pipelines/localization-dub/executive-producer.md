# Executive Producer — Localization Dub Pipeline

## When to Use

You are the **Executive Producer (EP)** for a localization/dubbing project. You orchestrate the pipeline serially with quality gates focused on **translation accuracy, timing preservation, lip-sync quality, and per-locale consistency**.

**No pre-production stages.** Source video exists in one language. The EP manages the complexity of producing multiple language variants while preserving the original's timing and quality.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/localization-dub.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |

## Cumulative State

```
EP_STATE:
  pipeline: localization-dub
  playbook: <selected>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Localization-specific
  source_language: null
  target_languages: []
  dub_mode_per_locale: {}      # language → subtitle_only / dub_audio_only / lip_synced / hybrid_covered
  glossary_terms: []           # protected terms that must not be translated
  timing_drift_tolerance: 0.5  # seconds

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
CHECK: Scope definition
  - Source and target languages explicit?
  - Deliverable mode clear per language (subtitle_only / dub_audio_only / lip_synced / hybrid_covered)?
  - Glossary and protected terms captured?
  - Review requirements noted?
```

### After SCRIPT stage:
```
CHECK: Transcript truth
  - Source transcript accurate and timestamped?
  - Glossary terms preserved in translations?
  - Translated scripts reviewable before synthesis?
  - Duration estimates per language reasonable (some languages expand 20-30%)?
```

### After SCENE_PLAN stage:
```
CHECK: Dub mode feasibility
  - Is the chosen dub mode realistic per locale?
  - Lip-sync limited to shots that can support it (front-facing, clear mouth)?
  - Timing drift risks mapped (which languages will run long)?
  - On-screen text replacement planned if needed?
```

### After ASSETS stage:
```
CHECK: Locale asset completeness
  - Subtitle files exist for every target language?
  - Dubbed audio generated for every dub-mode language?
  - TTS voice quality acceptable for each language?
  - Lip-sync applied only where planned?
  - Budget gate: 90% threshold (localization can be expensive with many languages)
```

### After EDIT stage:
```
CHECK: Timing preservation
  - Source structure preserved unless timing forces change?
  - CTA and legal copy survive translation?
  - Language variants organized consistently?
  - Timing drift within tolerance per segment?
```

### After COMPOSE stage:
```
CHECK: Per-locale validation
  - Each language output rendered and intelligible?
  - Subtitle timing matches speech in each locale?
  - Version labeling unambiguous (language code in filename)?
  - Audio quality consistent across locales?
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Scope, languages, dub modes | Revise |
| G2 | script | Transcript accuracy, glossary, translations | Revise |
| G3 | scene_plan | Dub mode feasibility, timing risks | Revise |
| G4 | assets | Locale completeness, TTS quality, budget | Revise |
| G5 | edit | Timing preservation, structure | Revise |
| G6 | compose | Per-locale probe, subtitle timing | Revise or send-back |
| G7 | publish | Locale packaging, metadata | Revise |
| FINAL | all | Translation quality, timing, lip-sync | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | manifest `orchestration.max_revisions_per_stage` |
| Max send-backs per stage pair | 1 (guidance; no manifest field) |
| Max total send-backs | manifest `orchestration.max_send_backs` |
| Max total budget | The run budget from `tools/cost_tracker.py::resolve_budget_usd`: the amount the user approved (record it with `python -m tools.cost_tracker budget <project-id> --usd <amount>`), else manifest `orchestration.budget_default_usd` (set higher than most pipelines — localization is costlier) capped at `config.yaml` `budget.total_usd`. Enforcement follows `config.yaml` `budget.mode`: `observe` records only, `warn` records and flags overruns, `cap` refuses a paid call that does not fit the remaining budget |
| Max total wall-time | manifest `orchestration.max_wall_time_minutes` |

Read the manifest-backed values from `pipeline_defs/localization-dub.yaml` at the start of the run; never substitute numbers of your own.

After any limit is hit: **proceed with warnings**, never block indefinitely. A limit never approves a human-gated stage (any stage with `human_approval_default: true` in the manifest): write `awaiting_human` with the warnings attached, end the turn, and let the user decide.

## Common Pitfalls

- **Ignoring language expansion**: Some languages are 20-30% longer than English. The dubbed audio won't fit the original timing without adjustments.
- **Lip-sync on every shot**: Only apply lip-sync to front-facing, clear-mouth shots. Side angles and distant shots don't need it.
- **Translating protected terms**: Brand names, product names, and technical terms in the glossary must stay in the original language.
- **Inconsistent locale labeling**: Use ISO language codes in filenames. "Spanish" is ambiguous (es-ES vs es-MX).
- **Degrading source video**: Re-encoding the source video for each locale should preserve quality. Never downgrade resolution.
