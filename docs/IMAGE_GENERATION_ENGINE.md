# OpenMontage — Image Generation Engine

**Project:** OpenMontage Factory  
**Component:** `lib/image_generation_engine.py` (Orchestrator) + supporting modules  
**Status:** P2 complete — designed, implemented, and mock-tested  
**Date:** 2026-11-02  
**Model:** Nano Banana 2.1 via gflow-cli 0.92.0  
**Cost:** $0 default (no real generation, no credits spent)

---

## 1. Architecture

The Image Generation Engine turns each script sentence into exactly one unique
image.  It reuses existing OpenMontage modules rather than duplicating them:

| Layer | Module | Responsibility |
|---|---|---|
| Orchestrator | `lib/image_generation_engine.py` | Coordinates sentence → prompt → job → image → QC → asset |
| Provider Adapter | `lib/gflow_provider.py` | Adapts GflowWrapper to engine-level requests |
| CLI Driver | `lib/gflow_wrapper.py` | Safe subprocess calls to gflow-cli 0.92.0 (no shell=True) |
| Prompt Generation | `lib/prompt_engineer.py` | Per-sentence visual prompts (reused) |
| Visual Direction | `lib/visual_director.py` | Shot variety, composition, lighting per scene (reused) |
| Character Reference | `lib/character_consistency_manager.py` | Hero anatomy + references (reused) |
| Sentence Input | `lib/sentence_segmenter.py` | S001…S250+ IDs, verbatim text (reused) |
| Batch Scheduler | `lib/batch_scheduler.py` | Chunks within gflow limits (1-4 prompts/call) |
| Asset Registry | `lib/asset_registry.py` | manifest.json, prompts.json, generation_jobs.json, assets/, qc_reports/, generation_logs/ |
| Image QC | `lib/quality_control.py` + `lib/image_uniqueness.py` | Structural QC + aHash near-duplicate detection |
| Recovery | `lib/recovery_manager.py` | Resume checkpoint after Codespace restart |
| Spend Control | `lib/zero_cost_gate.py` + MCP Security Proxy | `--no-spend`, READY_FOR_APPROVAL stop |

**Rule enforced:** ONE SENTENCE = ONE UNIQUE PROMPT = ONE UNIQUE IMAGE.
One image is never used for two sentences.

---

## 2. Data model

### SentenceImagePlan (`lib/image_generation_engine.py`)

One plan per sentence:

| Field | Meaning |
|---|---|
| `sentence_id` | S001, S002, … |
| `sentence_text` | Verbatim source text |
| `prompt_id` | Unique prompt id (`<project>-PRT-S00N`) |
| `asset_id` | Unique asset id (`<project>-AST-S00N`) |
| `job_id` | Flow job id (set during planning) |
| `prompt` | Main visual prompt |
| `negative_prompt` | Negative prompt (text prohibition) |
| `output_path` | `projects/<project>/assets/S00N.png` |
| `model` | `nano2` (Nano Banana 2.1) |
| `aspect_ratio` | `16:9` |
| `reference_entity` | CHARACTER entity id (hero scenes only) |
| `state` | planned | ready_for_approval | generated | qc_passed | qc_failed | duplicate | failed | blocked |
| `qc_result` | QC outcome dict |
| `attempts` | Generation attempt count |

### AssetRegistry (`lib/asset_registry.py`)

Project-scoped registry:

```
projects/<project_id>/
├── manifest.json          # All assets + status
├── prompts.json           # sentence_id -> source prompt + prompt_id
├── generation_jobs.json   # job_id -> generation job record
├── assets/                # Generated image files (assets/<sentence_id>.png)
├── qc_reports/            # Per-asset QC reports (qc_reports/<sentence_id>.json)
└── generation_logs/       # Per-attempt generation logs
```

Integrity checks: unique asset_ids, one-image-per-sentence, unique prompt_ids,
file presence for generated/qc_passed assets.

---

## 3. Pipeline (sentence → image)

### Phase A: Planning (zero-cost, no generation, no credits)

For each sentence S00N:

1. **Segment** — `sentence_segmenter.segment()` produces `S00N` with verbatim text
2. **Prompt** — `prompt_engineer.build_packet()` creates main + negative prompt
   from scene plan + visual directive + character anatomy
3. **Register** — `asset_registry.register_asset()` binds sentence → asset (one
   image per sentence, enforced)
4. **Job** — `gflow_provider.plan_image()` creates a Flow Job held at
   `READY_FOR_APPROVAL` (automated system STOPS here; owner must approve)

No gflow-cli call is made in Phase A.  No credits are spent.

### Phase B: Execution (credit-bearing; requires owner approval)

Only jobs moved to `APPROVED` by the owner proceed.  `GflowWrapper.execute_image()`
enforces:
- Zero-cost gate (unknown cost → `ZeroCostViolation`, never free)
- `READY_FOR_APPROVAL` → `APPROVED` owner gate
- `gflow image t2i` via subprocess (arg list, never shell=True)
- Timeout handling, exit-code parsing, SHA-256 recording

