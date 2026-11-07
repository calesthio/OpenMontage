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
| `Flux2KleinPipeline` + `enable_model_cpu_offload()` loads and runs on the T4: 10/10 frames, bridge verify PASS, 24.691 s/image, 7995.02 MB peak VRAM | `logs/s7-klein-1/manifest.json` | 2026-10-21 |
| SDXL Base 1.0 + `madebyollin/sdxl-vae-fp16-fix` runs at 41.4 s/image, 9169.58 MB peak VRAM, diffusers 0.36.0 | `logs/s7-sdxl-1/manifest.json` | 2026-10-21 |
| The same SDXL stack + seeds reproduced run 1 **bit-for-bit** (all 10 sha256 identical) | `logs/s7-sdxl-1/manifest.json` vs `logs/s7-sdxl-2/manifest.json` | 2026-10-21 |
| diffusers 0.41.0 cannot be installed with transformers 4.57.6 (`ResolutionImpossible`: 0.41.0 wants hub>=1.32, transformers 4.x pins hub<1.0) and with transformers 5.x it fails to import (`cannot import name 'FqnToConfig' from 'torchao.quantization'`) | `logs/s7-sdxl-1/install_log.json` | 2026-10-21 |
| Z-Image-Turbo in fp16 on this T4 produces **NaN** and 10/10 black frames; the pipeline ignores `vae.config.force_upcast` and the NaN is already present before the VAE decode | `logs/s7-zimage-{2,3,4}/kernel.log` + `S7_CHECKS.json` | 2026-10-21 |
| The Kaggle runner keeps only the output of its **latest** kernel version; the `owner/kernel/version` CLI argument returns the latest output for every version | `kaggle kernels output .../1 .. /5`, all returning the klein run | 2026-10-21 |

### Assumed (not verified until the kernel answers)

- The Kaggle accelerator model and its VRAM (recorded in each manifest).
- ~~That klein's Qwen3 text encoder loads under `transformers` 4.57.6~~ -
  **verified**: diffusers 0.37.0 + transformers 4.57.6 loads it (rung 1).
- ~~That `Flux2KleinPipeline` is the class the installed release exposes~~ -
  **verified**: the in-kernel probe found it in diffusers 0.37.0 and the run
  produced 10 valid frames.
- fp16 instead of the vendor cards' bfloat16 — **mandated by S7**, a deliberate
  deviation, recorded so the numbers are comparable with the cards' claims.
- That 10 scenes x 1 seed is enough to separate the models on quality. It is
  a smoke test, not a benchmark.
- That Z-Image-Turbo needs a precision the S7 brief does not allow (bf16) or a
  larger GPU than the 16 GB T4 - **not verified, needs an owner decision**
  (section 6).

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

All numbers come from the kernel manifests (`docs/openmontage/image_gen/logs/*/manifest.json`).
"steady s/image" excludes the first (warm-up) image; "usable img/min" counts
only frames that are neither black nor NaN.

| model | job | load s | steady s/img | usable img/min | peak VRAM MB | black/NaN/OOM | attempts | diffusers | transformers | hub | torch | GPU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SDXL Base 1.0 | `s7-sdxl-1` | 86.233 | 41.400 | 1.42 | 9169.58 | 0/0/0 | 1 (rung 3 of 3) | 0.36.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | Tesla T4 |
| SDXL Base 1.0 (media re-run) | `s7-sdxl-2` | 90.629 | 42.977 | 1.38 | 9169.58 | 0/0/0 | re-run of run 1 | 0.36.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | Tesla T4 |
| FLUX.2-klein-4B | `s7-klein-1` | 133.852 | 24.691 | 2.17 | 7995.02 | 0/0/0 | 1 (rung 1) | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | Tesla T4 |
| Z-Image-Turbo | `s7-zimage-4` | 277.644 | 51.908 | 0.00 (1.15 raw) | 12355.12 | **10**/0/0 | 4 (cap) -> BLOCKED | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | Tesla T4 |

Common stack for every run: accelerate 1.14.0, safetensors 0.8.0, numpy 2.1.3,
pillow 12.3.0, CUDA 12.8, Python 3.13.15, fp16 (mandated), no bitsandbytes,
no CPU fallback (CPU *offload* only, compute stays on the GPU).

**Reproducibility (bonus result).** The SDXL media re-run used the identical
stack, seeds and config as run 1 and produced **bit-identical frames** — all
10 sha256 values match run 1's committed manifest. Same seed + same stack +
same GPU = the same image, so the SDXL numbers are repeatable, not a fluke.

klein is 1.7x faster per image than SDXL and needs 1.2 GB less VRAM. Both
clear the 16 GB T4; Z-Image-Turbo needs 12.4 GB and still failed (section 6).

---

## 4. Objective QC (flags only)

