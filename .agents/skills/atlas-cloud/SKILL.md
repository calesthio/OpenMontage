---
name: atlas-cloud
description: Atlas Cloud integration guide for OpenMontage workflows covering text-to-video, text-to-image, OpenAI-compatible chat completions, media upload, async polling, and live model/schema discovery.
metadata:
  author: OpenMontage
  version: "1.0.0"
  tags: atlascloud, video-generation, image-generation, llm, api, polling
  openclaw:
    requires:
      env:
        - ATLASCLOUD_API_KEY
    primaryEnv: ATLASCLOUD_API_KEY
---

# Atlas Cloud

Use this skill when an OpenMontage workflow needs Atlas Cloud for AI media generation or OpenAI-compatible LLM calls.

## Authentication

Set `ATLASCLOUD_API_KEY` before making requests.

```bash
export ATLASCLOUD_API_KEY="your-api-key"
```

Do not print, log, or commit the API key. Request failures should redact the token from errors.

## Base URLs

| API | Base URL | Purpose |
| --- | --- | --- |
| Media Generation | `https://api.atlascloud.ai/api/v1` | Image/video generation, prediction polling, media upload |
| LLM Chat | `https://api.atlascloud.ai/v1` | OpenAI-compatible chat completions |

All authenticated calls use:

```text
Authorization: Bearer $ATLASCLOUD_API_KEY
Content-Type: application/json
```

## Required Discovery Step

Before using a model in a production workflow, fetch the live model list and then fetch the target model schema.

```bash
curl -s "https://api.atlascloud.ai/api/v1/models"
```

Use only entries with `display_console: true`. For media requests, read the model's `schema` URL and only send fields listed in `components.schemas.Input.properties`.

## Verified Example Models

These model IDs and parameters were checked against the live Atlas Cloud model list and schemas on 2026-07-08.

| Task | Model | Endpoint |
| --- | --- | --- |
| Text-to-video | `bytedance/seedance-2.0-mini/text-to-video` | `POST /model/generateVideo` |
| Text-to-image | `google/nano-banana-2-lite/text-to-image` | `POST /model/generateImage` |
| Chat completions | `deepseek-ai/deepseek-v4-pro` | `POST /chat/completions` |

## OpenMontage Fit

Atlas Cloud is useful when a pipeline needs:

- short text-to-video generation with optional native audio
- image generation for storyboards, thumbnails, B-roll cards, or visual concepts
- OpenAI-compatible chat calls without adding a provider-specific SDK
- temporary media upload for image-to-video or image-editing workflows

## Workflow

1. Fetch `/models` and confirm the selected model is visible.
2. Fetch the selected model schema before building the request body.
3. Submit a generation request.
4. Poll `/model/prediction/{prediction_id}` until a terminal status.
5. Download output URLs promptly and store them as project assets.

## Quick Reference

- [references/api.md](references/api.md) - endpoints, schema-verified fields, polling rules, and error handling
- [references/examples.md](references/examples.md) - minimal cURL and Python snippets for image, video, chat, and media upload
