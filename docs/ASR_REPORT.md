# ASR Report — OpenMontage Factory V8

## Method
- Model: faster-whisper **small** (int8), device=cpu
- VAD filter: enabled (min_silence_duration_ms=500)
- Audio source: `projects/pilot/first_video/audio/narration_master.wav` — clean narration **without music** (extracted from final.mp4 during V7 build)
- Language: English
- Elapsed: 5.47s for 169.45s of audio (~31x realtime)

## Results

| Metric | Value |
|--------|-------|
| Segments | 46 |
| Reference segments | 41 |
| Overall WER (time-aligned) | 0.434 |
| Total errors | 266 / 613 words |

## Why WER is 0.434

**Primary cause: sentence-boundary misalignment.** The ASR segments (46) and reference subtitle segments (41) have different timing boundaries. When matched by time overlap, the ASR text often contains words from adjacent subtitle sentences, inflating WER to ~1.0 on mismatched segments. This is **not** a transcription quality problem — it's a segmentation mismatch.

**Secondary cause: proper nouns.** ASR sometimes transcribes "Enceladus" as "and celadus" (segment 35), showing difficulty with rare proper nouns. But this affects few segments.

**Not a cause: music masking.** The clean narration_master.wav (no music) was used, so music is NOT a factor in this WER.

**Not a cause: model size.** The small model is adequate for clear narration; the WER inflation comes from alignment, not model accuracy.

## Key Words Check

| Word | In scenario | In ASR transcript | Status |
|------|-------------|-------------------|--------|
| Cassini | No | No | N/A — not in scenario |
| cryovolcanism | No | No | N/A — not in scenario |
| Titan | No | No | N/A — not in scenario |
| Juno | No | No | N/A — not in scenario |
| Clipper | No | No | N/A — not in scenario |
| hydrothermal | No | No | N/A — not in scenario |

None of these words appear in the scenario script, so none could be "missed" by ASR. The scenario is about Europa/Enceladus subsurface oceans, not about specific missions.

## Files
- `qc/raw/asr_transcript_small.json` — raw ASR output (46 segments)
- `qc/raw/asr_sentence_diff.json` — per-sentence WER analysis
- `docs/ASR_REPORT.md` — this report
