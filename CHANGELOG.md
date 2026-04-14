# Changelog

All notable changes to OpenMontage are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-04-14

### Added

#### New Tools

**`tools/video/_google_flow_base.py`**
- Internal shared Playwright automation helpers for Google Flow browser sessions.
- Not a registered tool; do not import from outside `tools/video/`.
- Provides session management, navigation, and download helpers used by `GoogleFlowImage` and `GoogleFlowVideo`.

**`tools/video/google_flow_image.py`** — `GoogleFlowImage`
- Image generation via Google Flow (Nano Banana / Imagen 4 models).
- Capability: `image_generation` | Provider: `google_flow` | Runtime: HYBRID (Playwright + local).
- Cost: $0 (subscription credits).
- Fallback chain: `flux_image` → `imagen_image` → `dalle_image`.

**`tools/video/google_flow_video.py`** — `GoogleFlowVideo`
- Video generation via Google Flow (Veo models).
- Capability: `video_generation` | Provider: `google_flow` | Runtime: HYBRID (Playwright + local).
- Default download quality: 720p (Original Size — no upscaling delay).
- Cost: $0 (subscription credits).
- Fallback chain: `kling_video` → `higgsfield_video` → `minimax_video`.

**`tools/video/magic_hour_video.py`** — `MagicHourVideo`
- Cinematic video generation via Magic Hour REST API.
- Capability: `video_generation` | Provider: `magic_hour` | Runtime: API.
- Cost: ~$0.04/sec.
- Fallback chain: `kling_video` → `higgsfield_video` → `minimax_video`.

**`tools/video/heygen_browser_video.py`** — `HeyGenBrowserVideo`
- Avatar video generation via HeyGen browser automation (subscription tier).
- Capability: `video_generation` | Provider: `heygen_browser` | Runtime: HYBRID (Playwright + local).
- Cost: $0 (subscription credits).
- Fallback: `heygen_video` (API).

**`tools/graphics/giphy_search.py`** — `GiphySearch`
- GIF search via Giphy API.
- Capability: `gif_search` | Provider: `giphy` | Runtime: API.
- Cost: free.
- Returns GIF and MP4 URLs; optional local download.

#### New Base Infrastructure

**`tools/base_tool.py`** — `BaseTool.execute_safe(inputs)`
- New method on `BaseTool`. Should be preferred over `execute()` for all cloud generation tools.
- Dynamic timeout: `max(30s, min(estimate_runtime × 2, 600s))`.
- On timeout or unrecoverable error, auto-falls back to the first available tool in `fallback_tools[]`.

### Changed

**`AGENT_GUIDE.md`**
- Added `gif_search` capability family entry.
- Added `"browser"` qualifier to the `video_generation` capability description.
- Added one-line note on `execute_safe()` for tool authors.
- Removed 4 tutorial sections that were migrated to dedicated skill files.

**`PROJECT_CONTEXT.md`**
- Added browser subscription tool pattern documentation.
- Added `execute_safe()` architecture note.
- Updated `video_selector` routing example.
- Added `estimate_runtime()` guidance under "When Building New Tools".
- Added "Browser tool pattern (Playwright)" subsection.

### Known Issues

- **`google_flow_video.py`**: Default download quality in `execute()` may still reference `"1080p"` instead of `"720p"`. Fix pending. (`720p` = Original Size = instant download, no upscaling delay.)
- **`heygen_browser_video.py`**: Session check uses `[data-testid='user-menu']` selector, which may not exist in all HeyGen UI versions.
- **`magic_hour_video.py`**: Endpoint not smoke-tested live yet.
- **Video smoke test**: Veo Fast 720p generation needs one retest after the 720p default fix is applied.
