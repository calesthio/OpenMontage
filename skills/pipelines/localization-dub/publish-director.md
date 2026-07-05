# Publish Director - Localization Dub Pipeline

## When To Use

Package the completed localization outputs so downstream teams can find the right video, subtitle, and metadata bundle for each language without manual cleanup.

## Process

### 1. Package By Locale

Each language package should clearly separate:

- video output,
- subtitle files,
- transcript or approved script copy,
- review notes,
- metadata.

### 2. Keep Naming Precise

Recommended metadata keys:

- `locale`
- `language_name`
- `deliverable_mode`
- `subtitle_included`
- `review_owner`

### 3. Preserve Review Context

If a language output has pronunciation caveats, timing warnings, or missing lip sync, keep that note in the published package.

### 4. Quality Gate

- locale packages are clearly labeled,
- metadata matches the actual treatment,
- supporting text assets are present,
- warnings and review notes are not lost.

## Common Pitfalls

- Shipping localized videos without the matching subtitle or transcript files.
- Mixing audio-dub and subtitle-only variants under the same generic filename.
- Removing the QA notes that explain known issues.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
