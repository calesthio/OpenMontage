# Publish Packager

`publish_packager` turns an approved render into a final delivery package. It is
the last-mile helper after composition, timing review, and variant selection.

It does not choose the best cut, replace review platforms, or publish to an
external site. Use `variant_manager` to decide which render is current for a
channel, then pass the approved video and sidecars into `publish_packager`.

## Operations

### `package`

Copies the final video, optional cover, and sidecar files into a package
directory, then writes `final_package_manifest.json` with paths, checksums,
duration metadata, cover provenance, reference pages, and verification warnings.

```json
{
  "operation": "package",
  "video_path": "projects/demo/renders/final.mp4",
  "cover_path": "projects/demo/assets/cover.jpg",
  "output_dir": "projects/demo/final/final-v1",
  "project_id": "demo",
  "variant_id": "final-v1",
  "channel": "landing_page",
  "cover_mode": "replace_first_frame",
  "extra_files": [
    { "path": "projects/demo/artifacts/variant_review_notes.json", "role": "variant_review_notes" }
  ],
  "reference_files": [
    { "path": "projects/demo/reviews/visual-timing/review.html", "role": "visual_timing_review_page" },
    { "path": "projects/demo/reviews/tts-lab/compare.html", "role": "tts_segment_review_page" }
  ]
}
```

`cover_mode="replace_first_frame"` replaces only the first visible video frame
with the cover and keeps the original audio timing.

`extra_files` are copied into the package. Use `reference_files` for local HTML
review pages that depend on adjacent images, audio, or other assets; they stay
at their original path so their embedded media still works.

Set `require_timing_qa=true` for final packages whose narration, subtitles,
screen states, or motion timing changed materially. The package will only pass
when a Timing QA artifact is attached through `extra_files` or
`reference_files` using a role such as `visual_timing_review_page`,
`visual_timing_annotated_review`, or `timing_qa_page`.

Packaging also writes `FINAL_PACKAGE.md`, a standard package summary with
absolute paths for the video, cover, copied files, reference pages, and
checksums. Prefer this over adding ad hoc archive-manifest sidecars.

### `review`

Creates a local confirmation page for the package:

- `final_package_review.html`
- `final_package_review.md`
- `final_package_review.json`

The page embeds the packaged video, cover, copied file list, reference page
list, checksums, Timing QA status, verification status, and copy-path shortcuts. It is a lightweight
handoff check: if something is wrong, tell the agent what to adjust and rerun
packaging. The UI language can be set with `language`, or left as `auto` to
infer Chinese/English from captions, script sidecars, references, and package
metadata.

```json
{
  "operation": "review",
  "manifest_path": "projects/demo/final/final-v1/final_package_manifest.json",
  "review_output_dir": "projects/demo/final/final-v1/review",
  "language": "auto"
}
```

### `annotate`

Optionally records a pasted package review JSON as
`final_package_review_notes.json` and returns the next workflow step. This is
kept for teams that want an explicit package approval trail; the default local
confirmation page does not require it.

```json
{
  "operation": "annotate",
  "review_payload": {
    "version": "1.0",
    "run_id": "demo-landing-page-final-v1-package-review",
    "manifest_path": "projects/demo/final/final-v1/final_package_manifest.json",
    "decision": "NEEDS_REVISION",
    "notes": "Use the approved cover image before delivery."
  }
}
```

Result behavior:

- `APPROVED` -> `review_complete=true`, `next_operation=deliver_or_publish`
- `NEEDS_REVISION` -> `review_complete=false`, `next_operation=repackage_final`
- `WRONG_PACKAGE` -> `review_complete=false`, `next_operation=rebuild_package_inputs`

After a package is revised, run `package` and `review` again. If a team uses
explicit package approvals, repeat `annotate` until it records `APPROVED`;
otherwise the local confirmation page is enough for a human to spot issues and
tell the agent what to adjust.

## Relationship To Variant Manager

`variant_manager` answers: "Which candidate render is the approved version for
this channel?"

`publish_packager` answers: "Is the final delivery package complete and ready to
hand off?"

The recommended flow is:

1. Generate one or more render candidates.
2. Use `variant_manager review` and `annotate` until a candidate is approved.
3. Pass the approved candidate's package inputs into `publish_packager package`.
4. Use `publish_packager review` to inspect the final video, cover, copied
   sidecars, and reference pages.
5. If anything is wrong, adjust the inputs and rerun `package` + `review`;
   otherwise deliver or publish the package.
