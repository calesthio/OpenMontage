---
name: azure-speech-to-text
description: Transcribe audio to text using Azure AI Speech (Fast Transcription REST API). Use when converting audio/video to text, generating subtitles, or processing spoken content in OpenMontage. Optional cloud STT provider — preferred when AZURE_SPEECH_KEY is configured; the local faster-whisper `transcriber` is the default offline path.
license: MIT
compatibility: Requires internet access and an Azure AI Speech resource (AZURE_SPEECH_KEY + AZURE_SPEECH_REGION).
metadata: {"openclaw": {"requires": {"env": ["AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"]}, "primaryEnv": "AZURE_SPEECH_KEY"}}
---

# Azure AI Speech — Speech-to-Text

Transcribe audio to text with **Azure Fast Transcription** — synchronous,
word-level timestamps, speaker diarization, and multi-language identification.
In OpenMontage this is exposed through the `azure_stt` tool (`capability=analysis`,
`provider=azure`). It is an **optional cloud STT provider** — when
`AZURE_SPEECH_KEY` is configured, prefer it for cloud transcription. The local
`transcriber` tool (faster-whisper) remains the **default offline path** and the
fallback when Azure is unavailable.

> Docs: [Fast Transcription](https://learn.microsoft.com/azure/ai-services/speech-service/fast-transcription-create) · [Speech service overview](https://learn.microsoft.com/azure/ai-services/speech-service/spx-overview)

## Why Fast Transcription (not Batch)

Azure exposes three STT surfaces. OpenMontage uses **Fast Transcription** because
the pipeline transcribes **local audio files**:

| Surface | Input | Latency | Needs |
|---------|-------|---------|-------|
| **Fast Transcription** (used here) | local file, multipart POST | synchronous, sub-real-time | key + region |
| Batch Transcription | audio at a URL (Blob + SAS) | async job + polling | Blob storage plumbing |
| Speech SDK (`spx`) | mic / stream / file | streaming | native `azure-cognitiveservices-speech` package |

Fast Transcription needs no Blob storage, no SAS URLs, and no native SDK — just
`requests` and the two env vars.

## Setup

Create a **Speech** resource in the [Azure portal](https://portal.azure.com);
copy the key and region from its **Keys and Endpoint** page.

```bash
export AZURE_SPEECH_KEY=your_speech_resource_key
export AZURE_SPEECH_REGION=eastus          # your resource's region
# export AZURE_SPEECH_ENDPOINT=https://...  # optional: overrides region
```

`azure_stt` reports `AVAILABLE` once `AZURE_SPEECH_KEY` plus either
`AZURE_SPEECH_REGION` or `AZURE_SPEECH_ENDPOINT` are set.

## Using it in a pipeline

Prefer `azure_stt` over `transcriber` unless the run must be offline. Its output
matches the `transcriber` schema exactly, so it is a drop-in for `subtitle_gen`
and any stage that consumes a transcript.

```python
from tools.tool_registry import registry
registry.discover()
stt = registry._tools["azure_stt"]

result = stt.execute({
    "input_path": "projects/my-video/assets/audio/narration.mp3",
    # "language": "en",          # ISO 639-1 or BCP-47 ("en-US"); omit for auto-ID
    # "diarize": True,           # speaker labels, no HuggingFace token needed
    # "max_speakers": 4,
    "output_dir": "projects/my-video/artifacts",
})
if result.success:
    segs = result.data["segments"]          # [{id,start,end,text,words:[...]}]
    words = result.data["word_timestamps"]  # flat [{word,start,end,probability}]
```

If `azure_stt` is unavailable (no key) or errors, fall back to `transcriber`
(local whisper) — its `execute` signature and output are identical.

## Parameters that matter

- **`language`** — pass an ISO code (`"en"`) or a full locale (`"en-US"`). Pin it
  when you know the language; it is faster and more accurate than auto-ID.
- **`candidate_locales`** — when `language` is omitted, Azure runs language
  identification across this shortlist. Narrow it to the languages you actually
  expect; a huge list slows detection and invites misclassification.
- **`diarize` / `max_speakers`** — enable for multi-speaker audio (interviews,
  podcasts). Set `max_speakers` to the real upper bound.
- **`profanity_filter`** — `None` | `Masked` (default) | `Removed` | `Tags`.

## Response shape (mapped to the transcriber schema)

The raw Azure response (`phrases[]` with `offsetMilliseconds` / `words[]`) is
converted to seconds and the OpenMontage transcript schema:

```json
{
  "segments": [
    {"id": 0, "start": 0.0, "end": 2.4, "text": "Hello world",
     "speaker": 1,
     "words": [{"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.98}]}
  ],
  "word_timestamps": [{"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.98}],
  "language": "en-US",
  "duration_seconds": 2.4,
  "provider": "azure"
}
```

Note: Fast Transcription has no *per-word* confidence, so each word carries the
**phrase** confidence in `probability`.

## Limits & tips

- Single file up to ~2 hours / a few hundred MB per request. For longer or bulk
  jobs, use Azure Batch Transcription instead.
- Send clean audio (16 kHz+ mono is plenty). Transcode video to audio first if
  you only need speech — smaller upload, same result.
- Verify timing: word timestamps drive subtitle cues in `subtitle_gen`. Spot-check
  the first and last cues against the source audio.
