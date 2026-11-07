# S4 State — Speculative Evolution Model Bakeoff (AI stills only) — Kilo

**Resume rule:** Resume at the first phase not DONE. Do not sleep or loop on Kaggle
status: submit once, record here, do other phases, check status with ONE call between
phases. Never commit media. KAGGLE_API_TOKEN: env check yes/no only (never print).
STOP RULE: max 2 fix attempts per model; after that mark the model BLOCKED with the
exact error, versions and traceback path, and move on. Do not chase dependency conflicts
for hours.

## Phase status

| S4-2 RUN ORDER (fp16, version pins in manifest) | IN_PROGRESS | 1) Z-Image-Turbo BLOCKED (max fix attempts reached — see below); 2) SDXL Base + madebyollin/sdxl-vae-fp16-fix — SUBMITTED s4-sdxl-1, RUNNING with released diffusers (fix attempt 2/2 succeeded); 3) FLUX.2-klein-4B PENDING | — |
| S4-1 VERIFY PROMPTING CLAIMS | DONE | docs/openmontage/image_gen/PROMPTING_FACTS.md; official cards fetched (Z-Image, SDXL, BFL FLUX); diffusers z_image + FluxPipeline docs CONFIRM | — |
| S4-3 PROMPT-RULE EXPERIMENTS | DONE | scripts/s4_verify_prompt_experiments.py 12/12 assertions pass via tools/prompting.builder (read only); variants saved to docs/openmontage/image_gen/S4_PROMPT_EXPERIMENT_VARIANTS.json | — |
| S4-4 BLIND PACK FOR OWNER | PARTIAL | scorer (OpenCode-owned scripts/score_rubric.py) proven on dummy CSV: loads, validates, computes cell metrics, reports INSUFFICIENT when <24 images/cell; contact sheets + mapping BLOCKED pending generated images from S4-2 | — |
| S4-5 MODEL_BAKEOFF_REPORT | PENDING | docs/openmontage/image_gen/MODEL_BAKEOFF_REPORT.md not started — blocked pending S4-2 image results | — |
| S4-6 CLOSE | PARTIAL | LESSONS.md (dependency-conflict lesson + pinning rule) + CHANGELOG.md (S4 section) done; S4_STATE.md, stop commands pending close | — |

## Model run order (one model per kernel run, fp16 only)

1. Z-Image-Turbo — BLOCKED (max fix attempts reached). Last error:
   `RuntimeError: Failed to import diffusers.pipelines.z_image.pipeline_z_image`
   caused by `diffusers.loaders.single_file` import failure (transformers 5.x +
   git-main diffusers incompatibility). Traceback: /kaggle/src/script.py line 261
   (kernel log, fetched to /tmp/kilo/s1_output/s1-z-image-turbo-1). Stack used:
   huggingface-hub 1.x + transformers 5.x + diffusers git main (+ --force-reinstall).
   Jobs attempted: 5+. Per S4 stop rule, moving on without further Z-Image attempts.
2. SDXL Base + madebyollin/sdxl-vae-fp16-fix — SUBMITTED s4-sdxl-1 (job folder
   /tmp/kilo/s4_jobs/s4-sdxl-1, 72 images, RUNNING with released diffusers fix
   (fix attempt 2/2 succeeded); awaiting completion.
3. FLUX.2-klein-4B — PENDING (waiting on SDXL result / one status call between phases).

## Per-model run matrix (owner change: 2 seeds per scene → 24 images per cell)

- 12 scenes x 2 seeds x 3 variants (A tags / B prose / C anatomy-first) = 72 images per model
- 3 models = 216 renders total
- seeds: 4000-4011 (2 per scene), aspect 16:9, 1280x720
- same seed per scene across model/variant combos
- neutral render IDs (blind), mapping separate

## Notes

- OpenCode owns tools/prompting/ and scripts/score_rubric.py: USE them, do NOT edit; write change requests to docs/openmontage/OPENCODE_REQUESTS.md
- S1_STATE.md: Z-Image-Turbo license apache-2.0 (commercial OK), FLUX.2-klein-4B apache-2.0 (commercial OK) — neither BLOCKED on license
- SDXL license: CreativeML Open RAIL++-M (verified from HF card)
- Disk: 2.8 GB free on /workspaces (> 800 MB stop threshold)