`docs/openmontage/image_gen/S7_CHECKS.json` (30 images, machine-generated).
Flags only — nothing here judges beauty, anatomy or style.

| model | images | resolution bad | blur (abs) | blur (rel. to scene median) | text-like | saturation outlier | contrast outlier | duplicate pairs |
|---|---|---|---|---|---|---|---|---|
| sdxl | 10 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| klein | 10 | 0 | 0 | 8 | 1 | 2 | 3 | 0 |
| zimage | 10 | 0 | **10** (all frames are pure black) | 0 | 0 | 0 | 0 | **45** (all frames identical) |

**What the text-like heuristic got wrong** (it is a heuristic, not OCR):
it flagged 3 SDXL frames — of which only 1 (the s10 food-web plate) really
carries text; the two s01 poster frames it missed are the *worst* offenders
(whole blocks of fake lettering). Conversely it flagged one klein frame that
has no text at all (the lime mat outlines read as lettering) and missed the two
klein plates that do carry garbled labels. The visual review in section 5 is
the authority on text; the heuristic only says "look here".

**Blur flags (klein, 8 relative flags):** klein's frames are flat vector art
with large smooth areas, so the Laplacian variance is low and spread out
inside a scene. Inside one scene the relative rule fires whenever one frame
is much smoother than its neighbour — that is a property of flat-vector art,
not a defect. No absolute-blur flag fired for either working model.

---

## 5. Agent advisory ranking

**Label: agent opinion, not independent.** A vision model can miss anatomy
errors and misread flat art. The owner's blind CSV decides the winner.

Method: all 20 usable frames (SDXL 10 + klein 10) were opened and scored on
the OpenCode rubric (`scripts/score_rubric.py`, read-only): 0-2 per dimension
— anatomy, geometry, count/relation, texture, text, usefulness. 0 = severe
defect, 2 = clean. The per-image sheet is
`docs/openmontage/image_gen/S7_AGENT_REVIEW.csv`; the aggregate is
`docs/openmontage/image_gen/S7_AGENT_ASSESSMENT.json`.

| model | severe scores (0s) | images with a 0 | usable images | repair burden | s/img | ranking |
|---|---|---|---|---|---|---|
| **klein** | **6** | 4/10 | **5/10** | **0.583** | 24.691 | **1** |
| sdxl | 20 | 9/10 | 1/10 | 1.050 | 41.400 | 2 |

**Agent pick: klein — confidence: medium.**
(klein also wins on speed and VRAM, so the ranking is not close; "medium"
because this is 10 scenes x 1 seed scored by a non-human reviewer, and the
owner's blind score is what counts.)

Weakest scenes (a 0 on any dimension): klein — s03, s04, s01 (the food-web
plates s10/s11 carry garbled labels; s03/s04 get an eye the brief forbids);
sdxl — s09, s01, s08, s04 (wrong subject, busy poster collages, garbled text).

Per-scene picture (agent view, 0-2 per dimension, A=anatomy, G=geometry,
C=count/relation, T=texture, X=text, U=usefulness):

| scene | sdxl | klein |
|---|---|---|
| s01 vent grazer | 0 1 0 2 0 0 — poster collage, many creatures, fake text | 1 2 0 2 2 1 — clean silhouette, but 4 legs not 6 |
| s03 filter drifter | 1 1 1 1 2 1 — painterly jellyfish scene | 1 2 0 0 2 1 — photoreal fish with a visible eye |
| s04 ice burrower | 0 1 0 2 2 0 — wrong subject (fish shoal) | 1 2 0 1 2 1 — segmented burrower, visible eye |
| s05 chimney field | 2 1 2 0 2 1 — right subject, painterly neon | 2 2 2 2 2 2 — flat-vector black smokers, on brief |
| s06 under-ice cavern | 2 1 2 0 2 1 — photoreal cavern | 2 1 2 2 2 1 — flat-vector, subject ambiguous |
| s08 forelimb detail | 0 1 0 0 2 0 — spiky blob, no limb | 1 2 1 2 2 1 — flat-vector digits, no body context |
| s09 filter mouth | 0 0 0 1 2 0 — abstract mesh, no subject | 1 2 1 1 2 1 — glowing ring, too abstract |
| s10 food web | 1 1 0 2 1 1 — good plate, wrong limb count | 1 2 1 2 0 1 — good plate, garbled labels |
| s11 food web | 1 1 1 2 0 1 — on-palette, garbled captions | 1 2 2 2 0 1 — on-palette, garbled captions |
| s12 frozen surface | 2 1 2 0 2 1 — photoreal ochre surface | 2 2 2 1 2 1 — teal ice, plumes from below |

Read-across: SDXL's failure mode is *drifting off the brief* (photoreal
renders, busy collages, invented text) and it is twice as slow. klein's
failure mode is *small spec slips* (a 4-legged "6-limbed" grazer, an eye on a
"0-eyed" drifter, labels on a "text-free" plate) while the flat-vector style
and the palette land almost every time.

