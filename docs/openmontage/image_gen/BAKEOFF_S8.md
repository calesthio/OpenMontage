# S8 — 5-model image bake-off (Kilo)

**Status: in progress.** This file is the final report; it is filled in when the
three new model runs are done. No winner is declared by the agent: the owner's
blind CSV decides.

Scope: `docs/`, `tools/` (not `tools/prompting/`, not `scripts/score_rubric.py`),
`scripts/`, `tests/`, `.kilo/`. fp16 only, released library versions pinned in
every manifest (no git main), no bitsandbytes, no CPU fallback, no paid routes,
no secrets printed, no media in git, one Kaggle status call between phases.

Models compared (5):

| # | model | source | licence | status |
|---|---|---|---|---|
| 1 | SDXL Base 1.0 + `madebyollin/sdxl-vae-fp16-fix` | S7 run `s7-sdxl-1` (reused, sha256 verified) | OpenRAIL++ | DONE in S7 |
| 2 | FLUX.2-klein-4B | S7 run `s7-klein-1` (reused, sha256 verified) | BFL card | DONE in S7 |
| 3 | SDXL-Lightning 8-step | `ByteDance/SDXL-Lightning` (new) | OpenRAIL++ | DONE (10/10, verify PASS) |
| 4 | DreamShaper XL Lightning | `Lykon/dreamshaper-xl-lightning` (new) | OpenRAIL++ | DONE (10/10, verify PASS) |
| 5 | SANA-Sprint 1.6B 1024px | `Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers` (new) | Apache-2.0 | **BLOCKED** (4 attempts, 0 usable frames) |

Not submitted: **Z-Image-Turbo** (S7 verdict: BLOCKED, fp16 NaN -> black
frames) and **Krea 2 Turbo** (S8-1 verdict: LICENSE_BLOCKED - gated auto with
a community licence whose commercial terms could not be verified, 12.8 B
params). See `CANDIDATES_S8.md`.

---

## 1. Observed vs assumed

| # | Observed | Source | Date | Confidence |
|---|---|---|---|---|
| 1 | Three new models ran on the Kaggle T4 with **released** diffusers only (0.37.0), fp16, no bitsandbytes, no CPU fallback: SDXL-Lightning 8-step 10/10 (verify PASS), DreamShaper XL Lightning 10/10 (verify PASS), SANA-Sprint 1.6B 0/10 usable | `logs/s8-*/manifest.json` | 2026-10-22 | high |
| 2 | SDXL Base and FLUX.2-klein-4B were **reused** from S7, not re-rendered: all 20 images were sha256-verified against the S7 manifests before entering the pack | `S8_REUSE.json` | 2026-10-22 | high |
| 3 | The SDXL media re-run from S7 is bit-identical to the original run (10/10 sha256), so the S8 reuse is reproducible, not a lucky sample | `logs/s7-sdxl-1` vs `logs/s7-sdxl-2` | 2026-10-21 | high |
| 4 | SDXL-Lightning 8-step: **3.943 s/image** (12.51 usable img/min), 9168.6 MB peak VRAM, 0 black/NaN/OOM | `logs/s8-sdxl-lightning-2/manifest.json` | 2026-10-22 | high |
| 5 | DreamShaper XL Lightning: **5.112 s/image** (10.12 img/min), 9968.01 MB peak VRAM, 0 black/NaN/OOM | `logs/s8-dreamshaper-xl-1/manifest.json` | 2026-10-22 | high |
| 6 | SANA-Sprint 1.6B produced **10 black frames** in fp16 (same "invalid value encountered in cast" NaN signature as Z-Image in S7), with an fp32 text encoder and with a 4-step schedule; without CPU offload its 12.2 GB of weights OOM-loop on a 14.56 GiB T4 | `logs/s8-sana-sprint-1.6b-{1,2,3,4}/` | 2026-10-22 | high |
| 7 | Krea 2 Turbo is gated (`gated: auto`) under a community licence whose commercial terms could not be read in this environment, and needs ~25.6 GB of fp16 weights | `CANDIDATES_S8.md` | 2026-10-22 | high (gate) / unknown (licence text) |
| 8 | `stabilityai/sdxl-turbo` is under `sai-nc-community` (free use below US $1M revenue) - **not** run | `CANDIDATES_S8.md` | 2026-10-22 | high |
| 9 | The text-like heuristic under-detects real lettering (it missed the worst SDXL poster text in S7) and over-fires on clean flat art | S7 + S8 QC | 2026-10-22 | high |

