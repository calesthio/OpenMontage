# QA Director - Business Documentary Pipeline

## When To Use

Stage 11 of 12. You measure the final file and produce a `qa_report` that
either clears the film for publication or stops it. QA is a measurement
activity, not an opinion.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact in | `render_report` (validated) | The file to check |
| Schema | `schemas/artifacts/qa_report.schema.json` | Output validation |
| Registry | `composition_validator`, `visual_qa`, `audio_probe` (optional: `frame_sampler`, `scene_detect`, `transcriber`, `audio_energy`) | Measurement tools |
| Lib | `lib/artifact_ids.resolve_all()` | Cross-artifact integrity |

## Process

### 1. Deterministic gates block release

Each gate records `measured`, `threshold`, `status` and the `evidence` command
or artifact that produced the measurement:

- **schema** — every artifact validates against its schema;
- **reference** — every `evidence_id` / `source_id` / `scene_id` / `asset_id`
  resolves (`lib.artifact_ids.resolve_all`);
- **license** — every media file has provenance and a usable license;
- **technical** — ffprobe sees the expected streams/codecs; FFmpeg decodes the
  whole file without error; duration, resolution and FPS are in tolerance;
- **audio** — no digital silence, speech level adequate, nothing clips;
- **visual** — no long black or frozen frames; every scene has a visual;
- **subtitle** — subtitles present, inside frame, in sync with the audio.

A failed deterministic gate means `status: "fail"` and a non-empty
`blocking_failures`.

### 2. Semantic checks are scored and thresholded

Key factual scenes match the narration; clips are not over-repeated; no
unverified specific visual claim; diagrams agree with their data; no era,
place, scale or action mismatch; the script explains something original.

Record `summary.semantic_score` against `summary.semantic_threshold`.

### 3. Measure the final file, not a helper class

Never claim "QA passed" because a tool's unit test passed or because a
checkpoint says `completed`. The measurement must reference the output file
that will be published.

### 4. If a check cannot run, say so

`status: "skipped"` with a reason. `status: "blocked"` for the whole report
when the file or a required tool is missing — an unrun gate is never a pass.

### 5. Quality gate

- Every check has a measured value, a threshold and evidence.
- `summary` counts add up.
- `status` is `pass` only when every deterministic gate passed and the
  semantic score cleared its threshold.
- `blocking_failures` lists the check_ids that must be fixed.

## Common Pitfalls

- Averaging away a single failed gate.
- Sampling one middle frame and calling the visual check done.
- Marking a missing-ffmpeg check as "pass (not applicable)".
- Publishing with an unresolved evidence ID because "it's just a citation".

---

## Checkpoint Note

`qa` is auto-approved (`human_approval_default: false`), but a `fail` or
`blocked` status stops the pipeline: the run does not reach `publish`.
