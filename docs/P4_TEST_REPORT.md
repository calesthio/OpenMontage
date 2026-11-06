# OpenMontage — P4 Test Report

**Component:** Editing & Rendering Engine (P4)  
**Date:** 2026-11-03  
**Render path:** FFmpeg 7.1.5-0+deb13u1 (`/usr/bin/ffmpeg`)  
**Result:** ALL 13 TESTS PASS

---

## 1. Test inventory

| # | Test | Sentences | Status |
|---|---|---|---|
| 1 | test_edit_decisions_one_to_one | 10 | PASS |
| 2 | test_edit_decisions_artifact_shape | 5 | PASS |
| 3 | test_timeline_validation_gaps_overlaps | 10 | PASS |
| 4 | test_render_10_sentences_mp4 | 10 | PASS |
| 5 | test_render_50_sentences_mp4 | 50 | PASS |
| 6 | test_render_250_sentences_mp4 | 250 | PASS |
| 7 | test_render_various_durations | 20 | PASS |
| 8 | test_render_fast_and_slow_motion | 8 | PASS |
| 9 | test_render_long_pauses | 6 | PASS |
| 10 | test_render_missing_images_graceful_failure | 4 | PASS |
| 11 | test_render_missing_narration_silent_fallback | 5 | PASS |
| 12 | test_preview_system_short_fragment | 10→3 | PASS |
| 13 | test_sentence_timeline_integration | 7 | PASS |

**Total: 13 passed, 0 failed.**

(Plus all P0–P3 regression tests continue to pass.)

---

## 2. Real MP4 render results

The render engine produces genuine MP4 files verified by `ffprobe` + full `ffmpeg` decode.

### 10-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| File | 139,911 bytes |
| Duration | 5.000 s |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | h264 |
| Audio codec | aac |
| Bitrate | ~224 kbps |
| Black frames | 0 |
| Frozen segments | 0 |
| ffprobe decode | clean |
| ffmpeg full decode | clean |

### 50-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| Duration | ~4.0 s (80ms × 50) |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | h264 |
| Audio codec | aac |
| Black frames / frozen | 0 / 0 |

### 250-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| Duration | ~20.0 s (80ms × 250) |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | h264 |
| Audio codec | aac |
| Black frames / frozen | 0 / 0 |
| Render wall time | ~200 s |

---

## 3. Sync verification

Every render confirms `|render_duration - sum(scene_durations)| ≤ 1.0 s`. Audio and video are synchronized via the P3 sentence alignment (`start_ms`/`end_ms` from actual audio, not WPM estimates).

---

## 4. One-sentence = one-image = one-audio

`validate_one_to_one()` confirms:
- All `image_asset_id` values unique
- All `audio_asset_id` values unique  
- All `sentence_id` values unique
- No sentence shares an image or audio fragment with another

---

## 5. Error handling verified

| Scenario | Result |
|---|---|
| Missing image file | Graceful FAILED with "image missing" error |
| Missing narration | Silent-audio fallback renders successfully |
| Invalid timeline (overlaps/gaps) | BLOCKED before render |
| No edit decisions | FAILED with clear error |

---

## 6. Preview system

Short preview fragments (first N sentences) render and pass QC:
- Render success, 1920×1080, 16:9
- Motion parameters sane
- Transitions valid
- Audio/video sync within 1s
- Readability ≥720p
- Visual variety present
- No black/frozen frames

---

## 7. Remaining limitations

| Item | Status | Note |
|---|---|---|
| Remotion integration | Not wired | Explainer.tsx is scene-specific; FFmpeg is the verified path. Per AGENT_GUIDE, both engines presented before locking `render_runtime`. |
| Word-level timestamps | Not available | Kokoro-82M has no timestamp API; alignment is sentence-level. |
| Music/SFX rights | Caller-supplied | Module skips missing files; narration renders alone. No engine-sourced music. |
| Per-scene render speed | ~5–200s | 250 sentences ≈ 200s (per-scene ffmpeg process overhead). Acceptable for pipeline. |

---

## 8. Readiness for P5

P4 is complete. The pipeline can render a verified MP4 from edit decisions + audio. Remaining before publication:
- P5: Final QC (`tools/qa/qc.py` on the final MP4 — loudness, black/freeze/silence, subtitle sync, credits)
- P6: Pilot film assembly + release gate