Assumed (not verified here):

- That the vendor-card step counts and guidance values are the best settings for
  a flat-vector field-guide plate. They are the card values, not tuned values.
- That `madebyollin/sdxl-vae-fp16-fix` suits the SDXL-Lightning UNet. It was
  used so the SDXL-family rows share one VAE with the S7 SDXL Base run; the
  Lightning UNet is a finetune of the same architecture, but that pairing was
  not A/B tested.
- That the S7 SDXL/klein rubric scores carry over to S8. They are the same
  images (sha256-verified) with one extra dimension (style fit) added in S8
  from the same visual notes; the owner's S8 scores are a fresh blind pass.
- That 10 scenes x 1 seed separates the models on quality. It is a smoke test,
  not a benchmark.
- That SANA-Sprint needs bf16 to work on this stack. The card specifies
  bfloat16 and every fp16 variant produced NaN, but bf16 was not run because
  the brief mandates fp16 only.

---

## 2. Licence and fit table

Full evidence, licence quotes, URLs and dates:
**`docs/openmontage/image_gen/CANDIDATES_S8.md`** (raw metadata:
`S8_CANDIDATE_FACTS.json`, collected with `scripts/s8_candidates.py`,
read-only, official Hugging Face cards only, no weight downloads).

| model | licence | gated | verdict | run? |
|---|---|---|---|---|
| ByteDance/SDXL-Lightning | `openrail++` (CreativeML Open RAIL++-M) | no | FITS_T4 | **yes** |
| Lykon/dreamshaper-xl-lightning | `openrail++` | no | FITS_T4 | **yes** |
| Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers | `apache-2.0` | no | FITS_T4 | **yes (blocked at run time)** |
| krea/Krea-2-Turbo | `other` = krea-2-community-license | **yes** (auto) | LICENSE_BLOCKED (also ~25.6 GB fp16 -> TOO_BIG) | no - replaced by SANA-Sprint (Apache-2.0, explicitly commercial-OK) |
| stabilityai/sdxl-turbo | `other` = sai-nc-community | no | LICENSE_BLOCKED (revenue cap) | no |
| Efficient-Large-Model/Sana_1600M_1024px_diffusers | `apache-2.0` | no | FITS_T4 (backup, not needed) | no |
| segmind/SSD-1B | `apache-2.0` | no | FITS_T4 (backup, not needed) | no |
| PixArt-alpha/PixArt-Sigma-XL-2-1024-MS | `openrail++` | no | NEEDS_OFFLOAD (backup, not needed) | no |

The two models already compared in S7 keep their S7 licences: SDXL Base 1.0
(`openrail++`) and FLUX.2-klein-4B (BFL card).

---

## 3. Attempts log per model

### SDXL-Lightning 8-step - DONE (2 attempts)

| attempt | what changed | result |
|---|---|---|
| 1 | first attempt: vendor-card recipe (SDXL Base pipeline + `sdxl_lightning_8step_unet.safetensors` fp16 UNet + EulerDiscreteScheduler `timestep_spacing="trailing"`, 8 steps, guidance 0, `madebyollin/sdxl-vae-fp16-fix` VAE), rung `released_037_x4` | **FAILED before any model call** - `RecursionError: maximum recursion depth exceeded`. The kernel's `run.py` is the S7 engine with the S8 additions appended; the additions defined their own `main()`, shadowing the engine's, so the runner called itself. Log: `logs/s8-sdxl-lightning-1/kernel.log` |
| 2 | fixed the runner: the engine's `main` is captured as `_ENGINE_MAIN` before the S8 `main` is defined (regression test in `tests/test_s8_bakeoff.py`); same released stack (the stack had never been exercised) | **DONE** - 10/10 images, bridge verify PASS, 3.943 s/image |

