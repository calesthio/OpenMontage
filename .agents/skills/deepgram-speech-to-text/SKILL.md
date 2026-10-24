---
name: deepgram-speech-to-text
description: Transcribe audio to text using Deepgram Nova-3 (pre-recorded REST /v1/listen). Use when converting audio/video to text, generating subtitles, or processing spoken content in OpenMontage. Optional cloud STT provider — available when DEEPGRAM_API_KEY is configured; the local faster-whisper `transcriber` is the default offline path.
license: MIT
compatibility: Requires internet access and a Deepgram API key (DEEPGRAM_API_KEY).
metadata: {"openclaw": {"requires": {"env": ["DEEPGRAM_API_KEY"]}, "primaryEnv": "DEEPGRAM_API_KEY"}}
---

# Deepgram — Speech-to-Text

Transcribe audio to text with **Deepgram Nova-3** — synchronous, word-level
timestamps, smart formatting (punctuation, capitalization, numerals), speaker
diarization, and language detection. In OpenMontage this is exposed through the
`deepgram_stt` tool (`capability=analysis`, `provider=deepgram`). It is an
**optional cloud STT provider**. The local `transcriber` tool (faster-whisper)
remains the **default offline path** and the fallback.

> Docs: [Pre-recorded audio](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded) · [Models & languages](https://developers.deepgram.com/docs/models-languages-overview)

## Setup

Create a key in the [Deepgram console](https://console.deepgram.com) under
**API Keys** (same key as `deepgram_tts`).

```bash
export DEEPGRAM_API_KEY=your_deepgram_api_key
```

`deepgram_stt` reports `AVAILABLE` once `DEEPGRAM_API_KEY` is set.

## Using it in a pipeline

Its output matches the `transcriber` schema exactly, so it is a drop-in for
`subtitle_gen` and any stage that consumes a transcript. The local file
(audio **or video** — Deepgram extracts the audio track) is uploaded as the raw
request body.

```python
from tools.tool_registry import registry
registry.discover()
stt = registry._tools["deepgram_stt"]

result = stt.execute({
    "input_path": "projects/my-video/assets/source/clip.mp4",
    "language": "es",               # BCP-47 hint; omit for auto-detection
    # "keyterms": ["Saporito"],     # boost names/brands (Nova-3 only)
    # "diarize": True,              # speaker labels
    "output_dir": "projects/my-video/artifacts",
})
if result.success:
    segs = result.data["segments"]          # [{id,start,end,text,words:[...]}]
    words = result.data["word_timestamps"]  # flat [{word,start,end,probability}]
```

If `deepgram_stt` is unavailable (no key) or errors, fall back to
`transcriber` (local whisper) or `azure_stt` — same `execute` signature and
output shape.

## Parameters that matter

- **`language`** — pin it when known (`"es"`, `"es-419"`, `"en-US"`); faster
  and more accurate than detection. Use `"multi"` only for real code-switching
  audio (billed at the multilingual rate).
- **`keyterms`** — Nova-3 keyterm prompting for proper nouns the model is
  unlikely to know (people, brands, book titles). Plain terms only.
- **`diarize`** — enables speaker labels via `diarize_model=latest` (the
  `diarize=true` flag is deprecated upstream).
- **`model`** — `nova-3` (default). `nova-2` only for languages Nova-3 lacks.

The tool always requests `smart_format`, `punctuate` and `utterances`.

## Response shape (mapped to the transcriber schema)

Deepgram returns `results.utterances[]` (semantic segments) and per-word
`start`/`end`/`confidence`/`punctuated_word`. They map to:

```json
{
  "segments": [
    {"id": 0, "start": 0.0, "end": 1.0, "text": "Hola mundo.",
     "speaker": 0,
     "words": [{"word": "Hola", "start": 0.0, "end": 0.4, "probability": 0.98}]}
  ],
  "word_timestamps": [{"word": "Hola", "start": 0.0, "end": 0.4, "probability": 0.98}],
  "language": "es",
  "duration_seconds": 1.0,
  "provider": "deepgram"
}
```

`word` uses the smart-formatted `punctuated_word` ("Hola," rather than "hola"),
which is what captions should display. Unlike Azure, confidence is real
per-word confidence.

## Cost

Nova-3 pre-recorded pay-as-you-go (Oct 2026): **$0.0048/min** monolingual,
**$0.0058/min** multilingual. A 60-second clip ≈ $0.005. The tool reports the
actual `cost_usd` from the returned duration. See
[Deepgram pricing](https://deepgram.com/pricing).

## Limits & tips

- Spot-check the first and last cues against the source audio — word
  timestamps drive subtitle timing in `subtitle_gen`.
- For source clips that already contain burned-in captions, transcribe anyway:
  the transcript is what lets you pick clean in/out points by word.
