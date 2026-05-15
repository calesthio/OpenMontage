# Variant Manager

Variant Manager is a lightweight project ledger for deliverable variants. It
does not store media bytes, replace review platforms, or choose the best cut
automatically. It records which source artifacts produced each deliverable,
which variants are current for named channels, and why older variants were
kept or archived.

Use it after a render candidate exists, and again whenever a candidate is
approved, superseded, or published.

Do not record every scratch render. Record complete candidates that may be
kept, compared, handed off, or published. Section previews, audio trials, and
timing contact sheets usually belong in their own experiment folders unless
they become part of the final candidate's inputs or review evidence.

## Artifact

The canonical artifact is `variant_manifest`, validated by:

```text
schemas/artifacts/variant_manifest.schema.json
```

A typical project stores it at:

```text
projects/<project-id>/artifacts/variants.json
```

## Minimal Manifest

```json
{
  "version": "1.0",
  "project_id": "demo-project",
  "current": {
    "handoff_intro": "v3-handoff",
    "standalone_teaser": "v5-standalone"
  },
  "variants": [
    {
      "id": "v3-handoff",
      "name": "Handoff intro",
      "status": "approved",
      "purpose": "handoff_intro",
      "created_at": "2026-05-12T00:00:00+00:00",
      "lineage": {
        "parent": "v2",
        "change_summary": "Switch ending to live handoff."
      },
      "inputs": {
        "script": "artifacts/script.json",
        "audio": "assets/audio/narration.mp3",
        "captions": "artifacts/captions.json",
        "render_props": "render-inputs/props.json"
      },
      "outputs": {
        "video": "renders/final-handoff.mp4",
        "duration_seconds": 160.2,
        "profile": "youtube_landscape",
        "speed": 1.25
      },
      "review": {
        "decision": "keep",
        "notes": "Approved for the live presentation handoff.",
        "known_issues": []
      },
      "tags": ["handoff", "approved", "1.25x"]
    }
  ]
}
```

## Tool Operations

`variant_manager` supports:

- `init`: create an empty manifest.
- `add`: add or update a variant record.
- `list`: list variants, with optional status/purpose/tag filters.
- `show`: show one variant and the channels where it is current.
- `promote`: mark a variant as current for a named channel.
- `archive`: archive a non-current variant.
- `compare`: compare the tracked inputs, outputs, review state, and lineage of
  two variants.
- `review`: generate a local HTML/Markdown/JSON review page for the current
  set of candidate variants.
- `annotate`: apply the review JSON pasted back from the review page. Approved
  selections are promoted for the requested channel; revision notes are written
  back to the selected variant without promoting it; "none of these" requests
  are recorded as a new-variant request.
- `validate`: validate schema, duplicate ids, and current-channel references.

## Workflow Placement

The tool is useful after `compose` or `final_review` creates a render candidate.
The Composer or Publisher can then record:

- the input artifacts used by the render;
- the output path and technical metadata;
- the human or agent review decision;
- the current channel if the variant is approved.

This keeps the project answerable when someone asks: "which file is the current
delivery version, and why?"

When a project has multiple delivery contexts, use named channels in `current`
instead of overwriting one global winner. Examples:

- `live_handoff_intro`
- `standalone_teaser`
- `vertical_short`
- `client_review`

Promote a variant only after it has passed the relevant human or agent review.
Archive a variant only after another variant has replaced it for every current
channel where it was used.

## Human Review Loop

Use `review` when several render candidates are ready and a human needs to pick
the delivery variant:

```json
{
  "operation": "review",
  "manifest_path": "projects/demo/artifacts/variants.json",
  "channel": "standalone_teaser",
  "output_dir": "projects/demo/reviews/variant-round-1"
}
```

Open the generated `variant_review.html`, choose one variant, or choose "none of
these" and describe what should change. The page copies a small review JSON
payload. Pass that payload to `annotate`:

```json
{
  "operation": "annotate",
  "manifest_path": "projects/demo/artifacts/variants.json",
  "review_payload": {
    "version": "1.0",
    "run_id": "demo-standalone_teaser-variant-review",
    "channel": "standalone_teaser",
    "selected_variant_id": "v3-standalone",
    "decision": "APPROVED",
    "notes": ""
  }
}
```

`annotate` returns a workflow hint:

- `review_complete=true`, `next_operation=package_or_publish`: the selected
  variant is now current for the channel and downstream packaging can proceed.
  The result also includes `package_inputs` with the approved `video_path`,
  `project_id`, `variant_id`, `channel`, review notes, and any existing sidecar
  files that can be passed to the final package helper.
- `review_complete=false`, `next_operation=revise_variant`: the selected
  variant has human notes and should be revised into a new candidate before the
  next review round.
- `review_complete=false`, `next_operation=add_variant`: none of the candidates
  were accepted, so the workflow should create a new candidate from the review
  notes.

This keeps Variant Manager focused on decision history. It does not render the
revision itself and does not package final files; those steps remain with the
composer and final package helper.
