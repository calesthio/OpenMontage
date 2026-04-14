---
name: magic-hour
description: |
  Cinematic video generation via Magic Hour API. Best for: cinematic trailers, hyperreal footage, brand ads, natural lifestyle footage. Cost: ~$0.04/second. OpenMontage tool: magic_hour_video.
homepage: https://app.magichour.ai
metadata:
  openclaw:
    requires:
      env:
        - MAGICHOUR_API_KEY
    primaryEnv: MAGICHOUR_API_KEY
---

# Magic Hour

AI video generation service optimized for cinematic output. Cost: ~$0.04/second. OpenMontage tool: `magic_hour_video`.

## Style Modes

| Mode | Best For | Look |
|------|----------|------|
| `cinematic` | Trailers, narratives, film-style | Golden hour, soft shadows, shallow depth of field |
| `hyperreal` | Product showcases, nature, sci-fi | Photorealistic 8K detail, physically accurate lighting |
| `ad` | Brand campaigns, product demos | Clean product lighting, sharp focus, professional color grade |
| `natural` | Lifestyle, documentary, vlog-style | Natural lighting, authentic motion, no stylization |

## Parameters

- **Aspect ratios:** `16:9` (landscape), `9:16` (portrait/reels), `1:1` (square)
- **Duration:** 3–30 seconds, default 5
- **style:** one of the modes above (required)

## Prompt Tips

- Describe the **scene and subject**, not the style — the `style` param handles visual treatment
- Good: `"A barista pours latte art in a sunlit cafe, close-up on hands"`
- Avoid: `"cinematic shot of a barista with golden hour lighting"` — the style param already handles that
- Be specific about subject, location, action, and camera position
- Motion verbs help: "walks toward camera", "spins slowly", "water cascades down"

## Fallback Chain (OpenMontage)

If Magic Hour is unavailable or quota exceeded:
`magic_hour_video → kling_video → higgsfield_video → minimax_video`
