# Hosted-Lite Proposal Director

This skill exists only for quarantined hosted-lite runs. The production hosted
Ray path must use the StageExecutor-backed `cinematic` pipeline. Hosted-lite is
a degraded mode and must say so in every proposal artifact.

## Runtime Contract

You must create a visible `render_runtime_selection` decision. Present both
composition runtimes by name: `remotion` and `hyperframes`. If hosted-lite is
locked to one runtime for safety, state the constraint explicitly instead of
silently defaulting.

Required proposal notes:

- `pipeline_type: hosted-lite`
- `degraded_mode: true`
- `not_production_cinematic_pipeline: true`
- Explain that hosted-lite skips the real OpenMontage StageExecutor planning
  directors and is not acceptable for normal Ray production work.

