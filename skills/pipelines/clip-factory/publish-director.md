# Publish Director - Clip Factory Pipeline

## When To Use

This stage packages the clip batch into a distribution plan. The goal is not just exported files. The goal is a usable content engine.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Outputs, rankings, and goals |
| Playbook | Active style playbook | Brand voice |

## Process

### 1. Lead With The Strongest Clip

Do not schedule by chronology. Schedule by ranking.

The first published clip should usually be:

- the strongest hook,
- the cleanest standalone clip,
- the clip most aligned with the batch goal.

### 2. Tailor Copy By Platform

Each platform needs its own tone and packaging:

- TikTok / Reels: direct, fast, hook-led
- Shorts: searchable, keyword-aware
- LinkedIn: insight-led and more professional
- X: short, punchy, opinion-friendly

### 3. Package The Batch Cleanly

Group by platform and include ready-to-paste text assets, not just video files.

### 4. Preserve Batch Truth

Store in `publish_log.metadata`:

- `clip_catalog`
- `posting_order`
- `platform_copy_map`
- `schedule_notes`

### 5. Quality Gate

- strongest clips lead the rollout,
- captions are platform-specific,
- export folders are usable without extra cleanup,
- the batch catalog clearly links ranking, file paths, and publishing intent.

## Direct Publishing (Optional)

If `UPLOADPOST_API_KEY` is set, use the `uploadpost_publisher` tool to publish the final video directly to social platforms (Instagram, TikTok, YouTube, LinkedIn, X, Threads, Pinterest, Bluesky, Reddit, Facebook, Google Business) instead of only exporting locally. See `skills/core/social-publishing.md` for integration details.

## Common Pitfalls

- Publishing the whole batch on the same day.
- Using one caption everywhere.
- Losing the rank/order logic after rendering is complete.
