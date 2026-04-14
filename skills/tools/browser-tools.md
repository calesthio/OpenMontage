# Browser Tools — Operational Guide

## What Browser Tools Are

Browser tools automate the provider web UI via Playwright instead of calling an API. They consume your subscription plan credits rather than per-call API credits — cost per generation is $0 as long as your subscription is active.

Three tools currently follow this pattern:

- `heygen_browser_video` — avatar/talking-head video via HeyGen web UI
- `google_flow_video` — AI video generation via Google Flow (Veo models)
- `google_flow_image` — image generation via Google Flow (Nano Banana / Imagen models)

---

## When to Use Browser Tools vs API Tools

| Scenario | Use |
|----------|-----|
| HeyGen subscription active, want $0 per-call cost | `heygen_browser_video` |
| HeyGen API quota exhausted | `heygen_browser_video` |
| Veo-quality video at no per-clip cost | `google_flow_video` |
| Nano Banana / Imagen images at no per-image cost | `google_flow_image` |
| Batch production needing exact parameter control | API tools (more predictable) |
| CI/automated pipeline without user-attended browser | API tools (browser tools need session setup) |

---

## Per-Tool Reference

### `heygen_browser_video`

- **Capability:** `video_generation` | **Provider:** `heygen_browser` | **Runtime:** HYBRID
- **Cost:** $0 (HeyGen subscription)
- **Fallback:** `heygen_video` (API)
- **Required env:** `HEYGEN_EMAIL`, `HEYGEN_PASSWORD`
- **Key inputs:** `script` (required), `avatar_id`, `voice`, `language`, `tone`, `output_path`

### `google_flow_video`

- **Capability:** `video_generation` | **Provider:** `google_flow` | **Runtime:** HYBRID
- **Cost:** $0 (Google Flow subscription)
- **Fallback:** `kling_video` → `higgsfield_video` → `minimax_video`
- **Required env:** `GOOGLE_FLOW_EMAIL` + first-run OAuth (see `skills/meta/browser-tools-setup.md`)
- **Key inputs:** `prompt`, `model` (`veo_fast`/`veo_lite`), `aspect_ratio` (`16:9`/`9:16`), `first_frame`, `last_frame`, `ingredients`, `download_quality` (`720p` default), `output_path`

### `google_flow_image`

- **Capability:** `image_generation` | **Provider:** `google_flow` | **Runtime:** HYBRID
- **Cost:** $0 (Google Flow subscription)
- **Fallback:** `flux_image` → `imagen_image` → `dalle_image`
- **Required env:** `GOOGLE_FLOW_EMAIL` + first-run OAuth
- **Key inputs:** `prompt`, `model` (`nano_banana_pro`/`nano_banana`/`imagen_4`), `aspect_ratio`, `ingredients`, `output_path`
- `nano_banana_pro` is best for text-in-image, posters, CTAs, and typography

---

## Fallback Behavior

Browser tools auto-fall back via `execute_safe()`. No explicit fallback code is needed in pipelines — call `execute_safe(inputs)` and the tool handles degradation transparently.

---

## Session Notes

- First-time setup is required before any browser tool will work. See `skills/meta/browser-tools-setup.md`.
- Sessions persist in `~/.openmontage/` — no repeated logins after initial setup.
- Google Flow requires a manual OAuth step on first use (visible browser window opens; you complete sign-in).
