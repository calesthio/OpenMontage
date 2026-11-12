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
artifact paths, and cost. An unknown route, invalid enum, missing media input,
or out-of-range duration fails BEFORE billing, with the supported choices in
the error. A request can report COMPLETED with a non-empty `error` (a
normalized provider failure); the tools treat that as failure, never as output.

**Cost.** After a job finishes, the tool reads the request record back from
ModelRunner and reports what was actually charged. `data["billing"]` says
where the figure came from:
- `"source": "modelrunner_request_record"` means it is the real charge;
- `"source": "estimate"` means the charge had not settled when the tool read
  it back.

`cost_usd` is `None` when the charge is **unknown**: the job was or may have
been accepted, and its outcome cannot be verified. It is never `0.0` in that
case.

**Failures.** Every failure carries `billing_status` and `resubmit_safe`:

| `billing_status` | Meaning | `cost_usd` | `resubmit_safe` |
|---|---|---|---|
| `not_submitted` | Refused before anything was accepted | `0.0` | true |
| `not_collected` | A collect call failed before reaching the job | `0.0` | false |
| `unknown` | The submit's outcome is unknown | `None` | false |
| `possibly_billed` | Accepted; the charge has not settled | `None` | false |
| `failed` | The job failed and was not charged | `0.0` | true |
| `charged` / `partial` | Charged (e.g. the download failed after completion) | the charge | false |

When `resubmit_safe` is false, do not resubmit. Collect the existing job
instead: pass the failure's `request_id` (or its `status_url` /
`response_url`) back to the same tool. A collect call polls, downloads and
reports the job without submitting anything:

```python
tool.execute({"request_id": failed.data["request_id"], "output_path": "out.mp4"})
```

**Job checkpoint.** Every submission is also written to disk, at `job_path`
(default `<output_path>.job.json`). The attempt id goes in before the request
is sent, and the `request_id`, `status_url` and `response_url` once the job is
accepted. If the process dies while polling, read the `request_id` from that
file and collect the job. A file still in `"state": "submitting"` or
`"unknown"` has only the `attempt_id`: find the job in the request history by
its `openmontage_attempt` metadata before submitting again.

A collect call reports `cost_usd: 0.0`, because it caused no new spend. The
job's own charge is in `data["billing"]`.

**Submits are idempotent.** Each submit sends a per-attempt
`X-Idempotency-Key` and retries transport errors, 5xx and 429 responses under
that same key, so a lost response never starts a second paid job. A refusal is
confirmed by one more same-key send before it is reported as `not_submitted`:
the server answers the same refusal only when nothing was dispatched. If the outcome
is still unknown after the retries, the failure carries an `attempt_id`, and
the request is tagged with metadata `openmontage_attempt=<attempt_id>`. Find
it in your ModelRunner request history before resubmitting. `extra_params`
may not set `metadata`.

**Estimates.** Per-second video and per-audio-second TTS estimates add one
second of headroom (`rate x (seconds + 1)`). Billing is on the seconds
delivered, which can run past the request: a 4s Seedance clip delivered 4.1s.

The API key is only ever sent to `queue.modelrunner.run` and
`api.modelrunner.run`; output downloads are unauthenticated.

Rates above were verified 2026-08-28. Confirm current pricing from
`get_info()["model_catalog"]` and the live model page before quoting or
spending on a batch.
