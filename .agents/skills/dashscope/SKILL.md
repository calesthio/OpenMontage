---
name: dashscope
description: DashScope (Alibaba Cloud Bailian / 阿里云百炼) integration — image generation (Qwen-Image 3.0 / 2.1 / 2.0), text-to-speech (qwen3-tts-flash), and ASR with word-level timestamps (qwen3-asr-flash-filetrans). Use when generating images via Qwen-Image, narrating via Qwen-TTS, or transcribing with word-level timestamps via Qwen-ASR.
---

# DashScope

Requires `DASHSCOPE_API_KEY` in `.env`. Get one at https://dashscope.aliyun.com/.

## Current API

**CRITICAL:** DashScope's `/compatible-mode/v1/` only supports `/chat/completions` and `/embeddings`. Image generation, TTS, and ASR all use **DashScope-native endpoints** — not OpenAI-compatible paths.

All three tools use `Authorization: Bearer $DASHSCOPE_API_KEY`.

### Image Generation

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

- Models:
  - Current: `qwen-image-3.0-pro`, `qwen-image-3.0`, `qwen-image-2.1-pro`, `qwen-image-2.1-turbo`
  - Legacy: `qwen-image-2.0-pro` (tool default), `qwen-image-2.0`
  - Other: `qwen-image-max`, `wan2.7-image`, `z-image-turbo`
- Body: `{model, input: {messages: [{role: "user", content: [{text: "prompt"}]}]}, parameters: {size: "W*H", n, prompt_extend, watermark}}`
- **Size format uses asterisk:** `"1024*1024"` not `"1024x1024"`
- Response: `output.choices[0].message.content[0].image` (URL, valid ~24h) — must download separately

**Parameter support differs by generation.** `dashscope_image` gates these automatically:

| Parameter | 2.1 series | 3.0 series | Legacy 2.0 |
|---|---|---|---|
| `negative_prompt` | ✗ (omitted) | ✓ | ✓ |
| `prompt_extend_mode` (`direct` / `agent`) | ✓ | ✓ | ✗ |
| `enable_thinking` (needs `prompt_extend=true`) | ✓ | ✓ | ✗ |
| `size="auto"` | ✓ | ✓ | ✗ |
| Prompt length | ~4.5k tokens | ~4.5k tokens | ~1.3k tokens |

The 2.1/3.0 series also accept reference images for editing (2.1: up to 10, 3.0: up to 3) and 2.1 can emit an alpha channel; `dashscope_image` currently exposes **text-to-image only**.

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
2. **TTS:** Generate a 10-15 second sample before full narration. Approve voice and pacing before committing to full generation.
3. **ASR:** Audio must be at a **publicly accessible URL**. Upload to any public host (S3, etc.) first. Local paths are rejected with a clear error.
4. **Subtitles:** Build from `result.data["words"]` — each word has `begin_time_seconds` and `end_time_seconds`. Group words into caption phrases by language semantics, not fixed character count.

## Parameters

### Image (`dashscope_image`)
- `prompt` (required): text prompt
- `model`: default `qwen-image-2.0-pro`; current models are `qwen-image-3.0-pro`, `qwen-image-3.0`, `qwen-image-2.1-pro`, `qwen-image-2.1-turbo`
- `size`: default `"1024*1024"` — **asterisk separator, not "x"**; `"auto"` is accepted by 2.1/3.0 only
- `n`: 1-6 images
- `negative_prompt`: things to avoid (max 500 chars); ignored for 2.1, where the API does not accept it
- `prompt_extend`: default `true` — auto-rewrite prompt for better results
- `prompt_extend_mode`: `"direct"` (provider default) or `"agent"` (richer rewrite, text-to-image only); 2.1/3.0 only
- `enable_thinking`: model reasoning for higher quality at higher latency; 2.1/3.0 only, requires `prompt_extend=true`
- `watermark`: default `false`
- `seed`: for reproducibility

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

- **Image size error:** Use `"W*H"` with asterisk, not `"WxH"`. Example: `"2048*2048"`. `"auto"` only works on 2.1/3.0.
- **`negative_prompt` rejected on 2.1:** The 2.1 series dropped it. `dashscope_image` omits it automatically; send it only with 3.0 or legacy 2.0.
- **`prompt_extend_mode` / `enable_thinking` rejected:** These are 2.1/3.0 parameters. `enable_thinking` also requires `prompt_extend=true`.
- **TTS no audio URL:** Check `output.audio.url` — if empty, the model name or voice may be wrong.
- **ASR "file not accessible":** `audio_url` must be publicly reachable. DashScope servers fetch the file; local paths and auth-gated URLs don't work.
- **ASR poll timeout:** Increase `timeout_seconds` (default 300). Long audio files take longer to transcribe.
- **ASR no word timestamps:** Ensure `enable_words: true` and model is `qwen3-asr-flash-filetrans` (not the sync `qwen3-asr-flash`).
- **Auth error (401):** Verify `DASHSCOPE_API_KEY` is set. Use `Authorization: Bearer $KEY` header.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names. The tool's `_safe_error()` method redacts the key from error messages.
