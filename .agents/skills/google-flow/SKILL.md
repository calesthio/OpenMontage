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

## Image Generation (`google_flow_image`)

| Model | Key | Best For |
|-------|-----|----------|
| Nano Banana Pro | `nano_banana_pro` | Text-in-image, posters, CTAs, typography, visual identity |
| Nano Banana 2 | `nano_banana` | General high-quality image generation |
| Imagen 4 | `imagen_4` | Photorealistic photography-style images |

Use `nano_banana_pro` whenever the image needs legible text, logos, or branded typography.

## Video Generation (`google_flow_video`)

| Model | Key | Notes |
|-------|-----|-------|
| Veo 3.1 Fast | `veo_fast` | Balanced quality and speed — default |
| Veo 3.1 Lite | `veo_lite` | Faster, lighter output |

## Veo Prompt Techniques

- **Camera movement:** "slow push in", "aerial drone shot", "handheld tracking", "dolly back"
- **Lighting:** "golden hour", "overcast diffuse", "neon-lit night", "rim-lit studio"
- **Ingredients:** pass style hints as `ingredients` array — e.g. `["cinematic", "slow motion", "shallow focus"]`
- Be specific about subject + motion + environment; camera and lighting described inline work better than separate style parameters

## First Frame / Last Frame

- Pass `first_frame` and/or `last_frame` image paths to guide keyframe-controlled generation
- Use cases: scene transitions, morphs, controlled motion arcs, avatar-driven clips

## Download Quality

| Quality | Key | Notes |
|---------|-----|-------|
| 720p | `720p` | Original size — default, instant |
| 1080p | `1080p` | Server-side upscale — slower |
| 270p | `270p` | Preview only, not for final output |

## Session and Authentication

- Cookies saved to `~/.openmontage/google_flow_session.json`
- First run opens a visible browser for manual Google OAuth; subsequent runs are fully automated
- If session expires, delete the JSON file and re-authenticate
- `GOOGLE_FLOW_EMAIL` must match the Google account used during OAuth
