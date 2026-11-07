# Publish Director - Business Documentary Pipeline

## When To Use

Stage 12 of 12. You assemble the `publish_package` a human reviews before
anything is uploaded: video, title, description, chapters, sources and
credits, plus the manual-approval state. **The pipeline never uploads.**

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `qa_report` (status `pass`), `render_report` (validated) | Cleared output |
| Schema | `schemas/artifacts/publish_package.schema.json`, `publish_log.schema.json` | Output validation |
| Registry | `export_bundle` | Local packaging only |
| Lib | `lib/artifact_ids.check_publish_package()` | Credit + QA gating |

## Process

### 1. Hard gate on QA

If `qa_report.status` is `fail` or `blocked`, do not build a package. The
check exists in `lib/artifact_ids.check_publish_package()` and raises a
dangling reference for a failed QA gate.

### 2. Assemble the package

- `video`: path, measured duration, resolution, FPS, container, codecs,
  SHA-256 of the file that was actually reviewed.
- `title` and `description`: written for the platform, no claims the evidence
  does not carry.
- `chapters`: start seconds + labels, derived from the scene plan.
- `sources_credits`: one row per asset with provider, original URL, author,
  license and the exact attribution the license requires — matching the
  asset manifest. Plus `music_credit` when a track is used.
- `thumbnail`: source frame and notes (draft only; a human decides).

### 3. Record the manual approval state explicitly

`manual_approval.status` is `pending`, `approved`, `rejected` or
`not_requested`. `upload_target` stays `null` until a human sets it. Nothing
in this artifact triggers an upload, and no automatic re-upload or retry is
permitted.

### 4. Write the publish log

`publish_log` is the repo-canonical governance artifact for this stage: who
approved, when, what was reviewed, and what (if anything) was published
manually afterwards.

### 5. Package locally

Use `export_bundle` to assemble a reviewable directory: video, package JSON,
credits, and the artifact set the reviewer needs.

### 6. Quality gate

- `publish_package` and `publish_log` both validate.
- `qa_ref.status == "pass"`.
- Every `sources_credits.asset_id` resolves against the manifest.
- `manual_approval.status` is explicit; `upload_target` is `null` unless a
  human set it.
- No network upload was performed by any tool in this stage.

## Common Pitfalls

- Writing a description that restates a claim QA marked unverified.
- Crediting "stock footage" instead of the author and license.
- Recording an approval the human never gave.
- Re-uploading automatically after a failed first attempt.

---

## Gate Reminder (Binding)

`publish` gates on human approval (`human_approval_default: true`). Write the
checkpoint `status="awaiting_human"`, present the package, and **END YOUR
TURN**. The human decides what happens next — including whether anything is
uploaded at all.
