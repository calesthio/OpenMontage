# EPISODE IMAGE PIPELINE — brief, budget, batches, resume (P3)

**Locked model:** `klein` → `black-forest-labs/FLUX.2-klein-4B`
(`config/image_engine.json` → `model`, status `OWNER_GATED`).
**Code:** `tools/illustration/image_brief.py` (the brief step),
`tools/illustration/episode_run.py` (the run), `tools/illustration/kaggle_episode_bridge.py`
(the bridge), driver `scripts/run_episode_images.py`.
**Tests:** `tests/illustration/test_episode_run.py` (fake bridge: partial failure,
resume, hash mismatch, unknown beat).
**Roles:** inline, not independent. Image quality is judged by the **owner** —
this pipeline records facts (seconds/image, usable share), never beauty.

## 1. The brief step: script -> one prompt per visual beat

`script.md` (beats with claim ids) + `claim_ledger.md` + the niche specs +
`style.json` + the locked model -> `image_brief.json`.

- The prompt text comes from **tools/prompting (read only)**; the style, the
  camera vocabulary and the constraints come from the niche's `style.json`.
- Every creature prompt carries its **anatomy counts** (`6 limbs, 2 eyes,
  0 horns`) — the builder's contract, checked by a test.
- **Subject resolution** (deterministic rules, in this order):
  1. two or more creature names in the beat -> the food-web plate;
  2. exactly one creature name -> that creature;
  3. a collective phrase ("creatures", "food web") or two or more creature
     claims -> the food-web plate;
  4. a beat that starts with "it/its/they/their" -> the creature of the
     previous beat (same chapter);
  5. a chapter that names exactly one creature -> that creature;
  6. keyword scoring against the habitat specs (unique winner, score >= 2);
  7. the habitat of the previous beat in the same chapter;
  8. otherwise the beat is **skipped** with a reason (never silently dropped).
- **Tags** (the evidence class of the image):
  - `SPECULATION` — the subject is an invented creature, or a claim is
    `SPECULATION` in the ledger;
  - `INFERENCE` — a real place with a hedged statement ("may", "could",
    "plausible") or a single-source claim;
  - `KNOWN` — a real place with a two-source claim and no hedge.
- **Fail closed:** a beat whose claim id is not in the ledger, or a required
  beat id that does not exist, raises `ImageBriefError` (the run blocks).

Pilot result (`projects/se_pilot/script.md`, 46 beats): **46 visual beats**,
0 skipped, tags KNOWN 23 / INFERENCE 7 / SPECULATION 16.

## 2. Budget

`budget = round(narration_minutes x images_per_minute)`, images per minute
**6-8** (default 7, out of range -> `BudgetError`). The pilot narration is
299.775 s (4.996 min) -> **35 images**. A brief that exceeds the budget is
truncated and the dropped beat ids are recorded in the plan and the state
(`truncated`, `dropped_beats`).

## 3. Batches and kernels

- Batch size 40-100 prompts (default 60), balanced: `ceil(total / batches)`
  per batch, so no batch is under 40 while the total allows it. A batch
  smaller than 40 is marked `partial` (a small budget, not a rule break).
- **One Kaggle kernel per batch.** The driver submits one batch per command
  call; there is no polling loop inside the tool (RUN_RULES §6).

## 4. Resume, retry, hashes

- Every render is tracked in `run_state.json` with its prompt sha256, seed,
  status and the sha256 of the fetched file.
- **Resume:** a render already verified by sha256 is never regenerated. The
  cached file is re-hashed on every `pending()` call — if it no longer
  matches, the render is re-queued (`hash mismatch`), never trusted.
- **Retry:** after a fetch, the failed renders only (missing image, missing
  file, hash mismatch, black frame, QC failure) go back into the queue and a
  new batch is planned for them. Verified images are never repeated.
- **Hard fail:** `finalize()` raises `RunError` when the number of usable
  images is lower than the number of prompts. The episode then has no
  complete image set (fail closed).

## 5. Owner-approved cache

