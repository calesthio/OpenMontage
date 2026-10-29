---
name: youtube-publishing-analytics
description: Use for YouTube Data API integration, upload manifests, title/description/tags/category/thumbnails/playlists, upload state management, quota handling, analytics ingestion, CTR and retention analysis, and controlled experiments.
---

# Publishing and analytics

## Publishing
- Prefer official YouTube Data API documentation and current API client libraries.
- Keep OAuth secrets outside the repository, logs and generated manifests.
- Use least-privilege scopes and document required permissions.
- Track API quota and rate limits; implement backoff and resumable uploads where supported.
- Default to draft or unlisted upload preparation. Public publishing requires explicit human approval in the current task.
- Do not auto-delete, mass-publish or modify live channel settings without explicit approval.
- Store title, description, thumbnail, language, category and visibility in a validated manifest.
- Keep states explicit: DRAFT, QA_PASSED, AWAITING_APPROVAL, UPLOADING, UPLOADED_UNLISTED, PUBLIC_APPROVED, FAILED.
- Never log tokens, authorization headers or private channel data.

## Analytics
- Distinguish impressions, click-through rate, views, average view duration, watch time and retention.
- Compare videos to the channel's own baseline and account for format, topic and publication age.
- Do not claim causal effects from a single video. Use controlled tests when possible.
- Avoid clickbait and spam tactics; optimize for viewer satisfaction and truthful packaging.
- Store data source, retrieval time, time window and API limitations.
