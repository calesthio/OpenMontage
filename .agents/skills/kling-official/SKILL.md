---
name: kling-official
description: Official Kling direct API guidance for OpenMontage providers. Use before calling `kling_official_video`, `kling_official_image`, `kling_tts`, `kling_avatar`, or `kling_lip_sync`.
metadata:
  openclaw:
    requires:
      env_any:
        - KLING_API_KEY
---

# Kling Official Direct API

Use this skill for OpenMontage tools with `provider="kling_official"`. This is not the fal.ai Kling gateway. Official Kling uses `KLING_API_KEY`, optional `KLING_API_BASE_URL`, and `Authorization: Bearer <KLING_API_KEY>`.

## Provider Split

- `kling_video` uses fal.ai, `FAL_KEY`, fal.ai queue URLs, and `provider="kling"`.
- `kling_official_video` uses Kling official API, `KLING_API_KEY`, official task protocols, and `provider="kling_official"`.
- `kling_official_image` uses the same official auth and task protocol for image generation.
- `kling_tts` uses the official audio TTS endpoint and stays in the existing `tts` capability.
- `kling_avatar` and `kling_lip_sync` use official avatar/lip-sync endpoints and stay in the existing `avatar` capability. They do not replace local `talking_head` or `lip_sync`.

Never silently switch between these paths. If the selected provider is unavailable, surface the blocker and ask before substituting.

## Auth And Endpoint

Default base URL:

```text
https://api-singapore.klingai.com
```

Users may override it with `KLING_API_BASE_URL`, for example for a regional endpoint. All requests send JSON and:

```text
Authorization: Bearer <KLING_API_KEY>
```

## Task Protocols

Classic APIs:

- Create ID path: `data.task_id`
- Statuses: `submitted`, `processing`, `succeed`, `failed`
- Result paths: `data.task_result.videos[]`, `data.task_result.images[]`, `data.task_result.audios[]`

Turbo APIs:

- Create ID path: `data.id`
- Poll path: `GET /tasks?task_ids=<id>`
- Statuses: `submitted`, `processing`, `succeeded`, `failed`
- Result path: `data[0].outputs[]`

Keep the parsers separate. Do not write a fuzzy parser that guesses between `task_id` and `id` or between `succeed` and `succeeded`.

## Omni References

Video Omni and Image Omni stay inside the existing provider tools through `api_family="omni"`.
Do not create selector-level Omni operations.

Video Omni accepts official reference structures:

- `image_list[]` with `image_url` and optional `type` such as `first_frame` or `end_frame`.
- `video_list[]` with `video_url`, official `refer_type` values such as `feature` or `base`, and optional `keep_original_sound`.
- `element_list[]` with official `element_id` values.
- Structured `multi_prompt[]`; do not split natural language into shots automatically.

Local image references may be normalized through `tools/_kling/media.py`. Local video paths must not be silently uploaded through fal.ai; ask for or require a reachable URL.

Image Omni accepts `image_list[]` with official `image` values. Prompt placeholders such as `<<<image_1>>>` must map stably to the provided image order. If the prompt already contains placeholders, validate that the referenced images exist and do not insert duplicates.

## Capability Boundaries

TTS, avatar, and lip sync are provider additions to existing OpenMontage capabilities. Audio effects and video effects are official Kling endpoints, but they are not registered as default OpenMontage tools until a pipeline has a stable capability slot for them.

- Do not add `sound_effects` or `video_effects` capabilities from inside a provider implementation.
- Do not let video effects enter the ordinary `video_generation` selector path.
- Do not disguise short sound effects as long background music unless a pipeline explicitly consumes that shape and the tool's `best_for` / `not_good_for` says so.

## Video Parameters

Use `operation` for OpenMontage semantics:

- `text_to_video`
- `image_to_video`
- `reference_to_video`

Use `api_family` for official protocol choice:

- `classic`
- `turbo`
- `omni`

Important constraints:

- Official video provider input schema must not expose top-level `image_url`; use `reference_image_url` or `reference_image_path`.
- Classic image-to-video accepts `reference_image_url` or a local path converted to raw base64 in official field `image`.
- Turbo image-to-video requires a URL first frame. Do not upload local files through fal.ai as a fallback.
- Send `aspect_ratio` only where the current schema supports it: Classic text-to-video, Turbo text-to-video, and Video Omni.
- Default paid path should avoid `4k`, native sound, or batch behavior unless explicitly selected.

## Image Parameters

