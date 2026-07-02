---
name: clipia
description: |
  Generate images and video through Clipia (api.clipia.ai) — a multi-model aggregator where one API key unlocks 50+ hosted models (Kling, Veo, Seedance, Wan, Sora, Nano Banana, FLUX, GPT-Image, ...). Use when: (1) CLIPIA_API_KEY is configured, (2) you need several different video/image models without opening new provider accounts, (3) you need a RU/CIS-payable route to premium models (billing in rubles, Russian bank cards), (4) you want spend-safe integration testing — clipia_test_ sandbox keys return instant mock COMPLETED results with zero credit spend. Wrapped by the `clipia_video` and `clipia_image` tools; also exposed as a remote MCP server at https://mcp.clipia.ai/mcp.
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - CLIPIA_API_KEY
---

# Clipia (api.clipia.ai)

Clipia is a generation **aggregator**: `POST /v1/models/{slug}` submits to any of 50+ hosted image/video models through one account, one key, one queue API. The API is deliberately fal.ai-shaped (`submit → status → result`, same field names like `request_id` / `status_url` / `response_url`), so fal.ai integration habits transfer directly. Billing is in **credits** with a fixed, deterministic price per call known at submit time.

**Base URL:** `https://api.clipia.ai` · **Docs:** https://clipia.ai/docs · **Key management:** https://clipia.ai/ru/developer

## Auth

```
Authorization: Key clipia_live_xxxxxxxxxxxxxxxxxxxxxx
```

`Authorization: Bearer <key>` and `X-Api-Key: <key>` are accepted too. Keys are created in the Developer console and shown **once**. The key is a server-side secret — never put it in client code or repos. Key prefixes: `clipia_live_` (production) and `clipia_test_` (sandbox, see below).

## Queue lifecycle (the only mode — async)

```bash
# 1. Submit
curl -X POST https://api.clipia.ai/v1/models/seedance-2-fast-t2v \
  -H "Authorization: Key $CLIPIA_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"input": {"prompt": "aerial dolly over a foggy coast, cinematic", "duration": 5, "aspect_ratio": "16:9"}}'
# -> { "request_id": "...", "status": "IN_QUEUE", "queue_position": 0,
#      "status_url": ".../v1/requests/{id}/status", "response_url": ".../v1/requests/{id}",
#      "cost": 47 }            # <- fixed price in credits, reserved now

# 2. Poll
curl -H "Authorization: Key $CLIPIA_API_KEY" https://api.clipia.ai/v1/requests/{id}/status
# -> { "status": "IN_PROGRESS", "progress": 45, ... }

# 3. Result (when status == COMPLETED)
curl -H "Authorization: Key $CLIPIA_API_KEY" https://api.clipia.ai/v1/requests/{id}
```

| Status | Meaning |
|--------|---------|
| `IN_QUEUE` | queued, `queue_position` ≥ 0 |
| `IN_PROGRESS` | running, `progress` 0–100 |
| `COMPLETED` | done — fetch `response_url` |
| `FAILED` | error; **reserved credits are refunded in full**; `error {code, message}` in the result |
| `CANCELED` | terminal; canceled outside the public API (e.g. from the web account). **Note the single L** — not fal's `CANCELLED`. There is no cancel endpoint in the public API. |

Result endpoint HTTP codes: `200` for terminal statuses (including `FAILED`/`CANCELED`), `202` while still running. Reasonable client timeouts: submit 60 s, poll every ~5 s, overall 15 min for video / 5 min for images.

## Output shapes

Image models:

```json
"output": { "images": [ { "url": "https://media.clipia.ai/....webp",
                           "original_url": "https://media.clipia.ai/....png",
                           "width": 1024, "height": 1024 } ] }
```

Video models:

```json
"output": { "video": { "url": "...", "original_url": "...", "width": 1280, "height": 720, "duration": 5 } }
```

`url` is a display-optimized rendition (usually WebP for images); **`original_url` is the full-quality file — prefer it for downloads** (fall back to `url` when absent).

## Model discovery is dynamic — never hardcode the catalog

- `GET /v1/models` → `{ "data": [ { "slug", "type": "image"|"video", "name", "modalities", "pricing": { "credits" } } ] }`
- `GET /v1/models/{slug}` → per-model `input_schema` (which fields exist, enums, defaults) + pricing multipliers
- `POST /v1/models/{slug}/estimate` → exact `credits` for a concrete parameter set, without queueing

Common `input` fields (availability varies per model — check the schema): `prompt`, `image_url`, `image_urls` (multi-reference), `aspect_ratio`, `duration` (number, seconds, video), `resolution`, `num_images` (images, 1–4).

Popular slugs as of 2026-07 (approximate list prices in credits; 1 credit ≈ $0.04–0.06):

