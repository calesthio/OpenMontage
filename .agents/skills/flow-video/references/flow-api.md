# Google Flow internal API

Observed on 2026-08-31 by instrumenting `fetch`/`XHR` in a live Flow tab while a
human drove the UI. Undocumented and unversioned — Google can change any of it
without notice. Credentials were never recorded: every call goes out from the
signed-in page, so the browser attaches its own cookies and nothing here needs a
key.

Base: `https://aisandbox-pa.googleapis.com/v1`
Media download: `https://labs.google/fx/api/trpc/…`
Every request carries `clientContext.tool = "PINHOLE"` and the project id.

## Endpoint map

| Endpoint | Method | reCAPTCHA | Purpose |
|---|---|---|---|
| `/flow/uploadImage` | POST | no | put an image in the project library |
| `/flow/models/statuses` | GET | no | which video models the account may use |
| `/credits` | GET | no | remaining credit balance |
| `/video:batchCheckAsyncVideoGenerationStatus` | POST | no | poll a generation |
| `/flowWorkflows/{workflowId}` | PATCH | no | workflow/project state |
| `/flow:batchLogFrontendEvents` | POST | no | telemetry (ignore) |
| **`/video:batchAsyncGenerateVideoStartImage`** | POST | **yes** | start a generation |
| **`/video:batchAsyncGenerateVideoUpsampleVideo`** | POST | **yes** | upscale to 1080p |

**The two credit-spending calls are the two gated ones.** Both carry a
`clientContext.recaptchaContext.token` — a ~2.5 KB reCAPTCHA Enterprise token
minted per request by Google's anti-bot script. This is a deliberate boundary,
not an oversight: everything that costs the user credits sits behind bot
detection.

OpenMontage does not mint those tokens. Generation and upscale are driven
through the real UI, where the token is produced as a genuine consequence of
interacting with the app; the rest of the flow uses these endpoints directly.
See "Division of labour" below.

## uploadImage

```jsonc
// POST /v1/flow/uploadImage
{
  "clientContext": { "projectId": "<uuid>", "tool": "PINHOLE" },
  "imageBytes": "<base64, no data: prefix>",
  "isUserUploaded": true,
  "isHidden": false,
  "mimeType": "image/png",
  "fileName": "first_frame.png"
}
```

```jsonc
// 200
{ "media": {
    "name": "<mediaId uuid>",          // this is what startImage.mediaId wants
    "projectId": "<uuid>",
    "workflowId": "<uuid>",
    "workflowStepId": "CAE",
    "mediaMetadata": { "createTime": "...", "visibility": "PRIVATE",
                       "mediaBlobSize": "57794" } } }
```

The returned `media.name` is the id the generation request references. Obtaining
it from this response is exact — far better than matching a filename in the
picker UI, which is what the click-driven path has to do.

## Generation (reCAPTCHA-gated)

```jsonc
// POST /v1/video:batchAsyncGenerateVideoStartImage
{
  "mediaGenerationContext": {
    "batchId": "<uuid>",
    "audioFailurePreference": "BLOCK_SILENCED_VIDEOS"
  },
  "clientContext": {
    "projectId": "<uuid>",
    "tool": "PINHOLE",
    "userPaygateTier": "PAYGATE_TIER_ONE",
    "sessionId": ";<epoch ms>",
    "recaptchaContext": {                      // <-- the gate
      "token": "<~2.5 KB>",
      "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
    }
  },
  "requests": [{
    "outputSpec": { "resolution": "VIDEO_RESOLUTION_720P" },
    "aspectRatio": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "textInput": { "structuredPrompt": { "parts": [{ "text": "<prompt>" }] } },
    "videoModelKey": "veo_3_1_i2v_lite",
    "seed": 27234,
    "metadata": {},
    "startImage": { "mediaId": "<uuid from uploadImage>",
                    "cropCoordinates": { /* … */ } }
  }]
}
```

## Status polling

```jsonc
// POST /v1/video:batchCheckAsyncVideoGenerationStatus
{ "media": [ { "name": "<mediaId>" } ] }
```

The response echoes the full generation parameters, which makes it the honest
place to read back **what Flow actually used** rather than what was asked for:

```jsonc
{ "media": [{
    "name": "<mediaId>",
    "mediaMetadata": {
      "mediaTitle": "<prompt>",
      "requestData": { "videoGenerationRequestData": { "videoModelControlInput": {
        "videoModelName": "veo_3_1_i2v_lite",
        "videoGenerationMode": "VIDEO_GENERATION_MODE_IMAGE_TO_VIDEO",
        "videoAspectRatio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "videoResolution": "VIDEO_RESOLUTION_720P" } } } } }] }
```

`videoGenerationMode` is the field that settles whether a reference image was
really used. A run that silently fell back to prompt-only reports
`VIDEO_GENERATION_MODE_TEXT_TO_VIDEO` here — the failure that produced a valid
but wrong mp4 twice during development.

## Media download

```
GET https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name=<mediaId>
GET …?name=<mediaId>_upsampled     # 1080p, only after an upscale
```

Redirects to a signed `flow-content.google` URL. A 200 with a body under ~100 KB
means the render is not finished — not a video.

## Vocabulary

| Field | Values |
|---|---|
| `videoModelKey` | `veo_3_1_lite`, `veo_3_1_fast`, `veo_3_1_quality`; at runtime the mode is folded in, e.g. `veo_3_1_i2v_lite` |
| `resolution` | `VIDEO_RESOLUTION_360P`, `VIDEO_RESOLUTION_720P` |
| `aspectRatio` | `VIDEO_ASPECT_RATIO_PORTRAIT`, `…_LANDSCAPE` |
| `videoGenerationMode` | `…_IMAGE_TO_VIDEO`, `…_TEXT_TO_VIDEO` |
| `tool` | `PINHOLE` (Flow's internal name) |

## Division of labour

Direct API calls, from inside the signed-in page:

- upload the reference image — returns the exact `mediaId`, no picker to click
- poll generation status — and read back the real model, mode and resolution
- read the credit balance before and after, for a truthful cost figure
- fetch the finished media

Through the UI, where the anti-bot token is a by-product of real interaction:

- starting a generation
- upscaling to 1080p

Do not call these endpoints from Python. They are reachable with the browser's
cookies, but a Python HTTP client presents a different TLS fingerprint and omits
the header the UI session signs, which is a fast route to a flagged account.
Everything that touches Google runs inside the page.
