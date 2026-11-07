# S1 State — Speculative Evolution / Alien Ecosystems (AI stills only) — Kilo

**Resume rule:** Resume at the first phase not DONE. Do not sleep or loop on Kaggle
status: submit once, record here, do other phases, check status with ONE call between
phases. Never commit media. KAGGLE_API_TOKEN: env check yes/no only (never print).

## Phase status

| Phase | Status | Evidence | Commit hash |
|-------|--------|----------|-------------|
| S1-1 IMAGE MODEL (Z-Image-Turbo) | RUNNING | job `s1-z-image-turbo-1` on `forts845/openmontage-runner` (GPU+internet), status RUNNING; 5th submission — fixed stack (hub 1.x + transformers 5.x + diffusers main + --force-reinstall), exact versions + diffusers commit recorded in manifest | f4e5eec+ |
| S1-1 SDXL Base | PENDING | next in order after Z-Image-Turbo; VAE madebyollin/sdxl-vae-fp16-fix; fp16 only; fail loudly if images < prompts | — |
| S1-1 FLUX.2-klein-4B | PENDING | last in order; license clear per LICENSE_EVIDENCE.md; ~13 GB VRAM — memory-fit TBD on T4 | — |
| S1-2 BLIND COMPARISON | BLOCKED | needs S1-1 images (>=1 USEFUL model) | — |
| S1-3 STYLE BIBLE | DONE | docs/openmontage/niches/speculative_evolution/{STYLE_BIBLE.md,speculative_evolution.yaml}; tools/illustration/s1_speculative_gate.py; tests/illustration/test_s1_speculative_gate.py (6 pass) | — |
| S1-4 PILOT SCRIPT + LEDGER | DONE | topic "How could life survive beneath a frozen alien ocean?" 10-12 min; claim ledger SE-01..SE-13; script 9 chapters + hook + 3 truthful titles; claim_ids_resolve QC PASS (48/48) | — |
| S1-5 BUILD | BLOCKED | requires S1-1 >= 1 USEFUL model | — |
| S1-6 CLOSE | PENDING | OWNER_ACTIONS.md, CHANGELOG.md, LESSONS.md, S1_STATE.md | — |

## S1-1 job records

| Model | Job id | Kernel slug | Prompts | Seeds | Seconds/image | Peak VRAM | GPU minutes | Revision | Manifest verified |
|-------|--------|-------------|---------|-------|---------------|-----------|-------------|----------|-------------------|
| Z-Image-Turbo | s1-z-image-turbo-1 | forts845/openmontage-runner | 12 (fixed) | 4000-4011 | TBD | TBD | TBD | main | NO |

## S1-1 submission detail

- Submitted: 2026-10-21 (this session); 5 submissions attempted (dependency-conflict fixes), currently RUNNING
- Job folder: /tmp/kilo/s1_jobs/s1-z-image-turbo-1 (not committed)
- Runner: tools/kaggle_bridge/s1_z_image_turbo_run.py (committed)
- Kaggle kernel: forts845/openmontage-runner, enable_gpu=true, enable_internet=true, timeout 3600s; status RUNNING (last checked this session)
- Model order (owner): Z-Image-Turbo (running) -> SDXL Base (VAE madebyollin/sdxl-vae-fp16-fix) -> FLUX.2-klein-4B; one model per kernel run.
- Exact stack pinned in kernel + recorded in manifest: diffusers (git commit), transformers 5.x, huggingface_hub 1.x, torch; fp16 only; fail loudly if images < prompts.
- 12 fixed prompts: 4 single-creature silhouettes, 3 habitat scenes, 2 anatomy-detail crops, 2 food-web background plates, 1 planet-surface wide; fixed seeds 4000-4011; 1024x1024; steps=9; guidance=0.0; dtype=float16
- g2-image-bakeoff NOT reused (G-rules: no further re-push)

## Notes

- LICENSE_EVIDENCE.md: Z-Image-Turbo (apache-2.0, commercial OK), FLUX.2-klein-4B (apache-2.0, commercial OK) — neither BLOCKED on license grounds (verified 2026-10-21 from official HF cards).
- G2 concluded FAILED (bitsandbytes missing, CPU fallback, dict-not-callable, FLUX OOM). S1-1: fp16 only, NO bitsandbytes, NO CPU fallback, non-zero exit if images < prompts, full tracebacks saved to output.
- Disk: 2.8 GB free on /workspaces (> 800 MB stop threshold).
- Tests passing: test_s1_z_image_turbo_run (3), test_s1_claim_ids (1), test_s1_speculative_gate (6), test_s1_contact_sheet (3), test_s1_edl (3), test_s1_qc (7 pass, 1 skip-imagehash).