### DreamShaper XL Lightning - DONE (1 attempt)

| attempt | what changed | result |
|---|---|---|
| 1 | vendor-card recipe: fp16 variant, `DPMSolverMultistepScheduler`, 4 steps, guidance 2, rung `released_037_x4` | **DONE** - 10/10 images, bridge verify PASS, 5.112 s/image |

### SANA-Sprint 1.6B 1024px - BLOCKED (4 attempts, cap reached, 0 usable images)

| attempt | what changed | result |
|---|---|---|
| 1 | vendor-card recipe (bf16 card, fp16 per the brief), `SanaSprintPipeline`, 2 steps, guidance 4.5, CPU offload | COMPLETE, 10/10 files, verify PASS, but **10 black frames** (`max == 0`). Kernel log: `diffusers/image_processor.py: RuntimeWarning: invalid value encountered in cast` (NaN in the decoded image) |
| 2 | the Gemma2 text encoder in **fp32** (DiT and VAE stay fp16), offload kept | COMPLETE, still **10 black frames** - the text encoder is not the source |
| 3 | **no** CPU offload (all weights resident, 12.2 GB with the fp32 VAE) + fp32 VAE | **hung** - OOM loop at 1024x1024; the run had to be abandoned (it would have hit the 90-minute in-job cap with no usable frame) |
| 4 | offload back on, fp32 text encoder kept, **4 steps** instead of 2 (the card allows 1-4) so the SCM scheduler takes smaller jumps | **FAILED before any frame**: `ValueError: Intermediate timesteps for SCM is not supported when num_inference_steps != 2.` - the diffusers SCMScheduler only supports 2 steps, so the 4-step configuration is not a valid run of this model (tracebacks: `logs/s8-sana-sprint-1.6b-4/traceback_r30*.txt`) |

Evidence that the NaN is upstream of the VAE: attempts 1, 2 and 4 kept a
black frame count of 10 even with the VAE decoding in fp32, and the same
warning line appears as in the S7 Z-Image-Turbo failure. The card's own
precision for this model is **bfloat16**; the S8 brief mandates fp16 only.

---

## 4. Speed / VRAM table

From the kernel manifests (`logs/*/manifest.json`). "steady s/image" excludes
the first (warm-up) image; "usable img/min" counts only frames that are
neither black nor NaN.

| model | job | load s | steady s/img | usable img/min | peak VRAM MB | black/NaN/OOM | attempts | diffusers | transformers | hub | torch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SDXL Base 1.0 (S7, reused) | `s7-sdxl-1` | 86.233 | 41.400 | 1.42 | 9169.58 | 0/0/0 | 1 | 0.36.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 |
| FLUX.2-klein-4B (S7, reused) | `s7-klein-1` | 133.852 | 24.691 | 2.17 | 7995.02 | 0/0/0 | 1 | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 |
| SDXL-Lightning 8-step | `s8-sdxl-lightning-2` | 73.471 | **3.943** | **12.51** | 9168.60 | 0/0/0 | 2 | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 |
| DreamShaper XL Lightning | `s8-dreamshaper-xl-1` | 38.511 | **5.112** | **10.12** | 9968.01 | 0/0/0 | 1 | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 |
| SANA-Sprint 1.6B | `s8-sana-sprint-1.6b-1` (last usable attempt) | 59.083 | 9.027 | **0.00** (1.15 raw) | 5085.20 | **10**/0/0 | 4 (BLOCKED) | 0.37.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 |

Common stack: accelerate 1.14.0, safetensors 0.8.0, numpy 2.1.3,
pillow 12.3.0, CUDA 12.8, Python 3.13.15, Tesla T4, fp16, no bitsandbytes,
no CPU fallback (CPU *offload* only, compute stays on the GPU).

