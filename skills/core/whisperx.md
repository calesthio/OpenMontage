# WhisperX / Transcription Skill

## When to Use

Use the `transcriber` tool whenever you need to convert speech to text from
audio or video files. This is the entry point for all transcript-dependent
workflows: subtitle generation, edit decisions based on spoken content, and
scene analysis from dialogue.

## Tool

| Tool | Capability |
|------|-----------|
| `transcriber` | Speech-to-text with word timestamps, language detection, optional diarization |

## How It Works

1. **Model loading:** faster-whisper loads the specified model size (tiny through large-v3). Defaults to `base` for speed. Use `large-v3` for production quality.
2. **Transcription:** VAD filter removes silence. Word-level timestamps are always enabled.
3. **Diarization (optional):** WhisperX alignment + pyannote speaker diarization assigns speaker labels. Requires `HF_TOKEN` environment variable.

## Model Size Guide

| Model | RAM | Speed (CPU) | Quality | When to Use |
|-------|-----|-------------|---------|-------------|
| `tiny` | ~1 GB | ~10x real-time | Low | Quick drafts, iteration |
| `base` | ~1 GB | ~5x real-time | Good | Default for development |
| `small` | ~2 GB | ~3x real-time | Better | Short content |
| `medium` | ~5 GB | ~1.5x real-time | High | Important content |
| `large-v3` | ~10 GB | ~0.5x real-time | Best | Final production |

## Key Patterns

### Choosing When to Diarize

- **Single speaker (talking head):** Skip diarization — it adds latency with no benefit.
- **Multiple speakers (interview, podcast):** Enable diarization to label who said what.
- **Diarization requires** `whisperx` and `HF_TOKEN`. If unavailable, the tool proceeds without speaker labels.

### Word Timestamps for Subtitles

The transcriber produces word-level timestamps with confidence scores, in two shapes: nested per segment (`segments[].words`) and as one flat list (`word_timestamps`):

```
segments: [
  {"id": 0, "start": 0.5, "end": 1.2, "text": "Hello world", "words": [
    {"word": "Hello", "start": 0.5, "end": 0.8, "probability": 0.95},
    {"word": "world", "start": 0.9, "end": 1.2, "probability": 0.92}
  ]},
  ...
]
word_timestamps: [
  {"word": "Hello", "start": 0.5, "end": 0.8, "probability": 0.95},
  {"word": "world", "start": 0.9, "end": 1.2, "probability": 0.92},
  ...
]
```

The `subtitle_gen` tool takes **`segments`** (its only required input) and reads the words from `segments[].words` — pass the transcriber's `segments`, not the flat `word_timestamps` list, which `subtitle_gen` does not accept.

### Language Detection

- Pass `language: null` to auto-detect (adds ~1s overhead).
- Pass an explicit ISO 639-1 code (`en`, `es`, `ja`, etc.) when you know the language.

## Quality Checklist

- [ ] Transcript text is accurate (spot-check 3-5 segments)
- [ ] Word timestamps align with actual speech when played back
- [ ] No missing segments or large gaps in the transcript
- [ ] Language was correctly detected (if auto)
- [ ] Speaker labels are correct (if diarization was used)