Use `api_family="generation"` for `/v1/images/generations` and `api_family="omni"` for `/v1/images/omni-image`.

Generation/edit path:

- `prompt` is required and should stay under the official 2500 character limit.
- `image_url` passes through as official `image`.
- `image_path` is converted to raw base64 and sent as official `image`.
- `image_reference` can be `subject` or `face`.

Omni path:

- Put references in `image_list[]` using official `image` values.
- Use prompt placeholders such as `<<<image_1>>>` only when the prompt needs to bind a specific reference image.

## TTS Parameters

`kling_tts` uses:

- `text`
- `voice_id`
- `voice_language`, currently `zh` or `en`
- `voice_speed`

Require an explicit `voice_id` unless an official account-specific default has been verified. Do not hard-code a made-up voice. Download every returned audio item, set `data.output_path` to the first local file, and include `voice_id`, `voice_language`, `voice_speed`, `task_id`, and non-zero `cost_usd`.

## Avatar Parameters

`kling_avatar` uses `/v1/videos/avatar/image2video` and accepts:

- avatar image via URL or local path converted to raw base64
- `audio_id` or `sound_file`
- optional `prompt`
- `mode`, such as `std` or `pro`

Keep it separate from local `talking_head`. Pipelines that want Kling avatar output must list and choose it explicitly.

## Lip Sync Parameters

`kling_lip_sync` has two steps:

1. `POST /v1/videos/identify-face` with `video_id` or `video_url`; read faces from `data.face_data[]`
2. `POST /v1/videos/advanced-lip-sync` with `session_id` and one `face_choose[]` item containing `face_id`, `audio_id` or `sound_file`, and the sound start/end/insert times

Local video paths must not be silently uploaded through fal.ai or any other provider. If multiple faces are returned and the user did not pass `face_id` or `face_choose`, stop and return the face list for confirmation unless `auto_select_face=True` was explicitly set. If auto-selecting, record the selection reason and selected face in the result/artifact.

## Audio Effects And Video Effects

Official Kling audio effects (`/v1/audio/text-to-audio`, `/v1/audio/video-to-audio`) and video effects (`/v1/videos/effects`) are intentionally not default OpenMontage selector tools. Record the non-mapping reason in docs/tests instead of registering tools that current pipelines might misuse.

## Elements Helper

Elements are an internal Kling Official helper, not a new OpenMontage tool capability.
Use `tools/_kling/elements.py` to normalize `element_list[].element_id`, optionally query read-only element endpoints, and record element metadata when queried. Do not create or delete elements from the default provider path.

## Account Usage Helper

Account Usage is diagnostic only. Use `tools/_kling/account.py` for low-frequency `/account/costs` checks, with local cache and throttle protection. Do not call it before every generation and do not put it in selectors or production pipeline stages.

For `1101` or `1102`, surface that the account or resource pack is exhausted and include an account-usage diagnostic hint.

## Callback Notes

Providers may accept `callback_url`, but polling remains the default execution mode.

- Classic and Omni paths pass `callback_url` at the top level.
- Turbo paths pass it as `options.callback_url`.
- Successful results should record `callback_requested=true`, `polling_used=true`, the `callback_url`, and `task_id`.
- Validate callback URLs before sending; only absolute `http` or `https` URLs should pass.

## Error Handling

Surface official `code`, `message`, and `request_id` whenever available.

Do not retry:

- Auth failures: `1000`-`1004`
- Balance/resource-pack exhaustion: `1101`, `1102`
- Permission/model access: `1103`
- Parameter errors: `1200`, `1201`
- Safety policy: `1301`

Limited retry is acceptable for:

- `1302` request too fast
- `1303` concurrency/resource-pack slot limit
- `5000`, `5001`, `5002` server/maintenance/backlog errors

For `1303`, explain that the account hit a concurrency or resource-pack slot limit.

## Cost Governance

Official Kling is a paid remote API. Provider tools must return non-zero conservative estimates from `estimate_cost()` and include `cost_usd` on successful paid results. Treat estimates as low-confidence until account usage reconciliation is implemented.
High-cost Omni inputs such as multiple references, element IDs, `result_type="series"`, `mode="4k"`, and `sound="on"` must increase or flag the cost estimate.

## Prompt Notes

For video, start from the universal OpenMontage video prompt skeleton: subject, subject motion, scene, spatial framing, and camera. Kling tends to respond well to clear temporal action order, camera movement verbs, and concise negative prompts. For reference workflows, state what should stay consistent from the reference and what should change.
