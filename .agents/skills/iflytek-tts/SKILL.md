---
name: iflytek-tts
description: Generate long-form Mandarin narration with iFlytek (讯飞) long-text TTS. Use when producing Chinese voiceovers, when the user prefers iFlytek/讯飞/科大讯飞/星火 TTS, when a single narration runs to tens of thousands of characters, or when the video needs a Mandarin dialect voice.
---

# iFlytek TTS (讯飞长文本语音合成)

Requires `IFLYTEK_APP_ID`, `IFLYTEK_API_KEY`, and `IFLYTEK_API_SECRET` in `.env`.
Set `IFLYTEK_TTS_VCN` for the default voice, or pass `voice_id` to the tool.

## Which iFlytek endpoint this uses

iFlytek ships several TTS products. `iflytek_tts` wraps the **long-text (DTS)** one:

```text
POST https://api-dx.xf-yun.com/v1/private/dts_create
POST https://api-dx.xf-yun.com/v1/private/dts_query
```

It is an async batch service — submit, poll, then download the finished audio —
which is the right shape for video narration and keeps the tool on plain HTTP.
The streaming WebSocket endpoints (`在线语音合成`, `超拟人合成`) are deliberately
not used here: they would add a `websocket-client` dependency for a real-time
capability that a render pipeline never needs. If you want the hyper-realistic
streaming voices for something else, iFlytek publishes standalone skills for
them at [iflytek/iFly-Skills](https://github.com/iflytek/iFly-Skills).

## Authentication

DTS signs each request into **query parameters**, not headers — this is the part
people get wrong:

```text
signature_origin = "host: api-dx.xf-yun.com\ndate: <RFC1123 GMT>\nPOST /v1/private/dts_create HTTP/1.1"
signature        = base64(hmac_sha256(IFLYTEK_API_SECRET, signature_origin))
authorization    = base64('api_key="...", algorithm="hmac-sha256", headers="host date request-line", signature="..."')
url              = https://api-dx.xf-yun.com/v1/private/dts_create?host=...&date=...&authorization=...
```

`IFLYTEK_APP_ID` is separate: it travels in the JSON body as `header.app_id`.
The server rejects a `date` more than 300 seconds from its own clock, so a
403 usually means the local machine's time is wrong, not that the key is bad.

## OpenMontage Usage

Generate with the TTS selector:

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "iflytek",
    "text": "在纪录片的第一幕，我们回到一九七八年的那个冬天。",
    "voice_id": "x4_mingge",
    "output_path": "projects/my-video/assets/audio/narration.mp3",
    "speed": 50,
})
```

Or call the provider directly:

```python
from tools.audio.iflytek_tts import IFlytekTTS

result = IFlytekTTS().execute({
    "text": "短样本试听文本。",
    "voice_id": "x4_mingge",
    "output_path": "projects/my-video/assets/audio/iflytek_sample.mp3",
})
```

The provider writes:

- `output_path`: downloaded audio file
- `metadata_path`: full `dts_query` response JSON, defaulting to `<output_path>.json`
- `<metadata_path>.task.json`: recovery inputs saved immediately after acceptance

## Pricing and Recovery

Obtain an account-specific DTS package quote before generating speech.
`estimate_cost()` raises `PriceQuoteRequired`; `cost_usd=None` with
`cost_status="unquoted"` means the actual charge is unknown, not zero.

After a polling or download failure, call `IFlytekTTS().execute(result.data["resume_inputs"])`
or load the inputs from the task checkpoint. The `task_id` selects query/download
only, without another `dts_create` call; text and voice are not required.
The failed result retains the task ID even when checkpoint persistence fails.
Automatic submission retries are disabled. A submission timeout with no returned
task ID has an unknown outcome: reconcile it before attempting a new synthesis.

## Parameters

- `voice_id`: iFlytek `vcn`. Defaults to `IFLYTEK_TTS_VCN`. There is no built-in
  default voice — which voices exist depends on what your app is authorized for.
- `task_id`: resume an accepted task without submitting another synthesis.
- `speed` / `volume` / `pitch`: `0-100`, `50` is normal. Note this is a different
  scale from Doubao's `speech_rate` (`-50..100`); do not copy a value across.
- `language`: `zh` or `en`. Dialects are selected through the voice, not this field.
- `format`: `lame` (MP3, default), `speex`, `opus`, or `raw` (headerless PCM).
- `sample_rate`: `8000`, `16000`, or `24000`. Defaults to `24000` for narration.
- `read_punctuation`: maps to DTS `ram`; `True` reads punctuation marks aloud.
- `timeout_seconds`: defaults to `600`. A 50k-character narration is minutes of
  server-side work, not seconds.

## Recommended Workflow

1. Generate a 10-15 second sample before a full paid narration.
2. Ask the user to approve voice, accent, and pace.
3. Generate the full narration only after approval.
4. Keep the query JSON alongside the audio; it records the task id and the sid,
   which is what iFlytek support asks for.
5. Download promptly — iFlytek keeps the rendered audio for **7 days**, and the
   URL in the metadata JSON goes dead after that.

## Captions

DTS returns **no word or sentence timings**. Do not try to build subtitles from
this provider's metadata. Either:

- transcribe the rendered audio with `azure_stt` or `dashscope_asr` and align
  from the transcript, or
- use `doubao_tts`, which returns `sentences[].words[]` timing directly, when
  word-level caption alignment matters more than iFlytek's voice.

## Troubleshooting

- `HTTP 401 HMAC signature does not match`: wrong `IFLYTEK_API_SECRET`, or the
  signature was built over a different path than the one being requested.
- `HTTP 403`: local clock is more than 5 minutes off UTC.
- `code 10313`: `IFLYTEK_APP_ID` is empty or does not match the key pair.
- `code 10163`: the request schema was rejected — check `vcn`, `encoding`, and
  `sample_rate` against the values this tool's `input_schema` allows.
- `task_status=2`: the task was never dispatched. 长文本语音合成 is probably not
  enabled for this app, or the `vcn` is not authorized for it.

## Safety

Never print or write the credentials to logs, metadata, patches, or project
artifacts. The signed URL itself contains the API key, so never log the full
request URL either. `.env.example` should contain only empty variable names.