| Slug | Type | Price |
|------|------|-------|
| `seedance-2-fast-t2v` / `seedance-2-fast-i2v` | video | 47 cr / 5 s @ 720p (28 @ 480p) |
| `kling-3` | video | 36 cr / 5 s @ 720p |
| `wan-2-7` | video | 24 cr / 5 s @ 720p |
| `sora-2` / `sora-2-pro` | video | 17 / 28 cr per clip |
| `nano-banana-2` (default image) | image | 4 cr |
| `nano-banana-pro` | image | 5 cr |
| `flux-2-pro` | image | 3 cr |
| `gpt-image-2` | image | 3–7 cr by resolution |

## Sandbox mode (`clipia_test_` keys)

Create a key with the environment toggle set to **Test** → prefix `clipia_test_`. Same header, same code paths:

- **No credits are spent**, no real generation runs.
- `submit` returns `status: COMPLETED` **immediately** (no `IN_QUEUE`/`IN_PROGRESS` phases).
- `output` is a **fixed sample asset** (image or video by model type) — for verifying parsing/polling/download code, not model quality.
- `cost` shows what the call *would* cost on a live key.
- Webhooks are still delivered and HMAC-signed; RPM limits and idempotency behave as in production.

Swap `clipia_test_` → `clipia_live_` and nothing else changes. This is the recommended way to test any Clipia integration end-to-end for $0.

## Idempotency

Send `Idempotency-Key: <UUID v4>` on every submit. Stripe-style rules: same key + same params within 24 h → the **same** `request_id` back (no double generation, no double billing); same key + different params → `409 idempotency_key_reuse`; retry while the first attempt is still processing → `409 request_in_progress`. POST only.

## Errors

Envelope: `{ "error": { "type", "code", "message" } }` (messages are sanitized).

| HTTP | code | Note |
|------|------|------|
| 400 | `invalid_request` | malformed body/params |
| 401 | `invalid_api_key` | missing/wrong/revoked key |
| 402 | `insufficient_credits` | top up credits |
| 402 | `subscription_required` | credits exist but frozen — an **active subscription** is required for API generation; topping up will not help |
| 403 | `insufficient_scope` | key lacks the `generate` scope |
| 404 | `not_found` | unknown `request_id` / model slug |
| 409 | `idempotency_key_reuse` / `request_in_progress` | idempotency conflict |
| 422 | `model_input_invalid` | params don't fit this model — check `GET /v1/models/{slug}` |
| 429 | `rate_limit_exceeded` | default 120 RPM, 10 concurrent; honor `Retry-After` |
| 5xx | `internal_error` / `service_unavailable` | retry with backoff |

## Webhooks (optional, instead of polling)

Pass `webhook_url` next to `input` at submit. On completion Clipia POSTs `{ "request_id", "status": "OK"|"ERROR", "payload": { model, output, cost } }`. Every delivery is HMAC-SHA256-signed: header `X-Clipia-Signature: t=<ts>,v1=<hex>`, signature = `HMAC_SHA256(secret, "{timestamp}.{raw_body}")` with the signing secret from the account; verify with a timing-safe compare and a ±5 min freshness window. Up to 6 retries with exponential backoff; handle deliveries idempotently by `request_id`.

## Calling Clipia inside OpenMontage

Prefer the selectors — both tools are auto-discovered by capability:

```python
from tools.tool_registry import registry
registry.ensure_discovered()

selector = registry.get("video_selector")
result = selector.execute({
    "prompt": PROMPT,
    "preferred_provider": "clipia",
    "operation": "text_to_video",        # or image_to_video
    "duration": "5",
    "aspect_ratio": "16:9",
    "output_path": "projects/<proj>/assets/video/clip_01.mp4",
})
```

Direct calls when you must bypass the selector:

```python
video = registry.get("clipia_video")
video.execute({
    "prompt": PROMPT,
    "model": "kling-3",                  # any slug from GET /v1/models; default seedance-2-fast-t2v
    "duration": "5",
    "resolution": "720p",
    "output_path": "...",
})

image = registry.get("clipia_image")
image.execute({
    "prompt": PROMPT,
    "model": "nano-banana-2",            # default
    "aspect_ratio": "16:9",
    "num_images": 2,
    "output_path": "...",
})
```

## Prompting notes

- English prompts work best for the video models (Russian is fine for image models).
- Do **not** bake on-screen text/captions into video prompts — text renders with artifacts; overlay it in the compose stage instead.
- For a locked-off shot add: `static locked camera, no zoom, no pan`.
- Model-specific prompting (e.g. Seedance shot-structure openers) lives in the model's own skill — e.g. `seedance-2-0` applies to Clipia's `seedance-2-*` slugs too.

## MCP alternative

Clipia also runs a remote MCP server: `https://mcp.clipia.ai/mcp` (stateless Streamable HTTP, `Authorization: Bearer <same key>`), with tools like `generate_image`, `generate_video`, `wait_generation`, `list_models`, `search_templates`. Useful for MCP-native agents; the OpenMontage tools use the REST API and do not need it.

## Sources

- API docs: https://clipia.ai/docs
- Developer console (keys, request logs, usage): https://clipia.ai/ru/developer
- MCP landing: https://clipia.ai/mcp
- Live model catalog: `GET https://api.clipia.ai/v1/models`
