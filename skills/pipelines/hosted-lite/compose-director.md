# Hosted-Lite Compose Director

This director is only for the quarantined hosted-lite fallback path. It must
not be used for normal hosted Ray production jobs.

## Runtime Routing

Read `render_runtime` from the proposal/edit decision record and route only to
the matching renderer. HyperFrames must be named and considered: if
`hyperframes` is unavailable or intentionally deferred in hosted-lite, record
that constraint in the render report. Do not silently pick Remotion.

Hosted-lite compose outputs must:

- Label `pipeline_type: hosted-lite` or `hosted_mode: hosted-lite`.
- State that the run is degraded and did not use the production cinematic
  StageExecutor flow.
- Run automated QA gates before exposing any final render: audio presence,
  dimensions, black-edge detection, SSIM cut continuity, and duration-vs-plan.

