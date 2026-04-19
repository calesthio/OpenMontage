# Publish Director - Animation Pipeline

## When To Use

Package the animation so the metadata, thumbnail concept, and platform framing reflect the actual visual system of the project.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["proposal"]["proposal_packet"]`, `state.artifacts["research"]["research_brief"]`, `state.artifacts["script"]["script"]` | Final outputs and topic framing |
| Playbook | Active style playbook | Visual naming consistency |

## Process

### 1. Match Packaging To The Animation Mode

Examples:

- diagram-heavy videos should look structured and legible,
- kinetic-type pieces should package around strong copy,
- illustrative animation should package around hero imagery.

### 2. Preserve Visual-System Truth

Store in `publish_log.metadata`:

- `animation_mode`
- `hero_frame_notes`
- `thumbnail_concept`
- `platform_notes`

### 3. Quality Gate

- metadata fits the actual animation mode,
- thumbnail concept matches the final visual system,
- exports are labeled by purpose and platform,
- the package is usable without extra manual work.

## Direct Publishing (Optional)

If `UPLOADPOST_API_KEY` is set, use the `uploadpost_publisher` tool to publish the final video directly to social platforms (Instagram, TikTok, YouTube, LinkedIn, X, Threads, Pinterest, Bluesky, Reddit, Facebook, Google Business) instead of only exporting locally. See `skills/core/social-publishing.md` for integration details.

## Common Pitfalls

- Writing generic metadata that ignores the animation style.
- Creating a thumbnail concept unrelated to the final frames.
- Mixing platform variants without clear labels.
