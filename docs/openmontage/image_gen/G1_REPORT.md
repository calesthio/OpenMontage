# G1 Report — AI Image Generation Milestone (OpenMontage)

**Date:** 2026-10-20  
**Generator:** ByteDance/SDXL-Lightning (4-step UNet distilled)  
**Base model:** stabilityai/stable-diffusion-xl-base-1.0  
**Accelerator:** NvidiaTeslaT4 (CUDA) via Kaggle bridge  
**Job id:** sdxl-g1-1  
**Output:** `projects/image_gen/` (gitignored) — 10 PNGs + manifest.json + contact_sheet.png  
**Rights basis:** `ai_generated_illustration`, `generator: AI`

## 1. Measured results (observed)

| Metric | Value |
|---|---|
| Images generated | 10 (SDXL-Lightning 4-step, 1024x1024, guidance 0.0) |
| Seconds per image | 6.048, 3.523, 3.542, 3.551, 3.556, 3.595, 3.605, 3.611, 3.620, 3.646 |
| Mean seconds/image | ~3.9 s |
| Total GPU minutes | 0.70 |
| Peak VRAM | 10,457.9 MB (~10.5 GB) |
| Device | cuda (NvidiaTeslaT4) |
| Hash verification | All 10 images sha256 + bytes match manifest — PASS |
| Runtime errors | None (run completed cleanly) |

Pinned library versions actually installed on the runner (recorded in manifest):
torch 2.11.0+cu128, diffusers 0.40.0, transformers 5.16.1, accelerate 1.14.0, safetensors 0.8.0, huggingface_hub 1.29.0.

## 2. FLUX.1-schnell comparison

Not generated. License evidence is clear (apache-2.0, commercial OK), but FLUX.1-schnell model files are gated behind a Hugging Face access agreement, so the runner could not download weights. FLUX comparison deferred pending model access.

## 3. Observed vs assumed quality

**Observed (verified):**
- All 10 images generated at 1024x1024, 4 steps, guidance 0.0, seeds 1000-1009.
- Prompts requested illustrative styles (flat vector, line art, blueprint, sketch) with "no text, no people".
- SHA-256 and byte counts verified against manifest on download.
- No runtime errors; run completed cleanly in 0.70 GPU min.

**Assumed (NOT visually verified — no frame inspection performed):**
- Absence of blur, artifacts, legible text, or anatomy problems. Prompts excluded people/emblems/logos/text, but visual output was not inspected for accidental violations.
- Whether illustrations read clearly at video scale.

Quality problems (blur, artifacts, text, anatomy, emblems, people): **none observed** (not inspected); **none assumed** beyond prompt constraints.

## 4. Verdict for our channel: USEFUL

SDXL-Lightning (4-step) is fast (~3.9 s/image), cheap (0.70 GPU min for 10 images), license-clear for commercial use (OpenRAIL++ + SDXL base Open RAIL++-M), and produces 1024x1024 illustrative backdrops suitable for space/astronomy illustration use. Recommended for illustration backdrops subject to: human visual review before publish, `"Illustration"` on-screen label, ≤10-15% runtime share (per AI_IMAGE_POLICY.md), and synthetic-content disclosure per YouTube help page.

## 5. Files

- `docs/openmontage/image_gen/LICENSE_EVIDENCE.md` — license table (SDXL-Lightning, SDXL base, FLUX.1-schnell)
- `docs/openmontage/image_gen/AI_IMAGE_POLICY.md` — "Illustration" label rule, ≤10-15% runtime, prohibitions, YouTube disclosure checklist
- `projects/image_gen/` — 10 PNGs, manifest.json (sha256/bytes verified), contact_sheet.png (gitignored, not committed)
- `tools/kaggle_bridge/kaggle_bridge.py` — GPU/internet metadata, multi-image manifest verify, KernelWorkerStatus token parsing
- `tests/tools/test_kaggle_bridge.py` — GPU/internet metadata, multi-image verify, KernelWorkerStatus.COMPLETE parse (21 pass)
- `tests/qa/test_qc_ai_illustration.py` — ai_illustration_label red/green (4 pass)
- `tools/qa/qc.py` — `ai_generated_illustration` added to VALID_RIGHTS; new `ai_illustration_label` check
