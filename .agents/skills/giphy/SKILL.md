---
name: giphy
description: |
  Animated GIF and MP4 search via Giphy API. Free tier. Best for: reaction inserts, emotional punctuation, overlays, engagement boosts in social video edits. OpenMontage tool: giphy_search.
homepage: https://developers.giphy.com
metadata:
  openclaw:
    requires:
      env:
        - GIPHY_API_KEY
    primaryEnv: GIPHY_API_KEY
---

# Giphy

Animated GIF and looping MP4 search. Free tier available. OpenMontage tool: `giphy_search`.

## What giphy_search Returns

Each result includes:
- `gif_url` — original GIF (large, use for preview/fallback)
- `mp4_url` — looping MP4 (preferred for video composition)
- `webp_url` — WebP animation (good for web embeds)
- `preview_url` — low-res preview GIF
- `width`, `height` — pixel dimensions

## When to Use in Video Edits

- **Reaction moments** — audience response, surprise, disbelief
- **Emotional beats** — celebration, sadness, excitement
- **Humor inserts** — facepalm, shrug, eye roll
- **Social engagement** — clapping, thumbs up, mind blown
- **Transition punctuation** — brief insert between scene cuts

## Parameters

- **rating:** `g` (all audiences), `pg` (default), `pg-13`, `r` — use `pg` unless content explicitly warrants otherwise
- **trending:** set `trending: true` to fetch culturally current GIFs instead of keyword search
- **limit:** number of results to return

## Typical Queries

`"mind blown"`, `"celebration"`, `"thinking"`, `"facepalm"`, `"clapping"`, `"nervous"`, `"excited"`, `"nope"`, `"approved"`

## Format Preference

Prefer `mp4_url` over `gif_url` for video composition — MP4 is smaller, smoother, and composites cleanly in both Remotion and FFmpeg overlay pipelines.

## Overlay Use

GIFs/MP4s work as sticker-style overlays:
- **Remotion:** render as `<Video>` or `<Img>` at absolute position over the base composition
- **FFmpeg:** use `overlay` filter with `shortest=1` to loop the GIF for its duration
