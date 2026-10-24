# S7 Bake-off — SDXL Base vs FLUX.2-klein-4B vs Z-Image-Turbo

**Milestone:** S7 (Kilo) · **Branch:** `factory/business-documentary-pilot` · **Date:** 2026-10-21
**Test set:** 10 fixed scenes x 3 models = 30 renders, 1024x1024, one seed per scene
shared by all three models (`docs/openmontage/image_gen/S7_TEST_SET.json`).
**Prompt variants** (best per `docs/openmontage/image_gen/PROMPTING_FACTS.md`,
rendered by `tools/prompting.builder`, read-only): SDXL = variant A (structured
phrases) + short negative prompt · Z-Image = variant B (prose, style first, no
negative) · klein = variant C (prose, anatomy first, no negative).

> **No model is declared the winner in this document.** The owner's blind CSV
> (`projects/s7_blind/results.csv`) decides. The agent's ranking below is
> advisory and is explicitly *agent opinion, not independent* — a vision model
> can miss anatomy errors and misread flat art.

---

## 1. Observed vs assumed

### Observed (verified against vendor sources / the live kernel)

| Fact | Source | Checked |
|---|---|---|
| FLUX.2-klein-4B is loaded with `Flux2KleinPipeline`, 4 steps, `guidance_scale=1.0`, `enable_model_cpu_offload()`, and the card's install line is `pip install git+https://github.com/huggingface/diffusers.git` | HF model card `black-forest-labs/FLUX.2-klein-4B` | 2026-10-21 |
| The HF model page for klein is tagged `Flux2KleinPipeline` (not `Flux2Pipeline`) | HF model page metadata | 2026-10-21 |
| `diffusers` 0.41.0 ships **both** `pipelines/flux2/pipeline_flux2_klein.py` and `pipelines/z_image/pipeline_z_image.py`; 0.37.0 does too | `raw.githubusercontent.com/huggingface/diffusers/v0.41.0/...` (HTTP 200) | 2026-10-21 |
| Z-Image-Turbo is loaded with `ZImagePipeline`, 9 steps (= 8 DiT forwards), `guidance_scale=0.0`, `low_cpu_mem_usage=False` | HF model card `Tongyi-MAI/Z-Image-Turbo` | 2026-10-21 |
| `Flux2KleinPipeline.__call__` defaults: 50 steps, `guidance_scale=4.0`; `ZImagePipeline.__call__` defaults: 50 steps, `guidance_scale=5.0`, `negative_prompt` accepted but ignored when guidance < 1 | diffusers 0.41.0 source | 2026-10-21 |
| Available releases: `diffusers` 0.41.0 (latest), `transformers` 5.20.2 and 4.57.6 | PyPI index | 2026-10-21 |
| The **S5** klein run died at `pipe.to("cuda")` with `NotImplementedError: Cannot copy out of meta tensor; no data!` (traceback saved) | fetched S5 kernel output | 2026-10-21 |
| S5 produced **0 usable images** for both SDXL and klein (SDXL output was overwritten by the klein push on the shared runner kernel) | fetched S5 kernel output + `S5_STATE.md` | 2026-10-21 |

### Assumed (not verified until the kernel answers)

- The Kaggle accelerator model and its VRAM (recorded in each manifest).
- That klein's Qwen3 text encoder loads under `transformers` 4.57.6 (the first
  rung of the ladder); the ladder falls back to `transformers` 5.20.2, then
  git-main diffusers.
- That `Flux2KleinPipeline` is the class the installed release exposes under
  the name used here (probed in-kernel with `python -c` before generating).
- fp16 instead of the vendor cards' bfloat16 — **mandated by S7**, a deliberate
  deviation, recorded so the numbers are comparable with the cards' claims.
- That 10 scenes x 1 seed is enough to separate the models on quality. It is
  a smoke test, not a benchmark.

---

## 2. Attempts log per model

<!-- FILLED: one row per attempt; what changed and the exact result -->

### SDXL Base 1.0 + `madebyollin/sdxl-vae-fp16-fix` — DONE (attempt 1)