---

## 6. BLOCKED causes

**Z-Image-Turbo (`Tongyi-MAI/Z-Image-Turbo`) — BLOCKED after 4 attempts,
0 usable images.** Evidence: `docs/openmontage/image_gen/logs/s7-zimage-{1,2,3,4}/`.

| attempt | change | result |
|---|---|---|
| 1 | vendor card config (fp16, `low_cpu_mem_usage=False`, no offload) | **BLOCKED at load** — `torch.OutOfMemoryError`: 14.49 GiB already in use on a 14.56 GiB T4. Traceback: `logs/s7-zimage-1/traceback_load.txt` |
| 2 | `enable_model_cpu_offload()` (the klein-proven fix) | ran to COMPLETE, 10/10 files, bridge verify PASS — but **every frame is pure black** (`max == 0`, 3129 bytes each). Kernel log: `diffusers/image_processor.py:142: RuntimeWarning: invalid value encountered in cast` |
| 3 | + `pipe.vae.config.force_upcast = True` (fp32 decode) | still 10 black frames — `ZImagePipeline` never calls `upcast_vae()`, so the flag is inert |
| 4 | + VAE cast to fp32 explicitly, before the offload hooks | still 10 black frames -> the NaN is produced **before** the VAE, inside the fp16 DiT / text-encoder path |

Root cause (evidence-backed): the frames empty out because of an fp16
numerical overflow, not because of the image pipeline plumbing. The vendor
card for this model specifies **bfloat16**; the S7 brief mandates **fp16
only**, so the remaining fix needs an owner decision. Objective confirmation:
all 10 frames are identical (45 duplicate pairs) and every one has Laplacian
variance 0.0.

**Owner options to unblock Z-Image (needs approval, not an agent decision):**
1. allow bfloat16 for this model (one more kernel run, ~15 min) — the vendor's
   own precision, and the only change not yet tried;
2. use a 24 GB GPU so the model runs without CPU offload (attempt 1's failure
   mode disappears) — this also tests whether the offload path is contributing;
3. keep Z-Image out of the pipeline and continue with SDXL + klein.

**SDXL media re-run** — not a model failure: the sandbox was restarted and
`/tmp` was wiped, deleting the fetched PNGs, and the Kaggle runner keeps only
the output of its latest version, so the images were regenerated with the
identical stack and seeds. The re-run reproduced run 1 **bit-for-bit** (all
10 sha256 match), which is recorded in `logs/s7-sdxl-2/manifest.json`.

---

## 7. Exact owner steps

1. Open the blind pack folder (gitignored, on the machine that ran S7):
   `projects/s7_blind/`
2. On a phone, open the 10 sheets in `projects/s7_blind/`
   (`sheet_s01.png`, `sheet_s03.png`, `sheet_s04.png`, `sheet_s05.png`,
   `sheet_s06.png`, `sheet_s08.png`, `sheet_s09.png`, `sheet_s10.png`,
   `sheet_s11.png`, `sheet_s12.png`). Each sheet shows the SAME scene drawn by
   2 models, panels **A** and **B**, in a different random order per sheet, no
   model names. (Z-Image-Turbo is not in the pack: it is BLOCKED, section 6.)
3. Fill `projects/s7_blind/results.csv` — one row per scene:
   `scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,comment`
   (`best_panel` / `worst_panel` = A|B; `anatomy_ok_*` = yes|no).
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

**Stopping the Codespace when the run is over** (nothing needed for the
tally is lost: the blind sheets, the CSV template and the mapping live in
`projects/s7_blind/` on the machine, and the manifests/text logs are
committed):

```bash
# stop this Codespace from the shell
gh codespace stop -c scaling-spoon-wv7wq975xwqjhgqgx
# or from the CLI without naming it (stops the current Codespace)
gh codespace stop
# or in the browser: github.com/codespaces -> right-click the Codespace -> Stop
```

Note: the raw PNGs live in `/tmp/kilo/s7_out/` (and a copy in the gitignored
`output/s7_cache/`) and disappear when the Codespace stops; the committed
manifests, QC report, rubric sheet and the blind sheets are enough to tally
the bake-off, but not to re-inspect the raw frames.

---

## 8. Winner (owner-decided)

**Not decided yet.** The owner's blind CSV (`projects/s7_blind/results.csv`)
is still empty. Run `python scripts/s7_tally.py` after filling it; the tally
prints the owner's result, a `TIE` when the top two are within one win, and
the `AGENT vs OWNER: agree/disagree` line against the agent's advisory pick
(klein). The owner's row decides - the agent's pick never overrides it.

The agent's advisory ranking (section 5) is **klein > SDXL**, with
Z-Image-Turbo BLOCKED and therefore out of the comparison.
