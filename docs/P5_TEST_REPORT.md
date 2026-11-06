# OpenMontage — P5 Test Report

**Component:** Final QC System (`lib/final_qc.py`, `lib/release_gate.py`)  
**Test File:** `tests/lib/test_final_qc.py`  
**Date:** 2026-11-03  
**Result:** ALL 8 TESTS PASS

---

## 1. Test Inventory

| # | Test | Sentences | Status | Key Assertions |
|---|---|---|---|---|
| 1 | test_qc_10_sentences_pass | 10 | PASS | Real MP4 rendered, QC PASS/WARNING, gate can_publish=True |
| 2 | test_qc_50_sentences_pass | 50 | PASS | Same at scale |
| 3 | test_qc_250_sentences_pass | 250 | PASS | Same at 250 sentences (~20s video) |
| 4 | test_qc_missing_image_render_fails | 5 | PASS | Render returns FAIL when image missing |
| 5 | test_qc_wrong_fps_fail | 5 | PASS | 24fps render detected as video_tracks FAIL |
| 6 | test_qc_duplicate_image_fail | 4 | PASS | Duplicate image_id → one_image_per_sentence FAIL |
| 7 | test_qc_release_gate_fail_blocks_publish | 3 | PASS | FAIL → can_publish=False; PASS → can_publish=True |
| 8 | test_qc_load_readiness_20_25_min | N/A | PASS | 20-min and 25-min timelines build correctly; QC on 20 sentences < 30s |

**Total: 8 passed, 0 failed.**

---

## 2. Real MP4 Render + QC Results

### 10-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | H.264 |
| Audio codec | AAC |
| Duration | 4.0s |
| QC overall | PASS |
| Release gate | PASS, can_publish=True |

### 50-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | H.264 |
| Audio codec | AAC |
| Duration | ~5.0s |
| QC overall | PASS |
| Release gate | PASS |

### 250-sentence render

| Attribute | Value |
|---|---|
| Status | rendered |
| Resolution | 1920×1080 |
| FPS | 30 |
| Video codec | H.264 |
| Audio codec | AAC |
| Duration | ~25.0s |
| QC overall | PASS |
| Release gate | PASS |
| Render wall time | ~170s |

---

## 3. Negative Test Results

| Test | Injected Defect | QC Check | Result |
|---|---|---|---|
| Missing image | Last image path = nonexistent | Render fails before QC | Render FAIL with "image missing" error |
| Wrong FPS | Render at 24fps | `video_tracks` | FAIL (fps ≠ 30) |
| Duplicate image | S002/S003 share same image_id | `one_image_per_sentence` | FAIL |

---

## 4. Release Gate Behavior

| QC Overall | Gate Decision | can_publish |
|---|---|---|
| PASS | PASS | True |
| WARNING | WARNING | True |
| FAIL | FAIL | False |

Verified: FAIL decisions correctly block publishing.

---

## 5. Load Readiness (20–25 min video)

A timing-based readiness check (no full 20–25 min render):
- 20-min timeline ≈ 300 sentences builds correctly
- 25-min timeline ≈ 375 sentences builds correctly
- QC on a 20-sentence subset completes in < 30s (proxy for scale)

---

## 6. QC Checks Covered

| Category | Checks |
|---|---|
| Video | integrity, tracks, codec, black_frames, frozen_segments |
| Audio | loudness, clipping, silence, audio_vs_timeline |
| Visual | one_image_per_sentence, image_asset_id_match, no_reused_images, no_missing_files, character_consistency |
| Sync | sync_accuracy (±1 frame at 30fps), no_gaps_overlaps |
| Structural | duration_match |

---

## 7. Limitations

- Visual style compliance (per MASTER_VISUAL_STYLE_GUIDE.md) is verified at generation time (P2); P5 confirms character reference consistency but does not replace human visual review
- Word-level timestamps are not available from Kokoro-82M; sync is sentence-level
- Music/SFX balance is not directly measured (music is optional); narration loudness is checked

---

## 8. Readiness for P6

P5 is complete. The factory pipeline can render, QC, and gate-release a verified MP4. P6 (pilot film assembly) can proceed once owner approves the pilot topic and master character reference.
