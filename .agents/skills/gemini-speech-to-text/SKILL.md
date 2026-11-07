---
name: gemini-speech-to-text
description: Transcribe audio to text using Gemini 3.5 Transcribe (Gemini API). Use when converting audio/video to text, generating subtitles, or processing spoken content in OpenMontage. Optional cloud STT provider — available when GOOGLE_API_KEY or GEMINI_API_KEY is configured (free tier on a Google AI Studio key); the local faster-whisper `transcriber` is the default offline path.
license: MIT
compatibility: Requires internet access and a Gemini API key (GOOGLE_API_KEY or GEMINI_API_KEY).
metadata: {"openclaw": {"requires": {"env": ["GOOGLE_API_KEY"]}, "primaryEnv": "GOOGLE_API_KEY"}}
---

# Gemini — Speech-to-Text

Transcribe audio with **Gemini 3.5 Transcribe** (`gemini-3.5-transcribe`):
word-level timestamps, automatic language detection across 85+ languages
(including code-switching), speaker diarization (up to 8 speakers) and custom
vocabulary. In OpenMontage this is the `gemini_stt` tool
(`capability=analysis`, `provider=google`). It is an **optional cloud STT
provider**; the local `transcriber` (faster-whisper) remains the **default
offline path**, and `azure_stt` is the other cloud option.

> Docs: [Transcribe](https://ai.google.dev/gemini-api/docs/transcribe) · [Model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-transcribe) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing)

## Setup

Create a key in [Google AI Studio](https://aistudio.google.com/apikey).

```bash
export GOOGLE_API_KEY=your_gemini_api_key   # GEMINI_API_KEY also works
```

`gemini_stt` reports `AVAILABLE` whenever Google credentials are configured
(API key or service account). **Free tier:** a key without billing can use
`gemini-3.5-transcribe` at no cost, but free-tier content may be used to improve
Google's products — never send confidential or client audio on the free tier.

## Using it in a pipeline

Output matches the `transcriber` schema exactly (segments + word_timestamps),
so it is a drop-in for `subtitle_gen`.

```python
from tools.tool_registry import registry
registry.discover()
stt = registry.get("gemini_stt")

result = stt.execute({
    "input_path": "projects/my-video/assets/audio/narration.wav",
    "language": "es-AR",            # BCP-47 hint; omit for auto-detection
    # "diarize": True,              # speaker labels (spk_1, spk_2, …)
    "output_dir": "projects/my-video/artifacts/transcripts",
})
```

If unavailable or failing, fall back to `azure_stt` (cloud) or
`transcriber` (local) — same `execute` signature and output shape.

## How the request is built

The tool uploads the file through the Files API, then calls
`interactions.create` with:

```json
{"model": "gemini-3.5-transcribe",
 "input": [{"type": "audio", "uri": "<file uri>", "mime_type": "audio/wav"}],
 "generation_config": {"transcription_config": {
   "mode": {"type": "verbatim", "timestamp_granularities": ["word"]},
   "language_codes": ["es-AR"]}}}
```

Word timings arrive as `word_info` annotations with `start_offset` /
`end_offset` duration strings (`"0.100s"`), which the tool converts to seconds.
Segments are rebuilt from the word stream (sentence end, speaker change, or a
pause > 0.8 s).

## Limits & tips

- Word timestamps or diarization cap a file at **30 minutes** (1 hour
  otherwise). Split longer audio first.
- Per Google, word timestamps slightly reduce transcription accuracy and are
  incompatible with custom vocabulary. The tool always requests timestamps
  because subtitles need them.
- Gemini reports no per-word confidence: `probability` is `null`.
- Free tier has per-minute and per-day request limits; space out batch jobs.
- **Video input:** Gemini Transcribe returns an empty transcript for video containers, so the tool extracts the audio track (16 kHz mono WAV, needs `ffmpeg`) before uploading. An empty transcript is reported as a failure, never as success.
