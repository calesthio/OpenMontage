---
name: minimax-tts
description: Generate expressive multilingual narration with MiniMax Speech T2A. Use when creating voiceovers with MiniMax/Hailuo voices, cloned MiniMax voices, or subtitle timing metadata from MiniMax Speech.
---

# MiniMax TTS

Requires `MINIMAX_API_KEY` in `.env`.
Set `MINIMAX_TTS_VOICE_ID` for the default voice, or pass `voice_id` to the tool.

## Current API

Use the MiniMax HTTP T2A endpoint for synchronous speech generation:

```text
POST https://api.minimax.io/v1/t2a_v2
Authorization: Bearer ${MINIMAX_API_KEY}
Content-Type: application/json
```

The HTTP endpoint is best for short and medium segments. It accepts up to 10,000 characters per request; for longer narration, split by scene or use MiniMax async T2A.

## OpenMontage Usage

Generate with the TTS selector:

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "minimax",
    "text": "如果 AI 真的会改变未来，普通人到底该怎么参与？",
    "voice_id": "Chinese (Mandarin)_Warm_Bestie",
    "model": "speech-2.8-hd",
    "output_path": "projects/my-video/assets/audio/minimax_sample.mp3",
    "subtitle_enable": True,
    "subtitle_type": "sentence",
})
```

Or call the provider directly:

```python
from tools.audio.minimax_tts import MiniMaxTTS

result = MiniMaxTTS().execute({
    "text": "短样本试听文本。",
    "voice_id": "Chinese (Mandarin)_Warm_Bestie",
    "output_path": "projects/my-video/assets/audio/minimax_sample.mp3",
})
```

The provider writes:

- `output_path`: audio file decoded from MiniMax `hex` output, or downloaded from a returned URL
- `metadata_path`: full MiniMax response JSON, defaulting to `<output_path>.json`

## Voice Audition

MiniMax's static system voice list does not include inline audio previews. For practical voice selection, generate a short audition pack with one fixed script:

```bash
python -m tools.audio.minimax_audition \
  --output-dir projects/minimax-tts-audition/assets/audio/first-pass
```

This generates MP3 samples for a Mandarin shortlist and writes `AUDITION_REVIEW.md` with links to each audio file and metadata JSON.

Pass explicit voices when comparing a narrower set:

```bash
python -m tools.audio.minimax_audition \
  --voices "Chinese (Mandarin)_Reliable_Executive" "Chinese (Mandarin)_News_Anchor" \
  --text "这个工具不是替你写一个结论，而是把排查过程变成可复盘的工作流。"
```

Or fetch account-available system voices first:

```bash
python -m tools.audio.minimax_audition \
  --discover-voices \
  --voice-type system \
  --language-filter "Chinese (Mandarin)" \
  --max-voices 8
```

## Recommended Workflow

1. Generate a 10-15 second sample before a full paid narration.
2. Ask the user to approve voice naturalness, pronunciation, and pace.
3. Generate section-level narration after approval, especially for videos with visual beats.
4. Keep the metadata JSON. It contains trace IDs, usage metadata, audio duration, and subtitle references when returned.
5. Use `subtitle_enable: true` and `subtitle_type: "sentence"` first; switch to `word` only when fine-grained captions are needed.
6. Keep `speed: 1.0` as the baseline. Compare short samples before changing speed or pitch.

## Parameters

- `voice_id`: MiniMax system, designed, or cloned voice ID. Defaults to `MINIMAX_TTS_VOICE_ID`.
- `model`: defaults to `speech-2.8-hd`; use `speech-2.8-turbo` when latency matters more than maximum quality.
- `language_boost`: defaults to `auto`; can be set to values such as `Chinese`, `English`, `Japanese`, or `Korean`.
- `speed`: baseline `1.0`.
- `format`: defaults to `mp3`; non-streaming also supports `wav` and `flac`.
- `output_format`: defaults to `hex`; `url` returns a temporary MiniMax audio URL that the provider downloads.
- `subtitle_enable`: defaults to `true`.
- `subtitle_type`: defaults to `sentence`; `word` is available for word-level timing.

## Troubleshooting

- Authentication failure: check `MINIMAX_API_KEY` and Bearer authorization.
- Missing or invalid voice: check `voice_id`/`MINIMAX_TTS_VOICE_ID` and whether the voice is authorized for the account.
- Long text rejected: split narration into scene-level segments or use async T2A.
- Missing subtitles: verify `subtitle_enable: true`, keep the metadata JSON, and confirm the selected model returned subtitle data.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names.
