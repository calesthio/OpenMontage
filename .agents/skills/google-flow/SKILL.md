---
name: google-flow
description: |
  Google Flow browser automation for image (Nano Banana / Imagen 4) and video (Veo 3.1) generation. Subscription-based, $0 per generation. Requires Playwright + Google OAuth. OpenMontage tools: google_flow_image, google_flow_video.
homepage: https://labs.google/fx/tools/flow
metadata:
  openclaw:
    requires:
      env:
        - GOOGLE_FLOW_EMAIL
    primaryEnv: GOOGLE_FLOW_EMAIL
    requires_browser: true
---

# Google Flow

Browser-automated access to Google's Flow platform for image and video generation. Subscription-based — $0 per generation after subscription. Requires Playwright and a Google account. OpenMontage tools: `google_flow_image`, `google_flow_video`.

## Image Generation (`google_flow_image` v1.2.0)

| Model | Key | Best For |
|-------|-----|----------|
| Nano Banana Pro | `nano_banana_pro` | Text-in-image, posters, CTAs, typography, visual identity — **default** |
| Nano Banana 2 | `nano_banana` | General high-quality photorealistic images |
| Imagen 4 | `imagen_4` | Google Imagen 4 — alternative base model |

**Parameters:**
- `quantity`: `x1`* | `x2` | `x3` | `x4` — batch count; all images downloaded, no extra credit cost
- `aspect_ratio`: `1:1`* | `16:9` | `9:16` | `4:3` | `3:4`
- `ingredients[]`: local image/video paths uploaded as reference (max 5)
- Download is always "Original size" (full-res PNG) — no quality option for images

Use `nano_banana_pro` whenever the image needs legible text, logos, or branded typography.

## Video Generation (`google_flow_video` v0.5.0)

| Model | Key | Notes |
|-------|-----|-------|
| Veo 3.1 Fast | `veo_fast` | Balanced quality and speed — **default** |
| Veo 3.1 Lite | `veo_lite` | Faster, lighter output |

**Parameters:**
- `quantity`: `x1`* | `x2` | `x3` | `x4` — all clips downloaded
- `aspect_ratio`: `16:9`* | `9:16`
- `download_quality`: `720p`* | `1080p` | `270p` (GIF/preview only)
- `camera_motion`: `none`* | `dolly_in` | `dolly_out` | `orbit_left` | `orbit_up` | `dolly_out_zoom`
- `continue_prompt`: extends the clip via "What happens next?" flow
- `first_frame` / `last_frame`: image paths for keyframe-guided generation (mutually exclusive with `ingredients`)
- `ingredients[]`: local image/video reference paths (max 5, mutually exclusive with frames)

**Validation (enforced before browser opens):**
- `first_frame`/`last_frame` + `ingredients` together → error (mutually exclusive)
- `len(ingredients) > 5` → error

## Usage Rules

These rules govern how the agent uses Google Flow video parameters. Follow them unless the stage director skill explicitly overrides.

### Download Quality
- Always use `720p` (default). It is the "Original Size" option — instant download, no server-side processing.
- Use `1080p` only if the user or director explicitly requests higher resolution output.
- **Never use `4k`** — the tool supports it technically but it is not used in OpenMontage pipelines.

### Camera Motion
- **Default: off (`none`).** Do not add camera motion unless the stage director skill or the user explicitly requests it.
- Camera motion is a post-generation effect applied to the clip. It changes the final feel significantly — it is a creative decision, not a default enhancement.
- When the director calls for it, use the most conservative preset that fits (`dolly_in` / `dolly_out` before orbit variants).

### `continue_prompt`
- **Do not use by default.** Only invoke `continue_prompt` when the stage director skill explicitly calls for clip extension, or when the user asks for a longer continuation of a specific shot.
- Do not use it as a general "make it longer" fallback.

### `first_frame` / `last_frame`
- Use **only for continuity** — to maintain character consistency, match a scene transition, or continue a visual from a prior clip.
- If a `first_frame`/`last_frame` call fails or produces inconsistent output, **do not retry with frames**. Fall back to a prompt-only generation instead.
- Do not use frames speculatively or for style reference — use `ingredients` for that.

### `ingredients`
- Use only when the user has provided a specific image or video they want referenced in the generation (e.g. "use this image as the style reference", "match this character").
- Do not add ingredients without a user-provided or director-specified reference asset.

## Veo Prompt Techniques

- **Camera:** describe inline — "slow push in", "aerial drone", "handheld tracking". Prefer inline prompt description over the `camera_motion` param (see rules above).
- **Lighting:** "golden hour", "overcast diffuse", "neon-lit night", "rim-lit studio"
- Be specific about subject + motion + environment; inline description beats generic style words

## Download Quality Reference

| Quality | Key | Use |
|---------|-----|-----|
| 720p | `720p` | **Always use this** — Original size, instant |
| 1080p | `1080p` | Only if explicitly requested |
| 270p | `270p` | Preview/GIF only — not for final output |
| 4k | `4k` | Not used in OpenMontage |

Images always download at full resolution (no quality selector).

## Session and Authentication

- Persistent Chrome profile: `~/.openmontage/google_flow_profile/`
- Cookies cached: `~/.openmontage/google_flow_session.json`
- First-time setup: `python3 -m tools.video.google_flow_setup` (opens visible browser for manual OAuth)
- Subsequent runs are fully automated (headless)
- If session expires, re-run setup script
