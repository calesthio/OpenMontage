---
name: heygen
description: |
  [DEPRECATED] Use `create-video` for prompt-based video generation or `avatar-video` for precise avatar/scene control. This legacy skill combines both workflows — the newer focused skills provide clearer guidance.
homepage: https://docs.heygen.com/reference/generate-video-agent
allowed-tools: mcp__heygen__*
metadata:
  openclaw:
    requires:
      env:
        - HEYGEN_API_KEY
    primaryEnv: HEYGEN_API_KEY
---

# HeyGen API (Deprecated)

> **This skill is deprecated.** Use the focused skills instead:
> - **`create-video`** — Generate videos from a text prompt (Video Agent API)
> - **`avatar-video`** — Build videos with specific avatars, voices, scripts, and scenes (v2 API)

This skill remains for backward compatibility but will be removed in a future release.

> **Browser alternative:** `heygen_browser_video` uses Playwright to automate the HeyGen web UI, consuming subscription credits instead of API credits. See `skills/tools/browser-tools.md`.

---

AI avatar video creation API for generating talking-head videos, explainers, and presentations.

## Tool Selection

If HeyGen MCP tools are available (`mcp__heygen__*`), **prefer them** over direct HTTP API calls — they handle authentication and request formatting automatically.

| Task | MCP Tool | Fallback (Direct API) |
|------|----------|----------------------|
| Generate video from prompt | `mcp__heygen__generate_video_agent` | `POST /v1/video_agent/generate` |
| Check video status / get URL | `mcp__heygen__get_video` | `GET /v2/videos/{video_id}` |
| List account videos | `mcp__heygen__list_videos` | `GET /v2/videos` |
| Delete a video | `mcp__heygen__delete_video` | `DELETE /v2/videos/{video_id}` |

If no HeyGen MCP tools are available, use direct HTTP API calls with `X-Api-Key: $HEYGEN_API_KEY` header as documented in the reference files.

## Default Workflow

**Prefer Video Agent** for most video requests.
Always use [prompt-optimizer.md](references/prompt-optimizer.md) guidelines to structure prompts with scenes, timing, and visual styles.

**With MCP tools:**
1. Write an optimized prompt using [prompt-optimizer.md](references/prompt-optimizer.md) → [visual-styles.md](references/visual-styles.md)
2. Call `mcp__heygen__generate_video_agent` with prompt and config (duration_sec, orientation, avatar_id)
3. Call `mcp__heygen__get_video` with the returned video_id to poll status and get the download URL

**Without MCP tools (direct API):**
1. Write an optimized prompt using [prompt-optimizer.md](references/prompt-optimizer.md) → [visual-styles.md](references/visual-styles.md)
2. `POST /v1/video_agent/generate` — see [video-agent.md](references/video-agent.md)
3. `GET /v2/videos/<id>` — see [video-status.md](references/video-status.md)

Only use v2/video/generate when user explicitly needs:
- Exact script without AI modification
- Specific voice_id selection
- Different avatars/backgrounds per scene
- Precise per-scene timing control
- Programmatic/batch generation with exact specs

## Quick Reference

| Task | MCP Tool | Read |
|------|----------|------|
| Generate video from prompt (easy) | `mcp__heygen__generate_video_agent` | [prompt-optimizer.md](references/prompt-optimizer.md) → [visual-styles.md](references/visual-styles.md) → [video-agent.md](references/video-agent.md) |
| Generate video with precise control | — | [video-generation.md](references/video-generation.md), [avatars.md](references/avatars.md), [voices.md](references/voices.md) |
| Check video status / get download URL | `mcp__heygen__get_video` | [video-status.md](references/video-status.md) |
| Add captions or text overlays | — | [captions.md](references/captions.md), [text-overlays.md](references/text-overlays.md) |
| Transparent video for compositing | — | [video-generation.md](references/video-generation.md) (WebM section) |
| Use with Remotion | — | [remotion-integration.md](references/remotion-integration.md) |

## Reference Files

### Foundation
- [references/authentication.md](references/authentication.md) - API key setup and X-Api-Key header
- [references/quota.md](references/quota.md) - Credit system and usage limits
- [references/video-status.md](references/video-status.md) - Polling patterns and download URLs
- [references/assets.md](references/assets.md) - Uploading images, videos, audio

### Core Video Creation
- [references/avatars.md](references/avatars.md) - Listing avatars, styles, avatar_id selection
- [references/voices.md](references/voices.md) - Listing voices, locales, speed/pitch
- [references/scripts.md](references/scripts.md) - Writing scripts, pauses, pacing
- [references/video-generation.md](references/video-generation.md) - POST /v2/video/generate and multi-scene videos
- [references/video-agent.md](references/video-agent.md) - One-shot prompt video generation
- [references/prompt-optimizer.md](references/prompt-optimizer.md) - Writing effective Video Agent prompts (core workflow + rules)
- [references/visual-styles.md](references/visual-styles.md) - 20 named visual styles with full specs
- [references/prompt-examples.md](references/prompt-examples.md) - Full production prompt example + ready-to-use templates
- [references/dimensions.md](references/dimensions.md) - Resolution and aspect ratios

### Video Customization
- [references/backgrounds.md](references/backgrounds.md) - Solid colors, images, video backgrounds
- [references/text-overlays.md](references/text-overlays.md) - Adding text with fonts and positioning
- [references/captions.md](references/captions.md) - Auto-generated captions and subtitles

### Advanced Features
- [references/templates.md](references/templates.md) - Template listing and variable replacement
- [references/photo-avatars.md](references/photo-avatars.md) - Creating avatars from photos
- [references/webhooks.md](references/webhooks.md) - Webhook endpoints and events

### Integration
- [references/remotion-integration.md](references/remotion-integration.md) - Using HeyGen in Remotion compositions
