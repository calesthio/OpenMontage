# OpenMontage — Audio Production Engine (P3)

**Component:** `lib/audio_production_engine.py` + `lib/audio_engine.py` +
`lib/audio_alignment.py` + `lib/audio_qc.py` + `lib/sentence_timeline.py`  
**Status:** P3 complete — designed, implemented, and mock-tested  
**Date:** 2026-11-03  
**Model:** Kokoro-82M, voice `af_heart`  
**Cost:** $0 default (local synthesis, no API keys, no credits)

---

## 1. Architecture

| Layer | Module | Responsibility |
|---|---|---|
| Orchestrator | `lib/audio_production_engine.py` | sentence → text → audio → alignment → QC → timeline |
| TTS Engine | `lib/audio_engine.py` | Kokoro-82M synthesis, caching, retries, text normalization |
| Alignment | `lib/audio_alignment.py` | sentence→timeline mapping via ffmpeg silence detection |
| QC | `lib/audio_qc.py` | file/format/duration/clipping/silence/loudness checks |
| Timeline | `lib/sentence_timeline.py` | per-sentence timeline entry (audio + image merge point) |

Reused P0–P2 modules: `sentence_segmenter`, `asset_registry`, `recovery_manager`.

---

## 2. Data model

### SentenceAudioPlan

One plan per sentence:
- `sentence_id` (S001…), `sentence_text` (verbatim, never modified)
- `normalized_text` (text actually sent to TTS)
- `audio_asset_id`, `output_path` (`audio/sentence_alignment/S00N.wav`)
- `voice` (`af_heart`), `speed` (1.0), `state`, `duration_seconds`
- `start_ms`, `end_ms`, `alignment_confidence` (set by alignment)
- `qc_result`, `error`, `attempts`, `cached`

### AudioSegment (engine output)

`original_text`, `normalized_text`, `audio_path`, `audio_sha256`, `duration_seconds`, `voice`, `speed`, `sample_rate` (24000), `status`, `cached`.

---

## 3. Pipeline

### Text normalization (original preserved separately)

`normalize_text_for_tts()` handles:
- Unicode NFKC normalization
- Abbreviations → spoken form (`Dr.` → `doctor`, `U.S.A.` → `u s a`, `e.g.` → `for example`)
- Decimals → digit-by-digit (`3.14` → `three point one four`)
- Whitespace collapse

The caller keeps `original_text` (verbatim) separate from `normalized_text` (TTS input).

### Synthesis (Kokoro-82M `af_heart`)

- Native 24000 Hz mono WAV output
- Per-sentence synthesis via `KPipeline`
- Retry logic (3 attempts) on failure
- Cache keyed by `voice|speed|normalized_text` → SHA-256 of audio

### Continuous vs per-sentence synthesis

Default `continuous=True` synthesizes each sentence (Kokoro yields one segment per call). The timeline merges them in order with a 0.30s inter-sentence pause. Tests compare both modes.

### Alignment (sentence-level timestamps)

Actual audio duration from ffprobe/soundfile — never words-per-minute estimates.
- ffmpeg `silencedetect` on the concatenated narration track finds pause boundaries
- Sentence start/end refined to nearest silence (tolerance 0.6s)
- Fallback to cumulative duration when silence detection is ambiguous
- Output: `start_ms`, `end_ms`, `duration_ms`, `alignment_confidence` (0.0–1.0)

Word-level timestamps are NOT available from Kokoro-82M (no timestamp API); alignment is sentence-level.

### QC (per sentence)

- file exists / non-empty
- decodable (soundfile)
- sample rate 24000 Hz, channels 1 (mono)
- duration ≥ 0.3s, plausible vs estimated
- clipping check (peak < 0.98)
- silence ratio (RMS/peak)
- loudness (−45…−5 dBFS)

---

## 4. Assets structure

```
projects/<project_id>/
├── audio/
│   ├── narration/          # concatenated narration.wav
│   ├── sentence_alignment/ # per-sentence S00N.wav
│   ├── music/              # background music (added P4, non-destructive)
│   ├── sfx/                # sound effects (added P4)
│   └── qc_reports/         # per-sentence QC JSON
```

Metadata stored per asset: model version (kokoro-82m), voice (`af_heart`), speed, sample rate (24000), file SHA-256, normalized text.

Music/SFX are additive layers (P4) and never overwrite narration WAVs.

---

## 5. Integration (P0–P2 → P3 → P4)

- `sentence_segmenter` → sentence IDs + verbatim text
- `audio_production_engine` → per-sentence audio + alignment timestamps
- `asset_registry` → one audio asset per sentence, integrity-checked
- `quality_control` (image) + `audio_qc` → parallel QC gates
- `sentence_timeline` → single timeline P4 consumes:
  `sentence_id → image_asset_id + [start_ms, end_ms]`

P4 shows one unique image per sentence for exactly its audio duration.

---

## 6. Files created (P3)

| File | Purpose |
|---|---|
| `lib/audio_engine.py` | Kokoro TTS engine + text normalization + caching |
| `lib/audio_alignment.py` | Sentence-level alignment via ffmpeg silence detection |
| `lib/audio_qc.py` | Audio QC (format, clipping, silence, loudness) |
| `lib/sentence_timeline.py` | Per-sentence timeline + P4 readiness gate |
| `lib/audio_production_engine.py` | Audio production orchestrator |
| `tests/lib/test_audio_production_engine.py` | 17 mock tests |
| `tests/tools/test_kokoro_real_smoke.py` | Real Kokoro smoke test |

---

## 7. Test results (P3)

**17 mock tests pass** (zero-cost, placeholder WAVs):
- 10 / 50 / 250 sentence synthesis + QC + alignment + timeline
- abbreviations / dates / numbers / scientific terms normalization
- sentence timestamp accuracy (monotonic, non-overlapping)
- continuous vs per-sentence mode comparison
- error handling & recovery (resume skips completed)
- caching (repeat text → cache hit)
- integration with sentence_segmenter / asset_registry / sentence_timeline
- `ready_for_p4()` gate

**1 real Kokoro smoke test passes**: `af_heart` synthesizes, ffprobe decodes WAV, local CPU, no keys/credits.

---

## 8. Safety

- `mock=True` default: placeholder WAVs, no Kokoro call, no credits
- `HF_HUB_OFFLINE=1` in tests: uses cached weights only
- Zero-Cost Gate + `--no-spend` + MCP Security Proxy respected, never overridden
- No Google Flow, no credit spend, no auth/browser changes

---

## 9. Readiness for P4

P3 complete. P4 consumes `sentence_timeline` (audio QC-passed, timestamps set) and merges image paths from P2's image_generation_engine. Owner gates before real Kokoro production: confirm `af_heart` voice by listening.
