# Bake-off S5 — SDXL vs FLUX.2-klein-4B vs Z-Image-Turbo (10 scenes, 1024²)

**Verdict so far: 2 of 3 models usable; the owner's blind review is pending.**
SDXL Base and FLUX.2-klein-4B produced 13/13 images each. Z-Image-Turbo
**BLOCKED** — it ran and returned 13/13 pure black frames under the mandated
fp16. The blind pack has 10 sheets with 2 panels each.

## Fixed test set (S5-1)

10 of the 12 scenes from `PROMPT_TEST_PLAN.md`; the 2 easiest dropped:

| dropped | why |
|---|---|
| `s02` | duplicate of `s01` (same vent-grazer silhouette, same anatomy) |
| `s07` | empty abyssal plate — no creature, no anatomy to judge |

Kept `s01 s03 s04 s05 s06 s08 s09 s10 s11 s12`; **one seed per scene, identical
across models** (`4000 4004 4006 4008 4010 4014 4016 4018 4020 4022`);
1024×1024. One prompt variant per model, per `PROMPTING_FACTS.md`:

| model | variant | style | negative prompt | steps / guidance |
|---|---|---|---|---|
| SDXL Base + `sdxl-vae-fp16-fix` | A | structured phrases | yes, short | 50 / 7.5 |
| Z-Image-Turbo | B | prose, style first | none | 9 / 0.0 |
| FLUX.2-klein-4B | C | prose, anatomy first | none | 4 / default (1.0) |

Fairness check: `s01 s08 s10` also rendered with **one identical prompt text for
all three models** (variant `N`) — 39 renders/model-set in
`S5_TEST_SET.json`, mapping in `S5_TEST_SET_MAPPING.json`. Prompts came from
`tools/prompting.builder` (OpenCode-owned, read only).

## Speed / VRAM (measured, one model per kernel, fp16, Tesla T4 16 GB)

| model | status | images | load s | s/img (steady) | peak VRAM MB | black | NaN | OOM | offload |
|---|---|---|---|---|---|---|---|---|---|
| SDXL Base | **DONE** | 13/13 | 89.9 | **44.6** | 9169.6 | 0 | 0 | 0 | no |
| FLUX.2-klein-4B | **DONE** | 13/13 | 125.0 | **25.1** | 7995.0 | 0 | 0 | 0 | yes |
| Z-Image-Turbo | **BLOCKED** | 13/13 black | 279.7 | 50.7 | 12249.2 | **13** | 0 | 0 | yes |

Pinned stacks actually installed (from each kernel manifest):

| model | diffusers | transformers | hub | torch | pipeline class |
|---|---|---|---|---|---|
| SDXL | 0.36.0 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `StableDiffusionXLPipeline` |
| klein | 0.37.1 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `Flux2KleinPipeline` |
| Z-Image | 0.37.1 | 4.57.6 | 0.36.2 | 2.11.0+cu128 | `ZImagePipeline` |

Cost per 10-image set (steady state, T4): SDXL ≈ 7.4 min, klein ≈ 4.2 min
(plus 2.1 min load), Z-Image ≈ 8.5 min + 4.7 min load (offload).

## Observed vs assumed

| # | Assumed (cards / docs) | Observed |
|---|---|---|
| 1 | klein = `FluxPipeline` | **wrong**: FLUX.2 klein needs `Flux2KleinPipeline`; the FLUX.1 class dies on `pipe.to("cuda")` with `Cannot copy out of meta tensor` |
| 2 | Z-Image runs in fp16 | **false in practice**: fp16 + guidance 0 produced 13/13 pure-black frames (pipeline loads and returns without error) |
| 3 | 4 steps for klein | not vendor-mandated (BFL docs give no step count) — project config, kept for speed parity |
| 4 | SDXL 50 steps is "official" | it is the diffusers default, not a vendor mandate |
| 5 | negative prompt helps all three | only SDXL: Z-Image ignores it at guidance 0, klein ignores it without true-CFG |
| 6 | builder prompt text is clean | cosmetic duplication ("… plate field-guide plate.", doubly stated anatomy) — reported in `OPENCODE_REQUESTS.md`, **not** patched, so the comparison stays reproducible |
| 7 | 1024² on a 16 GB T4 is comfortable | Z-Image 6B fp16 does not fit: load OOMs without `enable_model_cpu_offload()` (compute stayed on GPU) |
| 8 | objective checks are model-neutral | the scene-relative blur flag marks klein 7/13 — flat-vector art is *legitimately* smooth next to photoreal SDXL. **Not** evidence of a bad render |

