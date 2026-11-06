# OpenMontage — Image Generation Engine Test Report

**Component:** `lib.image_generation_engine` (P2)  
**Test file:** `tests/lib/test_image_generation_engine.py`  
**Mode:** Mock (zero-cost, no gflow-cli calls, no credits spent)  
**Date:** 2026-11-02  
**Result:** ALL 19 TESTS PASS

---

## 1. Test summary

| Test | Sentences | Status | Key assertions |
|---|---|---|---|
| `test_prompt_creation_10_sentences` | 10 | PASS | Unique non-empty prompts, one per sentence; hero refs every 4th; character NOT in every image |
| `test_prompt_creation_250_sentences` | 250 | PASS | Same assertions at scale |
| `test_unique_asset_prompt_job_ids` | 50 | PASS | Unique asset_id/prompt_id/job_id; asset_id tied to sentence_id |
| `test_one_image_per_sentence_registry` | 10 | PASS | Registry: one asset per sentence; re-register updates in place (no duplicate) |
| `test_mock_generate_10_sentences_qc_passed` | 10 | PASS | All generated, all QC-passed; files exist, 16:9, ≥720p; integrity OK |
| `test_mock_generate_160_sentences` | 160 | PASS | All generated, QC-passed; duplicate detection active |
| `test_mock_generate_250_sentences` | 250 | PASS | Same at 250; QC pass rate ≥95% |
| `test_duplicate_detection_near_duplicate_images` | 2 | PASS | Identical image files flagged as near-duplicate (duplicate_of set) |
| `test_failed_asset_recorded_and_retryable` | 1 | PASS | Failure recorded in registry; error persisted |
| `test_recovery_skips_completed_after_restart` | 5 | PASS | After simulated restart, QC-passed sentences skipped (process=[]) |
| `test_character_reference_registered_and_used` | 8 | PASS | Hero registered with reference; refs only on hero scenes (not every image) |
| `test_flow_job_manager_ready_for_approval_stop` | 5 | PASS | All jobs at READY_FOR_APPROVAL; automated system stops |
| `test_provider_plan_creates_draft_validated_ready` | 1 | PASS | DRAFT→VALIDATED→READY_FOR_APPROVAL; prompt_id/asset_id on job |
| `test_batch_scheduler_chunks_within_gflow_limit` | 10 | PASS | 10 prompts → chunks of 4/4/2 (max 4 per gflow call) |
| `test_batch_scheduler_concurrency_cap` | — | PASS | max_concurrent_batches=2 enforced |
| `test_prompt_engineer_builds_non_text_prompt` | — | PASS | PromptEngineer builds non-text prompt; QC no-text-in-image passes |
| `test_registry_integrity_and_missing_detection` | 1 | PASS | Missing file → integrity fails; file created → integrity passes |
| `test_ahash_detects_duplicate` | 2 | PASS | aHash detects duplicate images |
| `test_default_model_and_aspect_constants` | — | PASS | DEFAULT_MODEL=nano2, DEFAULT_ASPECT=16:9 |

**Total: 19 passed, 0 failed.**

---

## 2. Per-category results

### Prompt creation
- 10 and 250 sentences: all prompts unique, non-empty, contain the sentence's visual concept
- Prompt IDs unique (`<project>-PRT-S00N`)
- Negative prompt contains text/watermark/logo prohibition
- No positive text instruction (QC `check_no_text_in_image` passes)

### Unique IDs + one image per sentence
- `asset_id = <project>-AST-S00N`, `prompt_id = <project>-PRT-S00N`, `job_id = <project>-S00N`
- All unique across sentences
- Registry enforces one asset per sentence (re-register updates in place)

### Mock generation + QC (10 / 160 / 250)
- All images generated (mock placeholder PNGs)
- All images: file exists, decodable, 1920×1080, aspect ratio 16:9, ≥720p
- QC structural checks: script alignment, no prompt contradictions, composition variety, technical suitability
- Registry integrity: all OK, no missing images

### Duplicate detection
- Two identical image files → one flagged as `duplicate`, `duplicate_of` set to the first
- aHash Hamming distance threshold = 5/64

### Error handling / retries
- Failure recorded in registry with error message in `generation_params.last_error`
- Asset status = `failed` (retryable)

### Recovery / restart
- `recovery_checkpoint.json` written with completed/failed/pending/duplicate lists
- After restart, `load_plan()` rebuilds from registry; QC-passed sentences skipped

### Character reference workflow
- Hero character registered with anatomy (glasses, hair, lab coat) + reference image
- Reference entity applied only to hero scenes (every 4th)
- Non-hero scenes have no reference (character not in every image)

### Flow Job Manager integration
- All jobs at `READY_FOR_APPROVAL` after planning (automated stop)
- No `APPROVED`/`SUBMITTED` transition by the wrapper (owner gate)
- `execute_image` with `user_approved=False` + `cost_usd=None` raises `ZeroCostViolation`

### Batch scheduler
- 10 prompts split into chunks of 4/4/2 (respects gflow max 4 per call)
- Concurrency cap enforced (max 2 concurrent batches)

---

## 3. Test environment

- Python 3.12.16
- pytest 9.2.0
- Pillow (for mock image generation)
- gflow-cli 0.92.0 (NOT invoked — mock mode)
- FlowJobManager sqlite/persisted state cleaned between tests (autouse fixture)
- No network, no API keys, no credits spent

---

## 4. Known limitations (mock mode)

- Mock images are procedurally generated placeholders, not real Nano Banana output
- aHash near-duplicate detection can flag structurally similar mock images as duplicates
- Real QC (ffprobe full decode, blackdetect, silencedetect, ebur128) deferred to P3
- Real generation gated behind owner approval + zero-cost gate

---

## 5. Next steps (P3)

1. Audio synthesis: Kokoro-82M `af_heart` per sentence
2. Audio sync: `lib/audio_sync.py` binds scenes to narration
3. Motion: `lib/motion_engine.py` pan/zoom/parallax variety
4. Render: FFmpeg/Remotion compose + `finish_audio` loudness
5. Final QC: `tools/qa/qc.py` on final MP4
