# Atlas Cloud API Reference

## Live Model Discovery

Atlas Cloud models and schemas change over time. Always fetch the current model list first:

```bash
curl -s "https://api.atlascloud.ai/api/v1/models"
```

Use only models with `display_console: true`. For media generation, fetch the model entry's `schema` URL and build request bodies from `components.schemas.Input.properties`.

## Media Endpoints

Base URL:

```text
https://api.atlascloud.ai/api/v1
```

### Text-to-video

Endpoint:

```text
POST /model/generateVideo
```

Schema-verified model:

```text
bytedance/seedance-2.0-mini/text-to-video
```

Required fields:

- `model`
- `prompt`

Optional fields from the live schema checked on 2026-07-08:

- `duration`: `-1`, or `4` through `15`; default `5`
- `resolution`: `480p`, `720p`, `720p-SR`, `1080p-SR`, `1440p-SR`; default `720p`
- `ratio`: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive`; default `adaptive`
- `bitrate_mode`: `standard` or `high`; default `standard`
- `generate_audio`: boolean; default `true`
- `seed`: integer; default `-1`
- `watermark`: boolean; default `false`
- `return_last_frame`: boolean; default `false`

### Text-to-image

Endpoint:

```text
POST /model/generateImage
```

Schema-verified model:

```text
google/nano-banana-2-lite/text-to-image
```

Required fields:

- `model`
- `prompt`

Optional fields from the live schema checked on 2026-07-08:

- `aspect_ratio`: `auto`, `1:1`, `3:2`, `2:3`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`, `4:1`, `1:4`, `8:1`, `1:8`; default `auto`
- `enable_base64_output`: boolean; default `false`
- `enable_sync_mode`: boolean; default `false`
- `resolution`: `1k`; default `1k`
- `thinking_level`: `default`, `high`, `minimal`; default `default`

## Polling

Submit responses include a prediction id. Poll:

```text
GET /model/prediction/{prediction_id}
```

Treat these statuses as in-progress:

- `starting`
- `processing`
- `running`
- `queued`

Treat these as successful terminal statuses:

- `completed`
- `succeeded`

Treat these as failed terminal statuses:

- `failed`
- `canceled`
- `cancelled`
- `error`

Poll every 3 seconds for image generation and every 5 to 10 seconds for video generation. Do not retry generation POST requests automatically because a retry can create duplicate billable tasks.

## Media Upload

Use upload only when a model needs a public URL but the source file is local.

```text
POST /model/uploadMedia
Content-Type: multipart/form-data
```

The form field is `file`. The response includes a temporary `download_url`. Use uploaded media URLs only for Atlas Cloud generation tasks.

## OpenAI-Compatible Chat

Base URL:

```text
https://api.atlascloud.ai/v1
```

Endpoint:

```text
POST /chat/completions
```

Example model confirmed visible in the live model list on 2026-07-08:

```text
deepseek-ai/deepseek-v4-pro
```

Use the standard OpenAI chat-completions request format with `model`, `messages`, `temperature`, `max_tokens`, and `stream` as needed.

## Error Handling

- `401`: missing or invalid API key
- `402`: insufficient account balance
- `429`: rate limited; retry GET polling with backoff
- `5xx`: provider or gateway error; retry GET polling, but do not blindly retry POST generation submissions

Always include the provider endpoint, model id, prediction id, and terminal status in error messages. Never include the API key.