Style observations (not scored, for the owner's context): SDXL variant A produced
dense field-guide **posters** with pseudo-text labels and no single readable
subject; klein produced clean flat-vector **silhouettes**, but drew the vent
grazer with 4 legs where the brief says 6. Anatomy and beauty remain the owner's
call.

## Objective flags (S5-3 — flags only, no aesthetic judgement)

`docs/openmontage/image_gen/S5_CHECKS.json` (per image + duplicate pairs;
thresholds inside the file):

| model | resolution bad | black | blur (abs) | blur (scene-relative) | text-like | duplicate pairs |
|---|---|---|---|---|---|---|
| SDXL | 0/13 | 0 | 0 | 0 | 3 | 0 |
| klein | 0/13 | 0 | 0 | 7 (style, see #8) | 1 | 0 |
| Z-Image | 0/13 | **13** | 0 | 0 | 0 | 0 |

The text-like detector is a heuristic (edge-dense horizontal bands), not OCR: on
SDXL's poster plates it under-flags (3/13) while the eye sees micro-type on most
of them. Treat it as a lower bound.

## BLOCKED causes (exact)

1. **Z-Image-Turbo — BLOCKED (fp16 only).**
   Attempt 1: `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate
   76.00 MiB … 14.19 GiB allocated` at load (`pipe.to("cuda")`).
   Attempt 2 (fix): `enable_model_cpu_offload()` + `low_cpu_mem_usage=False` →
   generated 13/13 images, **every one a pure-black frame** (`min=max=0`,
   `black_count=13`), no exception. Vendor card specifies **bfloat16**; the S5
   rule is fp16 only, so this is reported BLOCKED rather than silently switching
   precision. Next test for a human: same job with `torch_dtype=bfloat16`
   (or fp16 without offload on a ≥24 GB GPU) — one run, no code change.
   Artifacts: `projects/s5_work/s5_bakeoff_zimage/` (manifest + 13 black PNGs),
   kernel output `/tmp/kilo/z2`.
2. **S5's first klein job** died on `NotImplementedError: Cannot copy out of
   meta tensor` (wrong pipeline class, `pipe.to("cuda")`). Fixed by the vendor
   class + CPU offload; that fix is 1 of klein's 2 allowed attempts.
3. **Not a model failure, but recorded:** S4's SDXL job (0 images) died on a
   blanket `from diffusers import ZImagePipeline`; S5's SDXL run 1 died on a
   `global` ordering bug; run 2 on `NameError: null` (JSON embedded as Python);
   run 3 was complete but its images were lost when `/tmp` was wiped by a server
   restart; the parallel **S7** session then overwrote the shared kernel slug, so
   S5 moved to `forts845/openmontage-s5-runner`. Lessons in
   `docs/agent-improvement/LESSONS.md`.

## Owner instructions (10 minutes, phone-friendly)

1. Open `projects/s5_blind/` (local, gitignored). Ten sheets
   `sheet_s01.png … sheet_s12.png`; each shows the same scene as panels
   **A / B** (two panels: the third model is the blocked one), in a different
   random order per sheet. The fairness check is there too:
   `sheet_s01_neutral.png`, `sheet_s08_neutral.png`, `sheet_s10_neutral.png`
   use **one identical prompt text** for both usable models, so you can see how
   much of the difference is prompt format and how much is the model.
2. Per sheet, fill `results.csv` (template present):
   `best_panel`, `worst_panel`, `anatomy_ok_A/B/C` (yes/no), optional `comment`.
   Do **not** open `mapping.json` before filling the CSV, or the test stops being
   blind.
3. Run:

   ```bash
   python scripts/s5_tally.py
   ```

   Output: wins / losses / anatomy-ok per model, the speed/VRAM table, `TIE` when
   the top two are within 1 win, and a recommended model taken **only** from your
   CSV. A partial CSV gets `PARTIAL` and no recommendation.
4. Re-run the flags any time: `python scripts/s5_checks.py --root /tmp/kilo/s5_out`
   (raw images are also banked in `projects/s5_work/`).
5. Decide about Z-Image: run the one-line bf16 test above, or drop it from the
   pilot's model list.

## Stop the Codespace

```bash
# inside the Codespace
gh codespace stop -c "$CODESPACE_NAME"

# from any machine with the gh CLI
gh codespace list
gh codespace stop -c <codespace-name>
```

Web: <https://github.com/codespaces> → `…` menu → *Stop codespace*.
Stopping keeps the repo and `projects/s5_blind/`; review the sheets before you
stop if you want them to hand without re-running anything.
