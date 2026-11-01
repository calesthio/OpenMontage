---
name: minimax-h3
description: |
  Generate MiniMax H3 (Hailuo 3.0) video through the official MiniMax v2 API, fal.ai, Runway, ComfyUI Partner Nodes, or local open weights in ComfyUI. Use for 4-15 second 2K clips, first/last-frame animation, and image/video/audio reference-conditioned video.
---

# MiniMax H3

MiniMax H3 is the Hailuo 3.0 family. The first-party API identifier is
`MiniMax-H3`; fal.ai exposes the family as `hailuo-03`, and Runway uses
`hailuo3`. Do not substitute one provider's identifier into another API.

## Choose a route

| Route | Tool call | Execution |
|-------|-----------|-----------|
| MiniMax direct | `minimax_video`, `model: "MiniMax-H3"` | Hosted first-party v2 API; global or mainland-China region |
| fal.ai | `minimax_fal_video` | Hosted gateway; T2V, I2V, reference-to-video |
| Runway | `runway_video`, `model: "hailuo3"` | Hosted; 768P or 2K, 5–15 seconds |
| ComfyUI Partner Node | `comfyui_video`, `model_family: "minimax_h3_api"` | Hosted and billed in Comfy credits |
| ComfyUI open weights | `comfyui_video`, `model_family: "minimax_h3_local"` | Local GPU with official workflow and model stack |

For local ComfyUI, export the official workflow in API format and pass
`workflow_json` or `workflow_path` plus `output_node`. OpenMontage reports the
required diffusion model, Qwen3-VL text encoder, video VAE, and audio VAE; it
does not silently download large weights.

## Operations and prompting

- Text-to-video: concrete ratio; do not use `adaptive` without visual input.
- Image-to-video: provide a first frame.
- First/last-frame: provide both images and describe the motion between them.
- Reference-to-video: images, videos, and audio can be combined. Audio needs at
  least one visual reference.

Write prompts as subject + action + camera path + environment + lighting +
audio intent. MiniMax responds well to explicit camera direction. Keep the
requested motion achievable within 4–15 seconds and inspect native audio as
carefully as the image track.

## Provider differences

The direct MiniMax v2 route currently outputs 2K and supports 4–15 seconds.
Runway's Hailuo 3.0 route supports 768P/2K and documents 5–15 seconds. Partner
Nodes require network access and credits. Only the open-weight ComfyUI route is
local/offline after all models are installed.