### Phase C: QC (structural, local)

For each generated image:
- File exists and is decodable (Pillow/ffprobe)
- Resolution ≥ 720p (1280×720)
- Aspect ratio 16:9
- Prompt non-empty
- Script alignment (scene serves script)
- Scientific accuracy flagged for human review
- Character reference consistency (if character present)
- No text/caption/watermark in main prompt
- No prompt contradictions (main vs negative)
- Composition variety (not near-duplicate of neighbours)
- Technical suitability (format, aspect ratio, no credit params)

### Phase D: Duplicate detection (`lib/image_uniqueness.py`)

- aHash (8×8 grayscale, mean threshold) over all generated images
- Hamming distance ≤ 5 → near-duplicate flag
- First occurrence wins; subsequent marked `duplicate` (candidate for re-roll)
- aHash alone does not prove semantic uniqueness — combined with scene-description
  Jaccard check from `quality_control.check_scene`

---

## 4. Character consistency

The hero character is registered once via `register_hero_character()`:

- Anatomy: body type, limb count, distinguishing features (glasses, hair, coat),
  clothing notes, color palette
- Reference: approved master reference image (`--reference-entity`)
- Applied only to scenes where `character_id == hero` (every 4th sentence by
  default) — the character is NOT in every image
- `validate_scene_against_character()` checks limb count, features, clothing
- `validate_all_scenes()` produces a ConsistencyReport

Text description alone is NOT accepted as proof of visual consistency — the
reference entity + anatomy checks are the mechanism.

---

## 5. Batch generation

`lib/batch_scheduler.BatchScheduler`:

- Respects gflow-cli 0.92.0 limits: 1-4 prompts per `t2i` call
- `MAX_PROMPTS_PER_CALL = 4` (observed CLI limit)
- `MAX_CONCURRENT_BATCHES = 1` (gflow-cli is a single sequential process)
- `create_batch()` builds a `BatchManifest` from `BatchPrompt` items
- `chunk_for_t2i()` splits into chunks of ≤4 prompts
- `mark_running()/mark_complete()/mark_failed()` enforce concurrency cap
- `save_state()/load_state()` for resume across Codespace restart
- Never launches one enormous job for the whole film

Batch execution via `GflowWrapper.execute_batch()` → `gflow run --config`
with `--continue-on-error --resume --profile flow_remote`.

---

## 6. Recovery / resume

`lib/recovery_manager.RecoveryManager`:

- `snapshot()` persists `recovery_checkpoint.json` (completed/failed/pending/
  duplicate sentences + counts)
- `sentences_to_process()` partitions sentences: `skip` (QC-passed),
  `retry` (failed), `process` (pending/missing)
- On Codespace restart, `load_plan()` rebuilds the plan from the registry
  without recreating Flow Jobs
- Skips already-completed work; re-attempts only failed/missing

---

## 7. Safety (never spend credits)

- `mock=True` by default: writes placeholder PNGs, no gflow call, no credits
- `GFLOW_CLI_HEADLESS=true`, `GFLOW_CLI_UPDATE_CHECK=0` set in wrapper env
- `--no-spend` and MCP Security Proxy are respected, never overridden
- `ZeroCostViolation` raised before any credit-bearing call if cost is unknown
- Execution stops at `READY_FOR_APPROVAL`; owner must manually approve
- No auth or browser profile changes

---

## 8. Files created (P2)

| File | Purpose |
|---|---|
| `lib/image_generation_engine.py` | Orchestrator (main pipeline) |
| `lib/gflow_provider.py` | Provider adapter |
| `lib/asset_registry.py` | Asset registry + integrity |
| `lib/batch_scheduler.py` | Batch scheduler |
| `lib/recovery_manager.py` | Recovery / resume |
| `tests/lib/test_image_generation_engine.py` | 19 mock tests |

### Files modified (P2)

| File | Change |
|---|---|
| `lib/sentence_segmenter.py` | Fixed abbreviation guard (last-token check, not full-text endswith) |
| `lib/gflow_wrapper.py` | Height parsing fix, state-machine order fix (APPROVED→SUBMITTED→COMPLETED), gate-before-state ordering |
| `requirements-pinned.txt` | Added kokoro/misaki/soundfile pins |

---

## 9. Readiness for P3

P2 is complete and mock-tested.  Remaining before real production:

1. Owner selects master hero reference image from 8 candidates (`contact_sheet_master.jpg`)
2. Owner confirms Kokoro `af_heart` voice by listening
3. Measured Nano Banana per-image cost sample (to confirm $0 viability)
4. Primary-source retrieval for pilot topic (publication gate)

P3 will wire audio synthesis (Kokoro), audio_sync, motion engine, FFmpeg/Remotion
render, and final QC (`tools/qa/qc.py`) to produce the pilot MP4.
