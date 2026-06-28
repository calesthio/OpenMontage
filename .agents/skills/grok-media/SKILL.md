---
name: grok-media
description: xAI Grok image and video generation guide covering authentication, endpoints, prompt structure, image editing, reference-image video, and async polling.
metadata:
  author: Balamonis Studio
  version: "1.0.0"
  tags: xai, grok, image-generation, video-generation, media
---

# Grok Media

Use this skill when working with xAI media models in Balamonis Studio.

## Models

- `grok-imagine-image` for image generation and image editing
- `grok-imagine-video` for text-to-video, image-to-video, and reference-image video

## Authentication

- Env var: `XAI_API_KEY`
- Base URL: `https://api.x.ai/v1`
- Header: `Authorization: Bearer $XAI_API_KEY`

## Image API

### Text-to-image

- Endpoint: `POST /images/generations`
- Core fields:
  - `model`
  - `prompt`
  - `n`
  - `aspect_ratio`
  - `resolution`

### Image edit

- Endpoint: `POST /images/edits`
- Use `image` for one source image
- Use `images` for multi-image compositing
- Each source image can be:
  - a public HTTPS URL
  - a base64 data URI

### Image prompting

- Grok responds well to direct natural language
- For edits, describe only the intended change and preserve everything else implicitly
- For multi-image merges, explicitly name how each source contributes
- Prefer one strong scene description over long style-stacking

## Video API

### Generation

- Endpoint: `POST /videos/generations`
- Polling endpoint: `GET /videos/{request_id}`
- Success state: `status == "done"`
- Failure states to handle explicitly: `failed`, `expired`

### Modes

- Text-to-video:
  - prompt-only generation
- Image-to-video:
  - use `image: {"url": ...}`
  - this anchors the starting frame
- Reference-to-video:
  - use `reference_images: [{"url": ...}, ...]`
  - this influences who/what appears in the video without locking the first frame
  - prompts can reference inputs with placeholders like `<IMAGE_1>`, `<IMAGE_2>`

### Video constraints

- Grok video is best treated as short-form generation
- Current output resolutions are `480p` and `720p`
- Reference-image video supports multiple images and is useful for product placement, wardrobe transfer, and identity consistency
- Download outputs promptly; provider URLs may be temporary

## Pricing

- `grok-imagine-image`: `$0.02` per generated image
- `grok-imagine-image` edits/composites: add `$0.002` per input image
- `grok-imagine-video`:
  - `480p`: `$0.05` per second
  - `720p`: `$0.07` per second
- `grok-imagine-video` image-conditioned requests: add `$0.002` per input image

## Grok-Specific Prompt Guidance

### Images

- Start with subject, action, setting
- Add one style anchor, not five
- For edits:
  - describe the desired modification
  - keep the rest of the image stable by omission, not by writing a giant preservation list

### Video

- Keep prompts scene-local: one shot, one main motion idea, one emotional beat
- For reference-conditioned video, explicitly map source images to roles:
  - person from `<IMAGE_1>`
  - jacket from `<IMAGE_2>`
  - product from `<IMAGE_3>`
- Camera and pacing language helps:
  - slow push-in
  - handheld follow
  - locked-off medium shot
  - high-energy whip pan transition

## Good Fits

- Image style transfer
- Image compositing from multiple sources
- Reference-conditioned short video
- Product-led motion clips
- Character-consistent scenes without hard first-frame lock

## Weak Fits

- Long-form clip generation
- Heavy reliance on deterministic seeds
- Overloaded prompts with multiple scene changes

## Failure Handling

- If generation submission succeeds but polling expires, surface it as a provider/runtime issue
- If a request fails, preserve the endpoint, mode, and prompt summary in the error
- Do not silently substitute a different provider after xAI was selected without user approval