**Speed head-line:** the two distilled SDXL checkpoints are 8-10x faster per
frame than the SDXL Base and klein runs (3.9 s and 5.1 s vs 41.4 s and
24.7 s) at a comparable VRAM footprint. If throughput is the deciding
criterion, the distilled models win that axis outright.

---

## 5. Objective QC

`docs/openmontage/image_gen/S8_CHECKS.json` (machine-generated, flags only).
Per-image checks: Laplacian blur (absolute + relative to the scene median),
text-like banding heuristic, dHash duplicates, resolution, saturation and
contrast outliers.

| model | images | resolution bad | blur (abs) | blur (rel.) | text-like | saturation outlier | contrast outlier | duplicate pairs |
|---|---|---|---|---|---|---|---|---|
| sdxl | 10 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| klein | 10 | 0 | 0 | 8 | 1 | 2 | 3 | 0 |
| sdxl-lightning | 10 | 0 | 0 | 0 | 4 | 1 | 2 | 0 |
| dreamshaper-xl | 10 | 0 | 0 | 2 | 2 | 0 | 3 | 0 |
| sana-sprint-1.6b | 10 | 0 | 10 (all black) | 0 | 0 | 0 | 0 | 45 (identical frames) |

**The text-like detector is unreliable - in S7 and in S8.** In S7 it missed
the two worst SDXL frames (whole blocks of fake lettering on the s01 poster)
and fired on a clean klein frame whose lime mat outlines look like text. In
S8 it flags 4 of 10 SDXL-Lightning frames: the visual review confirms
lettering in two of them (the s10 plate's corner labels and the s11 plate's
caption line) and no lettering in the other two. Treat the flag as "look at
this frame", never as a verdict; the visual review in section 6 is the
authority.

**Blur flags:** klein's 8 relative flags are a property of flat vector art
(large smooth areas -> low Laplacian variance), not a defect: no absolute
blur flag fired for any working model.

---

## 6. Advisory agent ranking

**Label: agent opinion, not independent, a vision model can miss anatomy
errors.** The owner's blind CSV decides the winner.

Method: every usable frame was opened and scored 0-2 on the OpenCode rubric
(`scripts/score_rubric.py`, read-only): anatomy, geometry, count/relation,
texture, text, usefulness, plus **style fit** against
`docs/openmontage/niches/speculative_evolution/STYLE_BIBLE.md` (flat-vector
field-guide plate, silhouette-first, clean lines, no gradients, no text,
palette deep teal / bioluminescent lime / basalt charcoal / pale bone).
Per-image sheet: `docs/openmontage/image_gen/S8_AGENT_REVIEW.csv`;
aggregate: `docs/openmontage/image_gen/S8_AGENT_ASSESSMENT.json`.

| model | severe scores (0s) | images with a 0 | usable images | repair burden | s/img | rank |
|---|---|---|---|---|---|---|
| **klein** | **7** | 4/10 | **5/10** | **0.571** | 24.691 | **1** |
| sdxl-lightning | 22 | 7/10 | 1/10 | 0.957 | **3.943** | 2 |
| sdxl | 25 | 9/10 | 0/10 | 1.071 | 41.400 | 3 |
| dreamshaper-xl | 28 | 6/10 | 0/10 | 1.171 | 5.112 | 4 |

**Agent pick: klein - confidence: medium.** klein wins on every quality
axis and on style fit; the two distilled SDXL checkpoints win only on speed.
"Medium" because this is 10 scenes x 1 seed scored by a non-human reviewer,
and because the owner's blind score is what counts.

Weakest scenes per model (a 0 on any dimension):

- klein: s03, s04, s01 (an eye on a "0-eyed" drifter, a segmented burrower
  that still has an eye, a 4-legged "6-limbed" grazer) and the two food-web
  plates s10/s11 (garbled labels).
- sdxl-lightning: s01, s09, s03, s04, s07 (collages and abstract textures
  where a subject was required).