`assets/illustrations/approved.json` holds the owner-approved images
(`render_id`, `prompt_sha256`, `sha256`, `file`, `approved_by`, `approved_utc`).
An approved prompt is **never regenerated** — a rerun reuses the approved
file. Only verified images can be approved (approval of an unverified render
raises `RunError`).

```bash
python scripts/run_episode_images.py approve --render-id r0027 --approved-by owner
```

## 6. Seed log and manifest

- `assets/illustrations/seed_log.jsonl`: one line per planned/submitted
  render (`render_id`, `beat_id`, `prompt_sha256`, `seed`, `model`, `batch`,
  `attempt`, `status`, `ts`). Append-only and deduplicated per
  (render_id, prompt_sha256); a seed is never reused inside a batch.
- `assets/illustrations/episode_manifest.json`: model + model_id, the
  **verified versions** (diffusers, transformers, torch, ...), the **params**
  (steps, guidance, dtype, scheduler, prompt target/variant, VAE, distilled
  UNet, install ladder), the budget, the brief hash, the tag counts and one
  entry per image (prompt, prompt sha256, seed, file sha256, QC).

## 7. The live job (24 images, locked model)

| Item | Value |
|---|---|
| Job | `ill-se_pilot-b1-klein` (kernel `forts845/openmontage-runner`) |
| Model | klein, 1344x768, 4 steps, guidance 1.0, fp16, CPU offload |
| Images | 24 (11 creature beats, 6 food-web plate beats, 7 habitat beats) |
| Budget | 4.996 min x 7 images/min = 35 (the job is a 24-image validation) |
| Seeds | 3000-3046 (one per image, in the reserved range) |
| Cost | 24 x 24.691 s + ~134 s load ≈ **12 min of T4 time** |

### Measured result of the live job (2026-10-22, kernel COMPLETE)

| Measure | Value |
|---|---|
| Images requested / generated | 24 / 24 (0 black, 0 NaN, 0 OOM) |
| Model load | 121.74 s |
| **Steady seconds/image (measured)** | **25.287 s** (warmup excluded, kernel manifest) |
| Usable images/minute (kernel) | 2.15 |
| Peak VRAM | 7991.4 MB (T4, CPU offload) |
| **QC-passed (usable) images** | **11 / 24 = 45.8 %** |
| Failed | 13 (11 `blur_ok=false` - flat/low-detail plates; 2 `text_like=true` - text-like artifacts on the food-web plate beats) |
| Total GPU time | 121.74 s load + 24 x ~25.3 s ≈ **11.3 min of T4 time** |

Facts only: no judgement of beauty is made here, and no QC threshold was
changed (the failures are the configured thresholds doing their job).

**State after the live job:** 11 images `verified`, 13 `pending` (re-queued
with a **new seed** each - a retry changes something concrete: the seed is
re-drawn inside the reserved range with stride 64, and the seed log records
the retry line). `finalize()` therefore **fails closed**: "only 11 usable
images for 24 prompts (13 failed) - the episode image set is incomplete".

**No second live job was submitted** (this milestone ran ONE live job). The
retry batch is planned and ready: `python scripts/run_episode_images.py submit`
pushes only the 13 failed prompts with their new seeds.

## 8. Usage

```bash
python scripts/run_episode_images.py brief                 # write the brief
python scripts/run_episode_images.py plan                  # budget + batches
python scripts/run_episode_images.py submit                # ONE kernel
python scripts/run_episode_images.py status                # ONE status call
python scripts/run_episode_images.py fetch                 # verify + QC
python scripts/run_episode_images.py finalize              # hard fail if short
python scripts/run_episode_images.py approve --render-id r0027
```

## 9. Known limits

- The subject resolution is a rule set over the script text, not a language
  model; a beat it cannot resolve is skipped (recorded) and can be forced
  with `--beat` (required beats) or `--select` (explicit render ids).
- The brief covers the *stills* of the episode; the footage plan (real NASA
  material) is a separate track and is not touched here.
- Nothing in this pipeline judges the images; the usable share is a
  technical measure (fetched, hash-verified, non-black, QC-passed).
