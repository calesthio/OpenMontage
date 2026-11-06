# OpenMontage — Audio Alignment Report (P3)

**Component:** `lib/audio_alignment.py`  
**Date:** 2026-11-03  
**Model:** Kokoro-82M `af_heart` (24000 Hz mono WAV)

---

## 1. Alignment approach (no WhisperX / no heavy deps)

`faster-whisper`, `whisperx`, and `stable-ts` are NOT installed in this
environment, and per project constraints no heavy/dedup libraries were
added. Alignment is therefore derived from the ACTUAL synthesized audio:

1. Kokoro-82M synthesizes each sentence to a separate WAV (measured
   duration via `soundfile.info`, never words-per-minute estimates).
2. Per-sentence WAVs are concatenated into one `narration.wav` track with a
   0.30s inter-sentence pause.
3. `ffmpeg silencedetect` (noise −30 dB, min silence 0.25s) scans the
   concatenated track for pause boundaries.
4. Each sentence's start/end is refined to the nearest detected silence
   (tolerance 0.6s). If no usable silence is found, cumulative duration is
   used (confidence 0.7 instead of 1.0).

**Word-level timestamps are NOT available** from Kokoro-82M (it exposes no
timestamp API). Alignment is sentence-level; sub-sentence granularity would
require a forced-aligner (WhisperX/faster-whisper) which is a P4+ optional
addition.

---

## 2. Data model — SentenceTiming

| Field | Meaning |
|---|---|
| `sentence_id` | S001, S002, … |
| `original_text` | verbatim source |
| `normalized_text` | TTS input |
| `audio_asset_id` | `<project>-AUD-S00N` |
| `audio_path` | path to WAV |
| `start_ms` / `end_ms` / `duration_ms` | timeline positions (actual audio) |
| `alignment_confidence` | 0.0–1.0 (1.0 = silence-refined, 0.7 = cumulative fallback) |
| `status` | `ok` | `partial` | `failed` | `missing_audio` |

---

## 3. Accuracy verification

Mock tests (17 passed) confirm:
- Timestamps are monotonic and non-overlapping across sentences
- `start_ms` of sentence N ≥ `end_ms` of sentence N−1
- `end_ms > start_ms` for every sentence
- `total_duration_ms` equals the last sentence's end (for uniform mock audio)
- `alignment_confidence` = 0.7 when silence detection falls back to cumulative
- Sentence count matches between audio timings and timeline entries

Real Kokoro smoke test (1 passed) confirms the model synthesizes and the WAV
decodes via ffprobe, so the duration inputs to alignment are real.

---

## 4. Limitations

| Item | Status | Notes |
|---|---|---|
| Word-level timestamps | NOT available | Kokoro-82M has no timestamp API |
| Phoneme-level alignment | Not implemented | Kokoro yields phonemes but no per-phoneme timing |
| Silence detection precision | ±0.6s tolerance | ffmpeg `silencedetect` granularity |
| Pauses inside a sentence | Not detected | Only inter-sentence pauses split segments |
| Forced alignment (WhisperX) | Deferred to P4+ | Would add word-level precision + heavy dep |

---

## 5. Output for P4

`SentenceTimeline` produces one entry per sentence with `start_ms` /
`end_ms` / `duration_ms`. P4 consumes this to display one unique image per
sentence for exactly its audio duration:

```
S001: [0ms, 500ms]   → image S001
S002: [800ms, 1300ms] → image S002
S003: [1600ms, 2100ms] → image S003
```

The 0.30s gap between sentences is the inter-sentence pause; P4 may hold
the previous image or cross-fade during the gap.