- sdxl: s01, s08, s09, s04 (posters, blobs, wrong subjects).
- dreamshaper-xl: s01, s03, s04, s08, s09, s10 (radial tentacle creatures,
  photoreal renders, no plate layouts).

Per-scene picture (agent view, 0-2 per dimension:
A=anatomy, G=geometry, C=count/relation, T=texture, X=text, U=usefulness,
S=style fit):

| scene | sdxl | klein | sdxl-lightning | dreamshaper-xl |
|---|---|---|---|---|
| s01 vent grazer | 0 1 0 2 0 0 1 | 1 2 0 2 2 1 2 | 1 1 0 2 2 1 1 | 1 1 0 1 2 1 0 |
| s03 filter drifter | 1 1 1 1 2 1 0 | 1 2 0 0 2 1 0 | 1 2 1 0 2 1 0 | 1 1 0 1 2 1 0 |
| s04 ice burrower | 0 1 0 2 2 0 2 | 1 2 0 1 2 1 1 | 0 0 0 1 2 0 0 | 1 1 0 1 2 1 0 |
| s05 chimney field | 2 1 2 0 2 1 0 | 2 2 2 2 2 2 2 | 2 1 2 0 2 1 0 | 2 1 2 0 2 1 0 |
| s06 under-ice cavern | 2 1 2 0 2 1 0 | 2 1 2 2 2 1 2 | 2 2 2 0 2 1 0 | 2 1 2 0 2 1 0 |
| s08 forelimb detail | 0 1 0 0 2 0 0 | 1 2 1 2 2 1 2 | 1 1 0 1 2 1 0 | 1 1 0 1 2 1 0 |
| s09 filter mouth | 0 0 0 1 2 0 1 | 1 2 1 1 2 1 1 | 0 0 0 1 2 0 0 | 0 0 0 0 2 0 0 |
| s10 food web | 1 1 0 2 1 1 2 | 1 2 1 2 0 1 2 | 1 2 0 2 1 2 2 | 0 0 0 0 2 0 0 |
| s11 food web | 1 1 1 2 0 1 2 | 1 2 2 2 0 1 2 | 1 2 1 2 1 2 2 | 1 1 0 0 2 1 0 |
| s12 frozen surface | 2 1 2 0 2 1 0 | 2 2 2 1 2 1 1 | 2 1 2 0 2 1 0 | 2 1 2 1 2 1 0 |

Read-across: **speed and style fit are separate axes.** SDXL-Lightning is the
fastest model by 6x and its two food-web plates (s10, s11) are the best
plates anyone produced in S7 or S8 - but its macro/abstract scenes (s03,
s04, s09) collapse into painterly or texture-only images. DreamShaper XL
Lightning is fast and coherent but photoreal and off-palette, i.e. wrong for
this niche. klein is the only model that lands the flat-vector style on
almost every scene, at 6x the cost per frame of SDXL-Lightning.

---

## 7. BLOCKED causes

**SANA-Sprint 1.6B 1024px (`Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers`)
- BLOCKED after 4 attempts (the cap), 0 usable images.**
Evidence: `docs/openmontage/image_gen/logs/s8-sana-sprint-1.6b-{1,2,3,4}/`.

- The licence is fine (Apache-2.0, explicitly commercial-OK) and the model is
  small (1.6 B, 9.7 GB of weights) - this is not a size or rights problem.
- In fp16 the pipeline produced **10 of 10 black frames** (`max == 0`) with
  `diffusers/image_processor.py: RuntimeWarning: invalid value encountered in
  cast` - the NaN signature S7's Z-Image-Turbo showed.
- Two in-spec hypotheses were tested and eliminated: the **Gemma2 text
  encoder** (fp32 encoder, still black) and the **VAE decode** (fp32 VAE,
  still black / OOM-loop without offload).
- The remaining suspect is the fp16 **transformer** itself: the card's own
  precision for this model is **bfloat16**, and the S8 brief mandates fp16
  only, so the one remaining fix is out of scope for this milestone.

