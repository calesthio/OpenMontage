---
name: modelrunner
description: Generate video, images, speech, or music through the ModelRunner gateway. Use for ModelRunner-hosted Wan 2.7, Happy Horse, Seedance 2.0 Mini, Seedream 5.0, Recraft V4.1, Stable Diffusion 3.5, Kokoro, Gemini TTS, ElevenLabs, Lyria, or Stable Audio, or when one MODELRUNNER_KEY should cover all four media capabilities.
metadata:
  openclaw:
    requires:
      env_any:
        - MODELRUNNER_KEY
        - MODELRUNNER_API_KEY
        - MRUN_API_KEY
---

# ModelRunner

Route complete productions through `video_selector`, `image_selector`, or
`tts_selector`. Call `modelrunner_video`, `modelrunner_image`,
`modelrunner_tts`, or `modelrunner_music` directly when the user names
ModelRunner or an exact ModelRunner endpoint. Never substitute a different
provider for a ModelRunner request.

Set `MODELRUNNER_KEY` (get one at https://modelrunner.ai -> Settings -> API
Keys). The aliases `MODELRUNNER_API_KEY` and `MRUN_API_KEY` are accepted.

## Preflight every paid call

1. Read `tool.get_info()["model_catalog"]`; do not infer a route from a model
   family name or invent a task suffix — endpoint ids are exact.
2. Several routes bill per second at a rate that DEPENDS ON `resolution`
   (the tables below). Announce the tool, exact endpoint, request count, and
   estimated cost before submitting. Per-second routes bill on the DELIVERED
   clip length, which can run slightly past the requested whole seconds
   (e.g. a 4s Seedance request delivering 4.1s bills ~2.5% over estimate).
3. Local image paths are fine — the video tool uploads them through
   ModelRunner storage first.
4. Save outputs inside the active `projects/<project-id>/` tree and inspect them.

## Video routes

Every video route generates a synchronized soundtrack with the picture by
default; the Seedance routes can opt out with `generate_audio: false`.

| Route | Operation | Rate per output second | Notes |
|---|---|---|---|
| `wan-video/wan/v2.7/text-to-video` | text | $0.10 @720P / $0.15 @1080P | 2-15s; 16:9, 9:16, 1:1, 4:3, 3:4; tool defaults to 720P for drafting |
| `wan-video/wan/v2.7/image-to-video` | image | $0.10 @720P / $0.15 @1080P | 2-15s; optional `end_image_url` closing frame; frame shape follows the source image (no ratio field) |
| `alibaba/happy-horse/v1.1/text-to-video` | text | $0.14 @720P / $0.18 @1080P | 3-15s; dialogue written in the prompt is spoken and lip-synced; 9 ratios incl. 21:9 and 4:5 |
| `bytedance/seedance-v2-mini/text-to-video` | text | $0.053 @480p / $0.113 @720p | 4-15s; budget drafting tier; `generate_audio: false` for silence (same price) |
| `bytedance/seedance-v2-mini/image-to-video` | image | $0.053 @480p / $0.113 @720p | 4-15s; motion prompt required; `aspect_ratio: adaptive` keeps the source shape |

```python
tool.execute({
    "prompt": "The balloon drifts across the valley as sunrise light spreads over the ridges",
    "model": "wan-video/wan/v2.7/image-to-video",
    "operation": "image_to_video",
    "image_path": "projects/demo/frame.png",
    "duration": 5,
    "resolution": "720P",
    "output_path": "projects/demo/balloon.mp4",
})
```

## Image routes

Image routes return a LIST of hosted URLs; extra images land as `stem_2`, ...

| Route | Price | Sizing |
|---|---|---|
| `bytedance/seedream-v5/text-to-image` | $0.035 flat | `size` WxH enum, all 2K-class (default 2048x2048) |
| `bytedance/seedream-v5-pro/text-to-image` | $0.045 (~1MP sizes) / $0.09 (2K sizes) | `size` WxH enum, 14 values — the price follows the size |
| `recraft/v4.1/text-to-image` | $0.035 flat | `image_size` preset or `{width, height}` up to 2048 |
| `recraft/v4.1/pro/text-to-image` | $0.21 flat | same sizing, premium tier |
| `stability-ai/stable-diffusion-v3.5-large` | $0.065 per output megapixel | `image_size` preset or `{width, height}`; also takes `negative_prompt`, `guidance_scale`, `num_inference_steps` |

Canonical `width`/`height` are adapted to the closest supported size; passing
the model-native `size` / `image_size` value instead is validated strictly and
fails before billing.

## Speech routes (`modelrunner_tts`)

| Route | Price | Voice field means |
|---|---|---|
| `hexgrad/kokoro-82m` (default) | GPU compute time — a fraction of a cent per clip | one of 46 named voices; prefix = language+gender (`af_bella`, `ff_siwis`, `jm_kumo`) |
| `google/gemini-3.1-flash-tts` | $0.0006 per audio second | 30 prebuilt voices (Kore, Puck, ...); pass delivery direction via `instructions` |
| `elevenlabs/tts/multilingual-v2` | $0.0015 per audio second | 21 named voices (Rachel, ...); `stability`/`similarity_boost`/`style` honored |
| `resemble-ai/chatterbox/text-to-speech/multilingual` | $0.000375 per audio second | `voice` selects the LANGUAGE; 300-char cap per call |

`model_id` accepts the friendly aliases `kokoro`, `gemini-tts`,
`multilingual-v2`, and `chatterbox`. The tts_selector has no exact-model
narrowing — reach a specific route with
`preferred_provider="modelrunner"` plus `model_id`, or call the tool directly.
Controls a route does not support are ignored, not rejected (the selector
passes its full vocabulary through); the catalog's `controls` list says what
each route honors.

## Music routes (`modelrunner_music`)

| Route | Price | Duration |
|---|---|---|
| `google/lyria2` (default) | $0.06 flat | fixed ~30s, instrumental only, 48kHz WAV |
| `google/lyria-3/clip` | $0.04 flat | fixed ~30s, sings lyrics by default — prompt "instrumental only" to suppress |
| `stability-ai/stable-audio-2.5/text-to-audio` | $0.20 flat | `duration_seconds` 1-190; the one route with duration control |

A `duration_seconds` the route cannot honor fails before billing and names the
route that can.

## Result and failure contract

All four tools submit to the ModelRunner queue, poll the returned request id,
download the output, and return `ToolResult` provenance containing the
provider, exact endpoint, request id, submitted parameters, source URL,
artifact paths, and estimated cost. An unknown route, invalid enum, missing
media input, or out-of-range duration fails BEFORE billing, with the supported
choices in the error. A failure after submission returns the `request_id`,
`status_url`, and `response_url` with `billing_status: "possibly_billed"` —
the job may still complete and bill; check the status URL rather than
resubmitting, and never switch providers silently. A request can report
COMPLETED with a non-empty `error` (a normalized provider failure); the tools
treat that as failure, never as output.

The API key is only ever sent to `queue.modelrunner.run` and
`api.modelrunner.run`; output downloads are unauthenticated.

Rates above were verified 2026-08-28. Confirm current pricing from
`get_info()["model_catalog"]` and the live model page before quoting or
spending on a batch.
