# IMAGE ENGINE CONFIG — the locked image model (P1)

**Config (single source of truth):** `config/image_engine.json`
**Adapter interface:** `tools/illustration/model_registry.py`
**CLI:** `python scripts/image_engine.py {status|project|select}`
**Rules:** `docs/openmontage/RUN_RULES.md` (fail-closed, $0, no silent threshold changes)
**Roles:** inline, not independent.

## 1. What is locked right now

| lock field | value |
|---|---|
| `model` | `klein` (FLUX.2-klein-4B) |
| `status` | `OWNER_GATED` — the agent advisory pick; the owner's blind scores are not in yet |
| `scheduler` | pipeline default (`class: null`) — the measured S7 run applied no scheduler override |
| `steps` | 4 |
| `guidance` | 1.0 |
| `dtype` | `float16` (no bf16, no bitsandbytes, no CPU fallback) |
| `prompt_variant` | `C` (klein target: prose, anatomy first, no negative prompt) |
| `seed_policy` | range 3000-3999 reserved for illustrations; one fixed seed per niche+subject, recorded in the manifest (`ILLUSTRATION_STYLE_BIBLE.md` §3) |
| `fallback` | `sdxl-lightning` — role `FAST_FALLBACK`, status `DECLARED`, drafts only |

**Why `klein`:** the agent advisory pick in both S7 and S8
(`S7_AGENT_ASSESSMENT.json`, `S8_AGENT_ASSESSMENT.json`; confidence medium).
The owner's blind CSV is **not filled**: `projects/s7_blind/results.csv` 0/10
scenes, `projects/s8_blind/results.csv` 0/10 scenes. No owner winner exists,
so the model stays `OWNER_GATED` and is **not waited on**.

**Why SDXL-Lightning is the declared FAST FALLBACK:** it is the fastest
verified model (3.943 s/image vs 24.691 s/image for klein on the same
Kaggle T4, 10/10 verified images, 0 black frames). It is declared for
**draft** renders only; every draft stays `NOT_PUBLISHABLE` until the owner
confirms the model.

**Owner action (one step):** open `projects/s8_blind/` (10 sheets, 4 panels
A-D) or `projects/s7_blind/` (10 sheets, 2 panels A-B), fill `results.csv`,
then run:

```bash
python scripts/s7_tally.py --csv projects/s8_blind/results.csv \
                           --mapping projects/s8_blind/mapping.json
python scripts/image_engine.py select --write
```

`select --write` re-locks the config to the owner's winner with status
`OWNER_CONFIRMED`. A TIE is **not** resolved by the agent: the config stays
untouched.

## 2. Model registry (every model is one config entry)

Each entry carries its verified library versions, its prompt rules (from
`tools/prompting`, read only) and its measured seconds/image from the kernel
manifest it cites. Changing the model is a JSON edit — no code change.

| model | model_id | pipeline | prompt target/variant | steps / guidance | scheduler |
|---|---|---|---|---|---|
| `klein` | black-forest-labs/FLUX.2-klein-4B | Flux2KleinPipeline | klein / C | 4 / 1.0 | default |
| `sdxl-lightning` | stabilityai/stable-diffusion-xl-base-1.0 + `ByteDance/SDXL-Lightning/sdxl_lightning_8step_unet.safetensors` | StableDiffusionXLPipeline | sdxl / A | 8 / 0.0 | EulerDiscreteScheduler (trailing) |
| `dreamshaper-xl-lightning` | Lykon/dreamshaper-xl-lightning | StableDiffusionXLPipeline | sdxl / A | 4 / 2.0 | DPMSolverMultistepScheduler |
| `sdxl` | stabilityai/stable-diffusion-xl-base-1.0 (+ `madebyollin/sdxl-vae-fp16-fix`) | StableDiffusionXLPipeline | sdxl / A | 50 / 7.5 | default |
| `zimage` | Tongyi-MAI/Z-Image-Turbo | ZImagePipeline | zimage / B | 9 / 0.0 | default — **BLOCKED** (0 usable images) |

Verified stacks (all measured on a Kaggle Tesla T4, Python 3.13.15, CUDA 12.8):

