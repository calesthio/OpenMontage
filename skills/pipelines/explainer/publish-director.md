# Publish Director — Explainer Pipeline

## When to Use

You are the Publisher for a generated explainer video. You have a `render_report` with the final video file. Your job is to prepare the video for distribution: generate SEO metadata, create thumbnails, package exports, and log the publish event.

This is where a great video reaches its audience. Without proper metadata and packaging, even the best content gets buried.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["proposal"]["proposal_packet"]`, `state.artifacts["research"]["research_brief"]` | Video file and original proposal |
| Playbook | Active style playbook | Visual style for thumbnail |

## Process

### Step 1: Gather Context

Collect everything needed for metadata:
- **Proposal packet**: title, hook, key points, target platform, tone
- **Render report**: output path, duration, resolution
- **Script**: section summaries for description/chapters

### Step 2: Generate SEO Metadata

**Title** (max 60 characters for YouTube):
- Include the primary keyword from the proposal packet
- Lead with a hook or number
- Avoid clickbait but be compelling
- Examples: "Vector Databases Explained in 60 Seconds" > "About Vector Databases"

**Description** (first 150 chars are critical — shown in search):
- Opening line: restate the hook with the main value proposition
- Body: key topics covered, with relevant keywords naturally included
- Chapters: timestamp markers for each major section (from script sections)
- Call to action: subscribe/like/follow
- Links: relevant resources mentioned in the video

**Tags/Keywords** (platform-dependent):
- 5-10 specific tags derived from proposal packet's key_points
- Mix broad and specific: "machine learning" + "vector database tutorial"
- Include the topic, format ("explainer"), and related terms

**Hashtags** (for social platforms):
- 3-5 relevant hashtags
- Mix trending and niche

**Comment-keyword CTA** (only when the script asks viewers to comment a word, e.g. "comment GUIDE for the checklist"):
- Repeat the exact on-screen word in the first line of the Reels/TikTok/Shorts caption, before the "more" cut
- Record it as `engagement_cta`: `keyword` (required), `promise`, `caption_line`, `dm_message` (a draft message that delivers the promise), `public_reply`, `platforms`
- Don't invent a CTA the script doesn't have

### Step 3: Generate Thumbnail Concept

Describe a thumbnail that:
1. Uses the playbook's visual style
2. Features the video's core concept visually
3. Includes 3-5 words of text (the hook or key stat)
4. Has high contrast and is readable at small sizes
5. Uses the playbook's accent colors for text

```json
{
  "thumbnail": {
    "concept": "Split screen: left side shows slow SQL query (red X), right shows fast vector search (green check). Large text: '100x FASTER'",
    "text_overlay": "100x FASTER",
    "style_notes": "Use playbook accent colors, bold Inter font, dark background"
  }
}
```

*Note: Actual thumbnail generation happens via image_selector if available, otherwise it's a concept for manual creation.*

### Step 4: Create Chapter Markers

From the script sections, generate YouTube-style chapters:

```
0:00 - Introduction
0:15 - What are Vector Databases?
0:45 - How Embeddings Work
1:20 - The Search Algorithm
1:55 - Real-World Examples
2:30 - When to Use Vector DBs
```

Each chapter maps to a script section's `start_seconds`.

### Step 5: Package Export

Use the `export_bundle` tool (capability `publish`) to do the packaging
deterministically — pass it the final `video_path` (from `render_report`), the
`title`, and the metadata you prepared (`description`, `tags`, `hashtags`,
`chapters`, optional `subtitles_path` and `thumbnail_path`/`thumbnail_concept`,
and `engagement_cta` when Step 2 recorded one).
It lays out the export directory, writes the metadata files, and returns a
schema-valid `publish_log` (`status: "exported"`) in `data["publish_log"]` that
you persist as the stage artifact. Fix anything listed in `data["warnings"]`
(for example a CTA keyword missing from the caption) before the approval gate.

It produces this structure:

```
exports/
  <project_name>/
    video/
      output.mp4            # Final rendered video (subtitles.srt alongside if provided)
    metadata/
      metadata.json         # All SEO metadata
      chapters.txt          # Chapter markers
      description.txt       # Ready-to-paste description (+ chapters)
      tags.txt              # One tag per line
      engagement_cta.json   # Only when an engagement_cta was passed
    thumbnails/
      concept.json          # Thumbnail concept (or the copied thumbnail image)
```

`export_bundle` is a local, offline packager — it does not upload. A networked
publisher (e.g. a YouTube uploader) would be a separate `publish`-capability
provider. It also sends no messages: an `engagement_cta` is recorded so the
overlay, caption and DM agree. If the creator automates the DM with a
comment-to-DM tool, list that as a follow-up in the approval summary.

### Step 6: Build Publish Log

`export_bundle` already returns a schema-valid `publish_log` in `data["publish_log"]` — persist that directly rather than hand-building one. Do **not** add extra entry fields (the schema sets `additionalProperties: false`; only `platform`, `status`, `url`, `video_id`, `visibility`, `export_path`, `timestamp`, `metadata_used`, `error` are allowed). A recorded CTA lives at the top level in `metadata.engagement_cta`, not in an entry. The shape it returns:

```json
{
  "version": "1.0",
  "entries": [
    {
      "platform": "youtube",
      "status": "exported",
      "export_path": "projects/vector-db-explainer/exports",
      "timestamp": "2026-01-15T10:30:00+00:00",
      "metadata_used": {
        "title": "Vector Databases Explained in 60 Seconds",
        "description": "What vector databases are and when to use them.",
        "hashtags": ["#ai", "#vectordb"],
        "chapters": [{ "start_seconds": 0, "title": "Introduction" }]
      }
    }
  ]
}
```

### Step 7: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **SEO quality** | Would this title and description rank well for the topic? |
| **Description completeness** | Does the description include chapters, CTA, and keywords? |
| **Thumbnail concept** | Would this thumbnail stand out in a feed? |
| **Export package** | Is everything a creator needs in the export directory? |
| **Platform fit** | Is metadata tailored to the target platform? |

If any dimension scores below 3, revise.

### Step 8: Submit

Validate the publish_log against the schema and persist via checkpoint.

## Common Pitfalls

- **Generic titles**: "Video About X" loses to "X Explained in 60 Seconds" every time. Be specific and compelling.
- **No chapters**: YouTube rewards videos with chapters. Always include them.
- **Description keyword stuffing**: Write for humans first, search engines second. Natural language with keywords woven in.
- **Forgetting the CTA**: Every description should end with a call to action.
- **Wrong platform format**: YouTube descriptions differ from TikTok captions. Tailor to the target platform.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
