# Publish Director - Screen Demo Pipeline

## When To Use

Package the finished demo so the user can publish it quickly and so the metadata reflects the actual task, result, and tools involved.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Optional schema | `schemas/artifacts/final_package_manifest.schema.json` | Final package file list, cover, checksum, and verification metadata |
| Optional tool | `publish_packager` | Copy final assets, optionally replace the first video frame with the cover, and write a final package manifest |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Video, brief, and sections |
| Playbook | Active style playbook | Thumbnail and copy tone |

## Process

### 1. Build Searchable Metadata

Screen-demo titles work best when they combine:

- task,
- tool,
- outcome.

Good patterns:

- `How to deploy on Vercel from Next.js`
- `Fix CORS in React + Express`
- `Set up GitHub Actions for Python tests`

Pull keywords from:

- software names,
- frameworks,
- commands,
- exact error text,
- outcome words such as `deploy`, `fix`, `connect`, `publish`, `ship`.

### 2. Use Chapter Markers As Navigation

Use script sections as the basis for chapter markers and packaging bullets. A good screen-demo package makes the workflow skimmable before the user even presses play.

### 3. Thumbnail Strategy

If a thumbnail concept is needed, it should show:

- the result state, not a generic setup screen,
- the recognizable tool surface,
- 2-4 words of value text.

Store the concept in `publish_log.metadata.thumbnail_concepts`.

Read `script.cover_policy` before creating cover assets. If it is missing,
infer it from the distribution context: page embeds, product demos, tutorials,
and external sharing usually need a cover; internal drafts and raw capture
tests usually do not.

If the policy requires a cover, use `cover_direction` as the thumbnail/poster
brief and compare it against the finished render. The final cover may be
generated from that direction, selected from a strong rendered frame, or
supplied by the user. If `user_decision` requests review, show the final cover
before final handoff or publish.

### 4. Package By Platform

Prepare:

- video file,
- title and description/caption,
- chapter markers where relevant,
- keyword list,
- thumbnail concept notes.

For developer or product-demo content, also package:

- commands shown,
- software/version mentions,
- error terms if it is a troubleshooting demo.

Use `publish_packager` when available to produce a final package directory and
`final_package_manifest.json`. If `cover_policy.first_frame_mode` is
`replace_first_frame`, use `cover_mode: "replace_first_frame"` so the cover
becomes the first visible frame without adding extra time before the original
audio.

### 5. Quality Gate

- metadata names the real tool and task,
- chapters match the actual rendered flow,
- export folders are clean and reusable,
- copy is tailored to the platform instead of duplicated.

## Common Pitfalls

- Publishing with generic titles that omit the actual software or task.
- Using the same caption for YouTube, LinkedIn, and short-form social.
- Building chapter markers from the script without checking the render.
