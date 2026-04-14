# Changelog

All notable changes to OpenMontage are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-04-14 (`3aa57ab`, `d7b4f1b`)

### Added

#### New Tools

**`tools/video/_google_flow_base.py`** (`3aa57ab`)
- Internal shared Playwright automation helpers for Google Flow browser sessions.
- Not a registered tool; do not import from outside `tools/video/`.
- Key exports: `launch_browser_context`, `check_session_valid`, `open_settings_panel`, `configure_image_settings`, `configure_video_settings`, `apply_camera_motion`, `wait_for_generation`, `upload_frame`, `upload_media_reference`, `open_download_submenu`, `click_download_quality`, `create_new_project`.

**`tools/video/google_flow_setup.py`** (`3aa57ab`)
- One-time session saver. Run: `python3 -m tools.video.google_flow_setup`
- Opens a visible Chrome window, completes manual Google OAuth, saves profile to `~/.openmontage/google_flow_profile/`.

**`tools/video/google_flow_image.py`** — `GoogleFlowImage` v1.2.0 (`3aa57ab`)
- Image generation via Google Flow (Nano Banana / Imagen 4 models).
- Capability: `image_generation` | Provider: `google_flow` | Runtime: HYBRID.
- Cost: $0 (subscription credits).
- Batch support: `quantity` `x1`–`x4`; all images downloaded at full-res PNG.
- Fallback chain: `flux_image` → `imagen_image` → `dalle_image`.

**`tools/video/google_flow_video.py`** — `GoogleFlowVideo` v0.5.0 (`3aa57ab`)
- Video generation via Google Flow (Veo 3.1 Fast/Lite models).
- Capability: `video_generation` | Provider: `google_flow` | Runtime: HYBRID.
- Default download quality: `720p` (Original Size — instant, no upscaling delay).
- Batch support: `quantity` `x1`–`x4`; all clips downloaded.
- Camera motion presets: `dolly_in`, `dolly_out`, `orbit_left`, `orbit_up`, `dolly_out_zoom` (applied post-generation).
- `continue_prompt` extends clip via "What happens next?".
- `first_frame`/`last_frame` mutually exclusive with `ingredients[]` (validated before browser opens).
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

- ~~**`google_flow_video.py`**: Default download quality in `execute()` referenced `"1080p"` instead of `"720p"`~~ — **Fixed** (`d7b4f1b`): line 293 now reads `"720p"`.
- **`heygen_browser_video.py`**: Session check uses `[data-testid='user-menu']` selector, which may not exist in all HeyGen UI versions.
- **`magic_hour_video.py`**: Endpoint not smoke-tested live yet.
- **Video smoke test**: Veo Fast 720p generation needs one retest.
