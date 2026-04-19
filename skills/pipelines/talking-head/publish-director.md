# Publish Director — Talking Head Pipeline

## When to Use

You have a render report with the final video. Your job is to prepare metadata, thumbnails, and an export package for publishing.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | Render report, Brief | Video file and context |

## Process

### Step 1: Generate Metadata

Create platform-specific metadata:
- **Title**: Based on the brief's title and hook
- **Description**: Summary of the content with relevant keywords
- **Tags**: Derived from brief's key_points
- **Chapters**: From script section timestamps

### Step 2: Thumbnail Concept

Describe or generate a thumbnail:
- Extract a compelling frame from the footage (if frame_sampler available)
- Add text overlay concept (title or key stat)

### Step 3: Package Export

Create the export directory:
- Video file
- Metadata JSON
- Description text file
- Chapter markers
- Thumbnail concept

### Step 4: Build Publish Log

Document the publish event with platform, status (draft), and export path.

### Step 5: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Metadata quality** | Is the title compelling and description informative? |
| **Completeness** | Is the export package complete? |

### Step 6: Submit

Validate the publish_log against the schema and persist via checkpoint.

## Direct Publishing (Optional)

If `UPLOADPOST_API_KEY` is set, use the `uploadpost_publisher` tool to publish the final video directly to social platforms (Instagram, TikTok, YouTube, LinkedIn, X, Threads, Pinterest, Bluesky, Reddit, Facebook, Google Business) instead of only exporting locally. See `skills/core/social-publishing.md` for integration details.
