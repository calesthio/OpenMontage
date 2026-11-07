# youtube-publishing-analytics — STUB (not an active skill)

**Status:** STUB ONLY. Not installed as an active Kilo skill. No OAuth, no YouTube Data API calls, no network to YouTube.

**Activation condition:** After the first published video; manual publish only; no OAuth now.

**Purpose (deferred):** YouTube Data API integration, upload manifests, title/description/tags/category/thumbnails/playlists, upload state management, quota handling, analytics ingestion, CTR and retention analysis, and controlled experiments.

**Constraints (from plan v3.2 zero-secrets rule + M1):**
- No OAuth credentials in repo, logs, or manifests.
- No automatic publish, schedule, delete, or channel mutation.
- Publication requires explicit human approval in the current task.
- Max 3 runtime components in v1; this stub adds zero runtime components.

**Source reference:** `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` embedded resource `02-youtube-factory-kilo-kit/skills/youtube-publishing-analytics/SKILL.md` (reference only; not materialized as active skill).

**Owner decision needed:** Whether and when to activate this skill; which MCP/adapter (if any) to use for YouTube Data API; credential storage path outside repo.
