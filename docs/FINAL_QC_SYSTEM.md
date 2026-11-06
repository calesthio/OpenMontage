# OpenMontage — Final Quality Control System (P5)

**Components:** `lib/final_qc.py`, `lib/release_gate.py`  
**Status:** P5 complete — designed, implemented, and tested  
**Date:** 2026-11-03  
**Cost:** $0 (FFmpeg/ffprobe only, no network, no model downloads, no credits)

---

## 1. Architecture

The Final QC system runs end-to-end verification of a rendered MP4 against the
ProductionTimeline (P4), edit decisions (P4), audio mix (P4), asset registry
(P2), and image uniqueness results (P2).

| Layer | Module | Responsibility |
|---|---|---|
| QC Engine | `lib/final_qc.py` | Orchestrates video/audio/visual/sync/structural checks |
| Release Gate | `lib/release_gate.py` | PASS/WARNING/FAIL decision; blocks publish on FAIL |
| Low-level probes | `tools/qa/qc.py` | ffprobe/full_decode/blackdetect/freezedetect/silencedetect/ebur128 |

---

## 2. Data Model

### QCResult

One check result:

| Field | Meaning |
|---|---|
| `check_id` | Unique check identifier |
| `category` | video \| audio \| visual \| sync \| structural |
| `status` | PASS \| WARNING \| FAIL \| BLOCKED \| NOT_RUN |
| `evidence` | Human-readable explanation |
| `measured_value` | Measured value (e.g., loudness, resolution) |
| `threshold` | Threshold used for comparison |
| `blocking` | If True, a FAIL blocks release |

### QCReport

Full report for one project:

| Field | Meaning |
|---|---|
| `overall_status` | PASS \| WARNING \| FAIL \| BLOCKED |
| `checks` | All QCResult entries |
| `blocking_failures` | Checks with blocking=True and status=FAIL |
| `warnings` | Checks with status=WARNING |
| `summary` | Counts by status |

### GateDecision

Release gate output:

| Field | Meaning |
|---|---|
| `decision` | PASS \| WARNING \| FAIL |
| `can_publish` | True only if PASS or WARNING |
| `blocking_checks` | Check IDs that failed (blocking) |
| `warning_checks` | Check IDs with WARNING status |
| `can_publish` | False on FAIL — publish is blocked |

---

## 3. QC Checks

### Video QC

| Check | What it verifies | Fail condition |
|---|---|---|
| `video_integrity` | File exists, non-empty, full decode clean | Decode errors, missing file |
| `video_tracks` | Video+audio streams, 1920×1080, 30fps | Wrong resolution, FPS, missing tracks |
| `video_codec` | H.264 video + AAC audio | Wrong codec |
| `black_frames` | Black frame ratio ≤ 5% | Excessive black frames |
| `frozen_segments` | Frozen segment duration ≤ 2s | Frozen video segments |

### Audio QC

| Check | What it verifies | Fail condition |
|---|---|---|
| `audio_loudness` | Integrated LUFS = −14±2, True Peak ≤ −1 dBTP | Out of range |
| `audio_clipping` | Peak amplitude < 0.98 | Clipping risk |
| `audio_silence` | Silence ratio ≤ 10%, longest run ≤ 3s | Excessive silence |
| `audio_vs_timeline` | Audio duration matches timeline (±1s) | Drift > tolerance |

### Visual QC

| Check | What it verifies | Fail condition |
|---|---|---|
| `one_image_per_sentence` | Each sentence has a unique image | Image reused across sentences |
| `image_asset_id_match` | Decision asset ID == timeline asset ID | Mismatch |
| `no_reused_images` | No duplicate image asset IDs | Duplicate images |
| `no_missing_files` | All image+audio files exist | Missing files |
| `character_consistency` | Hero scenes use single reference entity | Multiple refs (WARNING only) |

### Sync QC

| Check | What it verifies | Fail condition |
|---|---|---|
| `sync_accuracy` | Sentence start/end within ±1 frame (33ms) | Drift > tolerance |
| `no_gaps_overlaps` | Chronological, gap-free, explicit pauses | Overlaps, unexplained gaps |

### Structural QC

| Check | What it verifies | Fail condition |
|---|---|---|
| `duration_match` | Rendered duration matches timeline (±1s) | Drift > tolerance |

---

## 3.5 Visual QC — Frame Sampling

Per the requirements, automatic metrics are not a full replacement for human review. The QC system performs automated checks but flags low-confidence alignments as WARNING. Visual style compliance (per `MASTER_VISUAL_STYLE_GUIDE.md`) and character visual identity are verified at generation time (P2) via `--reference-entity`; P5 confirms the reference entity is consistent across hero scenes.

---

## 4. Release Gate

The `ReleaseGate` evaluates a `QCReport` and produces a `GateDecision`:

| Decision | Condition | Can Publish |
|---|---|---|
| PASS | All blocking checks PASS, no warnings | Yes |
| WARNING | All blocking checks PASS, but warnings exist | Yes (flagged for review) |
| FAIL | Any blocking check FAIL or BLOCKED | **No** |

The gate never auto-publishes on FAIL. It is the hard stop before `package_draft` / upload preparation.

---

## 5. Files Created (P5)

| File | Purpose |
|---|---|
| `lib/final_qc.py` | Final QC engine — all check categories |
| `lib/release_gate.py` | Release gate — PASS/WARNING/FAIL decision |
| `tests/lib/test_final_qc.py` | 8 tests (10/50/250 sentences + negative + load) |
| `docs/FINAL_QC_SYSTEM.md` | This document |
| `docs/P5_TEST_REPORT.md` | Test results |

---

## 6. Test Results

| Test | Sentences | Status |
|---|---|---|
| test_qc_10_sentences_pass | 10 | PASS |
| test_qc_50_sentences_pass | 50 | PASS |
| test_qc_250_sentences_pass | 250 | PASS |
| test_qc_missing_image_render_fails | 5 | PASS (render fails gracefully) |
| test_qc_wrong_fps_fail | 5 | PASS (24fps detected as FAIL) |
| test_qc_duplicate_image_fail | 4 | PASS (duplicate detected as FAIL) |
| test_qc_release_gate_fail_blocks_publish | 3 | PASS (gate logic verified) |
| test_qc_load_readiness_20_25_min | N/A | PASS (timing-based readiness) |

**Total: 8 passed, 0 failed.**

Negative tests verify: missing images, wrong FPS, duplicate images all produce FAIL decisions with `can_publish=False`.

---

## 7. Readiness for P5 → P6

P5 is complete. The factory can now:
1. Render a verified MP4 (P4)
2. Run comprehensive QC on the MP4 (P5)
3. Make a release gate decision (P5)
4. Proceed to package_draft only on PASS/WARNING

Remaining before pilot publication:
- P6: Pilot film assembly + release gate approval
