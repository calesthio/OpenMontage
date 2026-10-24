---
name: dashscope
description: DashScope (Alibaba Cloud Bailian / 阿里云百炼) integration — image generation (qwen-image-2.0-pro), text-to-speech (qwen3-tts-flash), and ASR with word-level timestamps (qwen3-asr-flash-filetrans). Use when generating images via Qwen-Image, narrating via Qwen-TTS, or transcribing with word-level timestamps via Qwen-ASR.
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

- Model: `qwen-image-2.0-pro` (default), `qwen-image-max`, `wan2.7-image`, `z-image-turbo`
- Body: `{model, input: {messages: [{role: "user", content: [{text: "prompt"}]}]}, parameters: {size: "W*H", n, prompt_extend, watermark}}`
- **Size format uses asterisk:** `"1024*1024"` not `"1024x1024"`
- Response: `output.choices[0].message.content[0].image` (URL, valid ~24h) — must download separately

### Text-to-Speech

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

Same endpoint as image gen, different body.

- Model: `qwen3-tts-flash` (default), `qwen3-tts-instruct-flash`, `qwen-tts-2025-05-22`
- Body: `{model, input: {text, voice: "Cherry", language_type: "Auto"}}`
- Response: `output.audio.url` (WAV, valid ~24h) — must download separately

### Voice Cloning (voice-enrollment)

```text
POST {base}/services/audio/tts/customization
Header: Authorization: Bearer $DASHSCOPE_API_KEY
Body:   {model: "voice-enrollment", input: {action: "create_voice", ...}}
```

- Actions: `create_voice`, `query_voice`, `list_voice`, `delete_voice`, `update_voice`
- `target_model`: the model that will speak the clone (`qwen-audio-3.1-tts-flash`, `qwen-audio-3.1-tts-plus`, `qwen-audio-3.0-*`, `cosyvoice-v3.5-*`, `cosyvoice-v3-*`). **A clone only works with its enrollment model.**
- `audio`: public URL **or** Base64 Data URI (`data:audio/wav;base64,...`) — local files need no hosting
- `prefix`: letters/digits only, ≤10 chars. The returned ID looks like `{target_model}-{prefix}-{hash}`
- Optional: `language_hints` (single-entry array), `enable_preprocess`, `enable_volume_normalization`, `max_prompt_audio_length`
- Response: `output.voice_id`; poll `action: "query_voice"` until `status` is `OK` (`DEPLOYING` → `OK`, `UNDEPLOYED` = rejected)

Reference audio: WAV/MP3/M4A, ≤10 MB, 10-20 s recommended (5 s minimum of continuous speech, 60 s max), clean single speaker, no music.

### TTS with a cloned voice

```text
POST {base}/services/audio/tts/SpeechSynthesizer
Body: {model: "<target_model>", input: {text, voice: "<voice_id>", format: "wav", sample_rate: 24000}}
```

This is a **different endpoint from `qwen3-tts-flash`** (which uses multimodal-generation with named voices like `Cherry`). `dashscope_tts` routes by model family, and infers the model from the `voice_id` prefix, so pass `voice_id` alone.

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

### Clone a voice, then narrate with it

```python
from tools.audio.dashscope_voice_clone import DashscopeVoiceClone
from tools.audio.dashscope_tts import DashscopeTTS

clone = DashscopeVoiceClone().execute({
    "operation": "create",
    "reference_audio": "path/to/voices/host.mp3",
    "target_model": "qwen-audio-3.1-tts-flash",
    "prefix": "narr",
    "language_hints": ["zh"],
    "enable_preprocess": True,
    "output_path": "projects/my-video/assets/audio/voice-enrollment.json",
})

speech = DashscopeTTS().execute({
    "text": "这是一段使用克隆音色合成的示例旁白。",
    "voice_id": clone.data["voice_id"],   # model is inferred
    "output_path": "projects/my-video/assets/audio/narration.wav",
})
```

Reuse an existing voice with `operation="query"` (health check) or `operation="list"`. Deleting is `operation="delete"` — it frees a slot in the 1000-voice account quota.

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
2. **Voice clone:** Enroll once per production, save the voice ID, and reuse it across every narration segment — re-enrolling per line wastes quota and changes the timbre slightly.
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

### TTS (`dashscope_tts`)
- `text` (required): text to synthesize (max 600 chars for qwen3-tts-flash)
- `model`: default `qwen3-tts-flash`; cloned voices use `qwen-audio-3.1-tts-flash` / `-plus`, `qwen-audio-3.0-*`, or `cosyvoice-v3*`
- `voice`: default `"Cherry"` — other voices: `"Ethan"`, `"Chelsie"`, etc.
- `voice_id`: cloned voice from `dashscope_voice_clone`; wins over `voice` and implies its `target_model`
- `format` / `sample_rate`: output container and rate for cloned-voice models (`wav`/`mp3`/`pcm`, 16000/24000/48000)
- `language_type`: default `"Auto"` — `"Chinese"`, `"English"`, `"Japanese"`, `"Korean"` (qwen3 models only)
- `instructions`: natural language delivery instructions (only for `qwen3-tts-instruct-flash`)

### Voice clone (`dashscope_voice_clone`)
- `operation` (required): `create` | `query` | `list` | `delete`
- `reference_audio`: local `.wav`/`.mp3`/`.m4a` (≤10 MB, 10-20 s recommended) or a public URL
- `target_model`: default `qwen-audio-3.1-tts-flash` — the model the clone will speak with
- `prefix`: letters/digits only, ≤10 chars (default `omvoice`)
- `language_hints`: single language hint such as `["zh"]`
- `enable_preprocess`: denoise/enhance noisy references; leave off for clean studio takes
- `voice_id`: required for `query` and `delete`
- `output_path`: optional JSON record for later stages
- `workspace_id` / `base_url`: switch to a workspace-specific domain if your key requires it

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
- **Clone stuck on `DEPLOYING`:** Usually resolves in seconds; if it stays there, `operation="query"` later. `UNDEPLOYED` means the sample was rejected — clean the audio, cut to 10-20 s, or turn on `enable_preprocess`.
- **Clone rejected on synthesis:** The `voice_id` was enrolled with a different `target_model`. Clones are model-bound; re-enroll with the model you want to use.
- **Clone endpoint 404 / auth error:** Some keys require the workspace-specific domain — set `DASHSCOPE_WORKSPACE_ID` (or pass `workspace_id`) so calls go to `https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1`.
- **ASR "file not accessible":** `audio_url` must be publicly reachable. DashScope servers fetch the file; local paths and auth-gated URLs don't work.
- **ASR poll timeout:** Increase `timeout_seconds` (default 300). Long audio files take longer to transcribe.
- **ASR no word timestamps:** Ensure `enable_words: true` and model is `qwen3-asr-flash-filetrans` (not the sync `qwen3-asr-flash`).
- **Auth error (401):** Verify `DASHSCOPE_API_KEY` is set. Use `Authorization: Bearer $KEY` header.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names. The tool's `_safe_error()` method redacts the key from error messages.
