---
name: dashscope
description: DashScope (Alibaba Cloud Bailian / 阿里云百炼) integration — image generation (qwen-image-2.0-pro), video generation (wan3.0-video, wan3.0-video-prime), text-to-speech (qwen3-tts-flash), and ASR with word-level timestamps (qwen3-asr-flash-filetrans). Use when generating images via Qwen-Image, video via Wan 3.0, narrating via Qwen-TTS, or transcribing with word-level timestamps via Qwen-ASR.
---

# DashScope

Requires `DASHSCOPE_API_KEY` in `.env`. Get one at https://dashscope.aliyun.com/.

## Current API

**CRITICAL:** DashScope's `/compatible-mode/v1/` only supports `/chat/completions` and `/embeddings`. Image generation, video generation, TTS, and ASR all use **DashScope-native endpoints** — not OpenAI-compatible paths.

All tools use `Authorization: Bearer $DASHSCOPE_API_KEY`.

### Image Generation

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

- Model: `qwen-image-2.0-pro` (default), `qwen-image-max`, `wan2.7-image`, `z-image-turbo`
- Body: `{model, input: {messages: [{role: "user", content: [{text: "prompt"}]}]}, parameters: {size: "W*H", n, prompt_extend, watermark}}`
- **Size format uses asterisk:** `"1024*1024"` not `"1024x1024"`
- Response: `output.choices[0].message.content[0].image` (URL, valid ~24h) — must download separately

### Video Generation (Wan 3.0)

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis
Header: X-DashScope-Async: enable
```

- Model: `wan3.0-video` (default) or `wan3.0-video-prime` (faster, ~1.3-1.5x the price) — each covers text-to-video, first/last-frame, and reference-to-video with the same request shape. The `/compatible-mode/v1/models` listing does **not** show video models; a key can call them anyway.
- Body: `{model, input: {prompt, media: [{type, url}]}, parameters: {resolution, ratio, duration, audio, seed, prompt_extend, watermark}}`
- `media[].type`: `first_frame`, `last_frame`, `reference_image` (≤10), `reference_video` (≤5, total ≤15s), `reference_audio` (≤5, total ≤15s). Frame types and `reference_*` types are mutually exclusive. `url` accepts public URLs or `data:{mime};base64,...`.
- Returns `task_id` → poll `GET /api/v1/tasks/{task_id}` until `SUCCEEDED` → download `output.video_url` (valid 24h). Task IDs expire after 24h.
- Billing is per output second by resolution. **The API defaults to 1080P**; the tool defaults to 720P.
- International-site keys need `DASHSCOPE_REGION=intl` (routes to `dashscope-intl.aliyuncs.com`) or `DASHSCOPE_BASE_URL`.

### Text-to-Speech

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

Same endpoint as image gen, different body.

- Model: `qwen3-tts-flash` (default), `qwen3-tts-instruct-flash`, `qwen-tts-2025-05-22`
- Body: `{model, input: {text, voice: "Cherry", language_type: "Auto"}}`
- Response: `output.audio.url` (WAV, valid ~24h) — must download separately

### ASR with Word-Level Timestamps

```text
POST https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription
Header: X-DashScope-Async: enable
```

- Model: `qwen3-asr-flash-filetrans` (NOT `qwen3-asr-flash` — the sync version has no word timestamps)
- Body: `{model, input: {file_url: "https://public-url/audio.mp3"}, parameters: {enable_words: true, language_hints: ["zh","en"]}}`
- Returns `task_id` → poll `GET /api/v1/tasks/{task_id}` until `SUCCEEDED` → download `output.result.transcription_url` → JSON with `transcripts[].sentences[].words[]`
- Timestamps in `begin_time`/`end_time` are in **milliseconds** — the tool normalizes to seconds

## OpenMontage Usage

### Image via selector

```python
from tools.graphics.image_selector import ImageSelector

result = ImageSelector().execute({
    "preferred_provider": "dashscope",
    "prompt": "一只猫坐在沙发上",
    "output_path": "projects/my-video/assets/images/cat.png",
})
```

### Video via selector

```python
from tools.video.video_selector import VideoSelector

result = VideoSelector().execute({
    "preferred_provider": "dashscope",
    "prompt": "清晨的江南水乡，乌篷船缓缓划过石桥，镜头缓慢推进",
    "duration": "5",
    "aspect_ratio": "16:9",
    "output_path": "projects/my-video/assets/video/scene1.mp4",
})
```

For image-to-video pass `operation: "image_to_video"` with `reference_image_path` (a local file is inlined as base64 — no upload host needed) or `reference_image_url`.

### TTS via selector

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "dashscope",
    "text": "如果 AI 真的会改变未来，普通人到底该怎么参与？",
    "voice": "Cherry",
    "output_path": "projects/my-video/assets/audio/narration.wav",
})
```

### ASR directly (word timestamps for subtitles)

