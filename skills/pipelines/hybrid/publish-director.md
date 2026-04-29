# Publish Director - Hybrid Pipeline

## When To Use

Package the hybrid outputs so the hero cut and its derivatives stay organized and the source/support mix remains clear.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Final outputs and hybrid framing |
| Playbook | Active style playbook | Tone consistency |

## Process

### 1. Distinguish Master And Variants

Group outputs as:

- master cut,
- short-form derivatives,
- format variants,
- chaptered or contextual variants.

### 2. Preserve Source Truth In Packaging

If the project uses interview footage, screen recording, or product footage as its anchor, the metadata should reflect that instead of packaging it like a pure generated piece.

### 3. Store Cross-Output Notes

Recommended metadata keys:

- `master_output`
- `derivative_outputs`
- `source_mix_notes`
- `platform_copy_map`

### 4. Quality Gate

- master and variants are clearly labeled,
- metadata matches the true source mix,
- export folders are organized by purpose,
- the package is ready to use without manual cleanup.

## Direct Publishing (Optional)

If `UPLOADPOST_API_KEY` is set, use the `uploadpost_publisher` tool to publish the final video directly to social platforms (Instagram, TikTok, YouTube, LinkedIn, X, Threads, Pinterest, Bluesky, Reddit, Facebook, Google Business) instead of only exporting locally. See `skills/core/social-publishing.md` for integration details.

## Common Pitfalls

- Hiding which output is the hero cut.
- Packaging a source-led project like a generic generated asset.
- Losing platform-specific copy and labeling across variants.