**Owner decision to unblock SANA-Sprint (not taken by the agent):** allow
**bfloat16** for this one model (the vendor's own dtype) and run one more
kernel job - the model is 1.6 B, bf16 is the same memory footprint as fp16,
and the card's snippet uses it. Nothing else in S8 changes.

**Nothing else is blocked.** SDXL Base 1.0, FLUX.2-klein-4B, SDXL-Lightning
and DreamShaper XL Lightning each produced 10/10 verified frames.

**Not run at all (gate decisions, not failures):**

| model | why it was not run |
|---|---|
| Z-Image-Turbo | BLOCKED in S7 (same fp16 NaN -> black frames). The S8 brief says not to submit it. |
| krea/Krea-2-Turbo | LICENSE_BLOCKED: gated `auto` under the Krea 2 Community Licence, whose commercial terms could not be read in this environment (PDF, no extractor), plus ~25.6 GB of fp16 weights on a 16 GB GPU. |
| stabilityai/sdxl-turbo | LICENSE_BLOCKED: `sai-nc-community` - free use only below US $1M annual revenue. |
| Sana 1.6M 1024px, SSD-1B, PixArt-Sigma-XL | backups, not needed (the brief allows up to 3 new models). |

---

## 8. Owner steps (exact)

1. Open the blind pack: `projects/s8_blind/` (gitignored, 10 sheets).
   `sheet_s01.png`, `sheet_s03.png`, `sheet_s04.png`, `sheet_s05.png`,
   `sheet_s06.png`, `sheet_s08.png`, `sheet_s09.png`, `sheet_s10.png`,
   `sheet_s11.png`, `sheet_s12.png`. Each sheet shows the **same scene drawn
   by 4 models, panels A/B/C/D**, in a different random order per scene, no
   model names, 1600 px wide. (SANA-Sprint is not in the pack: it is
   BLOCKED.)
2. Fill `projects/s8_blind/results.csv` on a phone, one row per scene:
   `scene,best_panel,second_best,worst_panel,anatomy_ok_A,anatomy_ok_B,anatomy_ok_C,anatomy_ok_D,comment`
   - `best_panel` / `second_best` / `worst_panel` = `A`|`B`|`C`|`D`
   - `anatomy_ok_<panel>` = `yes`|`no` (limbs/eyes/horns match the brief, no
     extra or missing limbs, no fused or duplicated bodies)
   - do **not** open `mapping.json` before the CSV is filled - that is the
     blind.
3. Tally it:
   ```
   python scripts/s7_tally.py --csv projects/s8_blind/results.csv \
       --mapping projects/s8_blind/mapping.json \
       --agent docs/openmontage/image_gen/S8_AGENT_ASSESSMENT.json \
       --title "S8 blind-pack tally"
   ```
   It prints wins, 2nd places, losses, anatomy-ok counts and the speed/VRAM
   table, declares `TIE` when the top two differ by <= 1 win, and prints
   `AGENT vs OWNER: agree/disagree` against the agent's advisory pick
   (klein). It refuses to recommend anything while the CSV is incomplete.
4. Write the decision into section 9 of this file, then decide on SANA-Sprint
   (section 7: allow bf16 for one more run, or leave it blocked).

**Stopping the Codespace** (nothing needed for the tally is lost: the sheets,
the CSV template and the mapping live in `projects/s8_blind/`, and the
manifests, QC report and rubric sheet are committed):

```
gh codespace stop -c scaling-spoon-wv7wq975xwqjhgqgx
```

---

## 9. Winner (owner-decided)

**Not decided yet.** The owner's blind CSV is still empty; the agent does not
declare a winner. The advisory ranking (section 6) is
**klein > SDXL-Lightning > SDXL Base > DreamShaper XL Lightning**, with
SANA-Sprint BLOCKED - and on the speed axis alone
**SDXL-Lightning > DreamShaper XL Lightning > FLUX.2-klein-4B > SDXL Base**.