| model | diffusers | transformers | huggingface_hub | torch | measured job |
|---|---|---|---|---|---|
| `klein` | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `s7-klein-1` |
| `sdxl-lightning` | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `s8-sdxl-lightning-2` |
| `dreamshaper-xl-lightning` | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `s8-dreamshaper-xl-1` |
| `sdxl` | 0.36.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `s7-sdxl-1` |
| `zimage` | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `s7-zimage-4` (10/10 black frames) |

Licences (commercial use allowed, use-based restrictions apply):
`klein` apache-2.0; `sdxl-lightning` openrail++ (distilled from
`stable-diffusion-xl-base-1.0`, CreativeML Open RAIL++-M);
`dreamshaper-xl-lightning` openrail++; `sdxl` openrail++;
`zimage` apache-2.0. Evidence: `LICENSE_EVIDENCE.md` and
`S8_CANDIDATE_FACTS.json` (official cards, with access dates).

## 3. Measured speeds and the projected GPU cost for 100 images

Measured values are copied from the kernel manifests; the projections are
computed from them by `project_gpu_minutes()` (no invented numbers).

| model | load s | **s/image (measured)** | usable img/min | peak VRAM MB | usable images | **100 images: render min** | **100 images: total min (incl. load)** |
|---|---|---|---|---|---|---|---|
| `klein` | 133.9 | **24.691** | 2.17 | 7995 | 10/10 | **41.15** | **43.38** |
| `sdxl-lightning` | 73.5 | **3.943** | 12.51 | 9168.6 | 10/10 | **6.57** | **7.80** |
| `dreamshaper-xl-lightning` | 38.5 | **5.112** | 10.12 | 9968.01 | 10/10 | **8.52** | **9.16** |
| `sdxl` | 86.2 | **41.400** | 1.42 | 9169.58 | 10/10 | **69.00** | **70.44** |
| `zimage` | 277.6 | 51.908 | **0.00** | 12355 | **0/10** | **BLOCKED** | **BLOCKED** |

Reading of the numbers:

* `klein` needs **~43 min of T4 time for 100 images**; `sdxl-lightning`
  **~8 min** — 5.6x cheaper. One 10-minute episode at the planned 84 images
  costs **34.6 min render / 36.8 min total** (klein) or **5.5 / 6.7 min**
  (SDXL-Lightning) of GPU time; DreamShaper XL Lightning is **7.2 / 7.8 min**
  and SDXL Base **58.0 / 59.4 min**.
* The projections are **one kernel load + N renders**; a re-run that reuses
  the cache costs only the render minutes.
* `zimage` has no projection: it produced 10 black frames and 0 usable
  images, so no timing claim can be made for it (fail-closed).
* The measurements are from 1024x1024 S7/S8 bake-off renders; the episode
  pipeline renders 1344x768, so the real cost can differ — the projection is
  an estimate from the measured rate, not a guarantee.

## 4. How the swap works

```bash
# 1. edit the lock
python - <<'PY'
import json, pathlib
p = pathlib.Path("config/image_engine.json")
doc = json.loads(p.read_text())
doc["model"] = "sdxl-lightning"      # <- the only change
p.write_text(json.dumps(doc, indent=2) + "\n")
PY

# 2. the pipeline now uses the other model (no code change)
python scripts/run_illustrations.py plan --episode se_pilot --per-spec 14
```

`plan_renders()` takes the prompt target, the prompt variant, the steps and
the guidance from the config entry; `build_job()` takes the model id, the
pipeline class, the VAE, the distilled-UNet checkpoint, the scheduler, the
install ladder and the measured timings. The job payload carries a
`model_config` block, so the Kaggle-side runner needs **no** hard-coded table
for a new model (`resolve_model_plan()` in
`tools/kaggle_bridge/s7_bakeoff_run.py`).

Verified by test (`tests/illustration/test_image_engine_config.py`): for every
registered model, only the JSON changes and the same pipeline
(plan → build job → generator → verify → label + QC) runs unchanged against
the fake generator (`FakeGenerator`, no GPU, no network, no Kaggle).

## 5. Not done / open

* The owner has not blind-scored the models yet → `OWNER_GATED`.
* The kernel-side change (config-driven pipeline candidates, scheduler
  override, distilled-UNet swap) is **unit-tested locally only**; no Kaggle
  job was submitted in this milestone (P1), so the runner is `NOT_RUN` on
  Kaggle for the Lightning models.
* `zimage` stays BLOCKED: unblocking needs an owner decision (bfloat16 or a
  bigger GPU).