```python
from tools.analysis.dashscope_asr import DashscopeAsr

result = DashscopeAsr().execute({
    "audio_url": "https://example.com/narration.wav",
    "output_path": "projects/my-video/assets/audio/transcription.json",
})

# result.data["words"] is a flat list of {text, begin_time_seconds, end_time_seconds}
```

## Recommended Workflow

1. **Image:** Generate a sample first. Check `prompt_extend: true` (default) — DashScope rewrites your prompt for better results. Disable if you need literal prompt adherence.
2. **Video:** Generate one 5-second 480P/720P sample, approve it, then batch. Check `result.data["actual_prompt"]` to see how `prompt_extend` rewrote the prompt. Wan 3.0 also writes a native audio track; pass `audio: false` when narration and music are laid in separately.
3. **TTS:** Generate a 10-15 second sample before full narration. Approve voice and pacing before committing to full generation.
4. **ASR:** Audio must be at a **publicly accessible URL**. Upload to any public host (S3, etc.) first. Local paths are rejected with a clear error.
5. **Subtitles:** Build from `result.data["words"]` — each word has `begin_time_seconds` and `end_time_seconds`. Group words into caption phrases by language semantics, not fixed character count.

## Parameters

### Image (`dashscope_image`)
- `prompt` (required): text prompt
- `model`: default `qwen-image-2.0-pro`
- `size`: default `"1024*1024"` — **asterisk separator, not "x"**
- `n`: 1-6 images
- `negative_prompt`: things to avoid (max 500 chars)
- `prompt_extend`: default `true` — auto-rewrite prompt for better results
- `watermark`: default `false`
- `seed`: for reproducibility

### Video (`dashscope_video`)
- `prompt` (required): up to 20000 characters, Chinese or English
- `operation`: `text_to_video` (default), `image_to_video`, `first_last_frame_to_video`, `reference_to_video`
- `reference_image_url` / `reference_image_path`: first frame (frame operations) or reference image
- `last_image_url` / `last_image_path`: final frame for `first_last_frame_to_video`
- `reference_image_urls|paths`, `reference_video_url(s)|path(s)`, `reference_audio_urls|paths`: references for `reference_to_video`
- `duration`: default `5`; 2-30 seconds, or `-1` to let the model choose (cost is budgeted at 30s until the real length is known)
- `model`: default `"wan3.0-video"`; `"wan3.0-video-prime"` for faster turnaround
- `resolution`: default `"720P"`; `"480P"` / `"1080P"` — per second up to $0.052 / $0.104 / $0.208 (standard) or $0.068 / $0.14 / $0.28 (prime)
- `ratio` (alias `aspect_ratio`): default `"16:9"` for text-to-video, `"adaptive"` otherwise
- `audio`: default `true`; `seed`; `prompt_extend`: default `true`; `watermark`: default `false`
- `poll_interval_seconds`: default `15`; `timeout_seconds`: default `1800`

### TTS (`dashscope_tts`)
- `text` (required): text to synthesize (max 600 chars for qwen3-tts-flash)
- `model`: default `qwen3-tts-flash`
- `voice`: default `"Cherry"` — other voices: `"Ethan"`, `"Chelsie"`, etc.
- `language_type`: default `"Auto"` — `"Chinese"`, `"English"`, `"Japanese"`, `"Korean"`
- `instructions`: natural language delivery instructions (only for `qwen3-tts-instruct-flash`)

### ASR (`dashscope_asr`)
- `audio_url` (required): **must be publicly accessible URL**
- `model`: `qwen3-asr-flash-filetrans` (only model that supports word timestamps)
- `language_hints`: default `["zh", "en"]`
- `enable_words`: default `true` — required for word-level timestamps
- `poll_interval_seconds`: default `5.0`
- `timeout_seconds`: default `300`

## Troubleshooting

- **Image size error:** Use `"W*H"` with asterisk, not `"WxH"`. Example: `"2048*2048"`.
- **TTS no audio URL:** Check `output.audio.url` — if empty, the model name or voice may be wrong.
- **ASR "file not accessible":** `audio_url` must be publicly reachable. DashScope servers fetch the file; local paths and auth-gated URLs don't work.
- **ASR poll timeout:** Increase `timeout_seconds` (default 300). Long audio files take longer to transcribe.
- **ASR no word timestamps:** Ensure `enable_words: true` and model is `qwen3-asr-flash-filetrans` (not the sync `qwen3-asr-flash`).
- **Video "Model not exist":** The model name is wrong for the region. Mainland China uses `wan3.0-video` / `wan3.0-video-prime` (not `wan3.0-t2v`).
- **Video 401 with an international key:** Set `DASHSCOPE_REGION=intl`.
- **Video timed out:** The error includes `task_id`; query `GET /api/v1/tasks/{task_id}` within 24 hours to recover the clip.
- **Auth error (401):** Verify `DASHSCOPE_API_KEY` is set. Use `Authorization: Bearer $KEY` header.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names. The tool's `_safe_error()` method redacts the key from error messages.