| Rung | Stack installed | Result |
|---|---|---|
| 1 `released_041_x4` | diffusers 0.41.0 + transformers 4.57.6 + hub<1.0 | **DEAD** — pip `ResolutionImpossible`: diffusers 0.41.0 requires `huggingface-hub>=1.32,<2.0`, transformers 4.57.6 pins `hub<1.0` |
| 2 `released_041_x5` | diffusers 0.41.0 + transformers 5.20.2 + hub 1.x | **DEAD** — install OK, import failed: `cannot import name 'FqnToConfig' from 'torchao.quantization'` (kernel's torchao no longer exports it) |
| 3 `released_036_x4` | diffusers 0.36.0 + transformers 4.57.6 + hub<1.0 | **OK** — 10/10 images, verify PASS |

Attempt 1 of the model succeeded (on internal rung 3), so **1 attempt** was used.
The ladder was re-ordered afterwards: the two dead rungs are no longer tried
first for the other models.

### FLUX.2-klein-4B — DONE (attempt 1)

| Rung | Result |
|---|---|
| 1 `released_037_x4` (diffusers 0.37.0 + transformers 4.57.6 + hub<1.0) | **OK** — 10/10 images, verify PASS, pipeline `Flux2KleinPipeline` + `enable_model_cpu_offload()`, guidance 1.0 |

The S5 blocker is gone: S5 used the FLUX.2-**dev** class `Flux2Pipeline`, whose
Qwen3 text encoder left the pipeline on the meta device
(`NotImplementedError: Cannot copy out of meta tensor; no data!` at
`pipe.to("cuda")`). The vendor class `Flux2KleinPipeline` loads and runs.
**1 attempt** used.

### Z-Image-Turbo — see the table below

### SDXL media regeneration — attempt 2

The sandbox was restarted mid-milestone and `/tmp` was wiped, which deleted the
SDXL PNGs; the Kaggle runner kernel keeps only the output of its **latest**
version (the `owner/kernel/version` CLI argument returns the latest output for
every version — checked for versions 1..5), and the klein run had already
overwritten the SDXL output. SDXL was therefore re-run (attempt 2) with the
same 10 seeds purely to regenerate the media. Attempt 2 starts at rung
`released_037_x4` (diffusers 0.37.0), the rung that worked for klein; run 1's
manifest (sha256, timings) remains the performance record.

---

## 3. Speed / VRAM table

<!-- FILLED: load time, steady s/image, usable images per minute, peak VRAM,
     black/NaN/OOM, attempts needed, exact versions -->

---

## 4. Objective QC (flags only)

<!-- FILLED: per-image Laplacian blur, text-like heuristic, dHash duplicates,
     resolution, saturation/contrast outliers -->

---

## 5. Agent advisory ranking

<!-- FILLED: rubric table + ranking + pick + confidence + weakest scenes -->

---

## 6. BLOCKED causes

<!-- FILLED -->

---

## 7. Exact owner steps

1. Open the blind pack folder (gitignored, on the machine that ran S7):
   `projects/s7_blind/`
2. On a phone, open `sheet_s01.png` … `sheet_s12.png` (10 sheets, 3 panels
   A/B/C each, a different random order per sheet, no model names).
3. Fill `projects/s7_blind/results.csv` — one row per scene:
   `scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,anatomy_ok_C,comment`
   (`best_panel` / `worst_panel` = A|B|C; `anatomy_ok_*` = yes|no).
   Do **not** open `mapping.json` before the CSV is filled — that is the blind.
4. Run the tally:
   ```bash
   python scripts/s7_tally.py
   ```
   It prints wins / losses / anatomy-ok per model, the speed + VRAM table,
   `TIE` when the top two are within one win, and `AGENT vs OWNER:
   agree/disagree` against the agent's advisory pick. The owner's row is the
   decision; the agent's pick never overrides it.
5. The winner is then written into `docs/openmontage/image_gen/BAKEOFF_S7.md`
   section "Winner (owner-decided)" and the milestone is closed.

**Stopping the Codespace when the run is over** (nothing is lost: images live in
`/tmp/kilo/s7_out/` on the Codespace and the manifests/text logs are committed):

```bash
# stop this Codespace from the shell
gh codespace stop -c scaling-spoon-wv7wq975xwqjhgqgx
# or from the CLI without naming it (stops the current Codespace)
gh codespace stop
# or in the browser: github.com/codespaces -> right-click the Codespace -> Stop
```

Note: `/tmp/kilo/s7_out/` (the PNGs) disappears when the Codespace stops. Copy
the folder somewhere durable **before** stopping if the images are still
needed; the committed manifests, QC report and the blind sheets are enough to
tally, but not to re-inspect the raw frames.
