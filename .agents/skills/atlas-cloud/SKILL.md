---
name: atlas-cloud
description: Generate or edit images and videos through the Atlas Cloud gateway. Use for Atlas-hosted Seedance 2.5/2.0, Gemini Omni Flash, MiniMax H3, Seedream 5.0, GPT Image 2, Nano Banana 2, or when one ATLASCLOUD_API_KEY should access multiple media model families.
---

# Atlas Cloud

Route complete productions through `image_selector` or `video_selector`. Call
`atlas_image` or `atlas_video` directly when the user names Atlas Cloud or an
exact Atlas model. Never substitute a direct vendor endpoint for an Atlas request.

Set `ATLASCLOUD_API_KEY`. The aliases `ATLAS_CLOUD_API_KEY` and `ATLAS_API_KEY`
are accepted for compatibility.

## Preflight every paid call

1. Read `tool.get_info()["model_catalog"]`; do not infer availability from a
   search collection or invent a task suffix.
2. Select an exact model id and operation supported by that catalog.
3. Announce the Atlas tool, provider, exact model, request count, and estimated
   cost before submitting.
4. Use local-path inputs when convenient. The tool uploads them through Atlas.
5. Save outputs inside the active `projects/<project-id>/` tree and inspect them.

## Video routes

| Family | Operations | Exact route notes |
|---|---|---|
| Seedance 2.5 | text, image, reference | `bytedance/seedance-2.5/{text,image,reference}-to-video`; image mode uses `image` plus optional `last_image`; reference mode accepts up to 30 images, 10 videos, and 10 audios (including audio-only); 4–30s; $0.134/s |
| Seedance 2.0 | text, image, reference | `bytedance/seedance-2.0/{text,image,reference}-to-video`; 4–15s; $0.112/s |
| Gemini Omni Flash | text, image, reference, video edit | Standard routes use `google/gemini-omni-flash/...`; developer routes exist for text/image/reference only. Standard image mode uses one `image`; standard reference uses `images`; developer reference requires one `video_clips` object. |
| MiniMax H3 | text, image, reference | `minimax/h3/{text,image,reference}-to-video`; image mode supports optional `end_image`; reference mode requires `refers` objects; 4–15s; 768P/2K; $0.10/s |

Use canonical OpenMontage fields:

```python
tool.execute({
    "prompt": "...",
    "model": "minimax/h3/reference-to-video",
    "operation": "reference_to_video",
    "duration": 10,
    "resolution": "2K",
    "reference_images": ["projects/demo/character.png"],
    "reference_audios": ["projects/demo/performance.wav"],
    "output_path": "projects/demo/h3.mp4",
})
```

For Gemini developer reference video, pass `video_clips` objects with `url`,
`start`, and `ends`. For H3, callers may pass normalized `reference_images`,
`reference_videos`, and `reference_audios`; the tool converts them to `refers`.

Do not silently clamp duration, resolution, or ratio. Invalid values must fail
before billing with the supported choices in the error.

## Image routes

| Family | Operations | Exact route notes |
|---|---|---|
| Seedream 5.0 Pro | generate, edit, decompose | `bytedance/seedream-v5.0-pro/text-to-image`, `/edit`, `/layer-decomposition`; edit accepts up to 10 images; sizes use `WIDTH*HEIGHT` |
| Seedream 5.0 Lite | edit | `bytedance/seedream-v5.0-lite/edit`; no live Lite text-to-image sibling is assumed; accepts up to 14 images |
| GPT Image 2 | generate, edit | `openai/gpt-image-2/text-to-image`, `/edit`; sizes use `WIDTHxHEIGHT`; edit accepts up to 10 images |
| Nano Banana 2 | generate, edit | `google/nano-banana-2/text-to-image`, `/edit`; uses aspect ratio plus 1k/2k/4k resolution; edit accepts up to 14 images |

Set `generation_mode` to `generate`, `edit`, or `decompose`. Source images can
be supplied as `image_path`, `image_paths`, `image_url`, or `image_urls`.

```python
tool.execute({
    "prompt": "Replace the packaging with matte cobalt glass; preserve the logo",
    "model": "google/nano-banana-2/edit",
    "generation_mode": "edit",
    "image_paths": ["projects/campaign/source.png"],
    "resolution": "2k",
    "output_path": "projects/campaign/revised.png",
})
```

## Result and failure contract

Both tools submit to Atlas, poll the returned prediction id, download every
output, and return `ToolResult` provenance containing the provider, exact model,
prediction id, submitted parameters, source URL, artifact paths, and estimated
cost. A missing key, unsupported route, invalid enum, missing media input, failed
prediction, timeout, or download failure must return a failed result without
switching providers.

Confirm current pricing and schemas from the machine-readable model page
(`Accept: text/markdown`) immediately before quoting or spending on a batch.
