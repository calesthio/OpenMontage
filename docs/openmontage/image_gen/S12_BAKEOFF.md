# S12 — model bake-off (free Kaggle T4)

**Scope:** 3 models x 6 S10 scenes (s01, s03, s05, s06, s10, s12) x 3 seeds
(1001, 2027, 4409) = 54 images, 1024x1024, fp16. Each model ran in a **separate
fresh Kaggle kernel** (never multiple dependency stacks in one kernel).
torch/diffusers/transformers versions pinned and logged per model
(diffusers 0.37.0, transformers 4.57.6, torch 2.11.0+cu128).

**Style:** the S10 owner scoring is not complete, so no winning S10 style
exists yet. All 54 images were rendered in the **flat-vector field-guide
style (S-A)** — that is the fallback stated in the task, not an agent style
judgment.

## Per-model results (verified, fail-closed sha256)

| model | scheduler | steps | cfg | load | median warm s/img | s per accepted img | peak VRAM alloc | peak VRAM reserved | black/NaN | status |
|---|---|---|---|---|---|---|---|---|---|---|
| black-forest-labs/FLUX.2-klein-4B (Flux2KleinPipeline, cpu offload) | pipeline default | 4 | 1.0 | 121.371s | 25.995 | 26.048 | 7995.02 MB | 8656.0 MB | 0 / 0 | PASS |
| Lykon/dreamshaper-xl-lightning (DPMSolverMultistepScheduler) | DPMSolverMultistepScheduler | 4 | 2.0 | 41.487s | 5.121 | 5.160 | 9968.01 MB | 12828.0 MB | 0 / 0 | PASS |
| Lykon/dreamshaper-xl-1-0 (DEISMultistepScheduler) | DEISMultistepScheduler | 25 | 5.5 | 87.697s | 26.259 | 25.546 | 9968.01 MB | 12828.0 MB | 0 / 0 | PASS |

- klein: 18/18 generated, install rung 1 (released_037_x4) on first attempt.
- dreamshaper-xl-lightning: 18/18 generated, stock VAE, no black frames.
- dreamshaper-xl-1-0: 18/18 generated with **stock VAE** — no black/NaN, so the
  madebyollin/sdxl-vae-fp16-fix fallback was **not** needed (spec: add VAE fix
  only if stock VAE gives NaN/black).
- No model errored; no retry was used (one retry per model max was allowed but
  not required).
- Every image's sha256 and byte count verified against the kernel manifest
  (fail-closed bridge `verify`, verdict PASS on all 3 models).

## Per-image CSV

`docs/openmontage/image_gen/S12_RESULTS.csv` — 54 rows:
model_id, revision, dtype, scheduler, steps, cfg, width, height, seed, scene_id,
load_time, warm_render_time (first image per model excluded as warm-up),
peak_vram_allocated, peak_vram_reserved, black_or_nan_flag, output_file.

Per-model stats in `docs/openmontage/image_gen/S12_STATS.json`. Per-kernel logs
(incl. install log and versions) under
`docs/openmontage/image_gen/logs/s12-klein-1/`,
`.../s12-dreamshaper-xl-lightning-1/`,
`.../s12-dreamshaper-xl-1-0-1/`.

## Pass gates

| gate | threshold | result |
|---|---|---|
| 0 black/NaN | 0 / 54 | PASS |
| usable without repair | >= 12 / 18 per seed cohort | PASS: seed 1001 = 18/18, seed 2027 = 18/18, seed 4409 = 18/18 |
| correct anatomy (part count) | >= 14 / 18 per seed cohort | NOT_CHECKED — owner blind scoring only; no LLM anatomy judgment |
| caption space | >= 15 / 18 per seed cohort | NOT_CHECKED — owner blind scoring only |

Per quality-gate rule, a check that cannot be performed is NOT_CHECKED, never
PASS. Anatomy and caption space require the owner's blind scores.

## Blind contact sheets (owner scoring)

`projects/s12_blind/` (gitignored): 9 phone-sized sheets (750x1334, 6 tiles),
tiles coded A1..A54 in a fixed random order, **no model names**, blank
caption-zone band under every tile. `mapping.json` (code -> model/scene/seed)
is separate and must not be opened before scoring.csv is filled.
`scoring.csv` template: code, scene_id, seed, correct_part_count, caption_space,
comment. Tally with `python scripts/s12_tally.py` once the owner fills it.

## Primary / fallback model

- **Primary:** Lykon/dreamshaper-xl-lightning — fastest (5.16 s/img accepted,
  ~5x faster than klein/xl-1-0), 0 failures, 18/18 usable, lowest load time
  (41.5s). VRAM within T4 limits (9968 MB allocated).
- **Fallback:** black-forest-labs/FLUX.2-klein-4B — 0 failures, 18/18 usable,
  proven stack; 26 s/img, higher load (121s).
- dreamshaper-xl-1-0 also ran clean (0 failures) but is 5x slower than the
  lightning model at 25 steps, so it is not the primary pick.

Anatomy and caption-space gates remain owner-judged; if the owner's blind
scoring reverses the speed/reliability ranking, the fallback can become primary
with no code change.

## Artifacts

- `docs/openmontage/image_gen/S12_RESULTS.csv` — per-image CSV (54 rows)
- `docs/openmontage/image_gen/S12_STATS.json` — per-model + per-cohort stats
- `docs/openmontage/image_gen/S12_BAKEOFF.md` — this report
- `docs/openmontage/image_gen/logs/s12-*-*/` — kernel status, manifest,
  install log, versions (committed record, no media)
- `/tmp/kilo/s12_out/*/s12_bakeoff_*/images/*.png` — generated images (not
  committed; media stays out of git)
- `projects/s12_blind/` — blind sheets, mapping, scoring template (gitignored)

No commits made.
