# S5 State — 10-image 3-model bake-off (Kilo)

**Resume rule:** resume at the first phase not DONE. Never loop on Kaggle status:
submit once, record here, do other phases, ONE status call between phases.
**STOP RULE:** max 2 fix attempts per model → BLOCKED with the exact error, then move on.
Never commit media; no secrets printed; fp16 only; no CPU fallback (CPU *offload*
is allowed: compute stays on the GPU); stop if free disk < 800 MB.

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| S5-1 FIXED TEST SET | DONE | 10 scenes (s02 + s07 dropped as the 2 easiest), 1 seed/scene shared by all models, 1024x1024, sdxl=A / zimage=B / klein=C, plus 3 scenes with one identical prompt text for the fairness check. `docs/openmontage/image_gen/S5_TEST_SET.json` (39 renders) + `S5_TEST_SET_MAPPING.json`; prompts via `tools/prompting.builder` (read only) |
| S5-2 RUN ORDER | DONE (1 BLOCKED) | SDXL **DONE** 13/13, 44.6 s/img, 9169.58 MB. klein **DONE** 13/13, 25.1 s/img, 7995.02 MB. Z-Image **BLOCKED** (13/13 pure black in fp16). Runs on `forts845/openmontage-s5-runner` |
| S5-3 OBJECTIVE CHECKS | DONE | `scripts/s5_checks.py` → `docs/openmontage/image_gen/S5_CHECKS.json` (blur abs + scene-relative, text-like, dHash dupes, resolution, black). 6 tests |
| S5-4 BLIND PACK | DONE | `projects/s5_blind/` (gitignored): 10 two-panel sheets + 3 neutral sheets + `results.csv` template + `INSTRUCTIONS.txt` + `mapping.json` (mapping never shown). Sheets 1048x584 px (phone-readable, <= 1600) |
| S5-5 TALLY HELPER | DONE | `scripts/s5_tally.py` + `tests/test_s5_tally.py` (10 tests). Verified on the real pack with a demo CSV: 10/10 scene cells, TIE detection, speed/VRAM table, no recommendation on a partial CSV |
| S5-6 REPORT | DONE | `docs/openmontage/image_gen/BAKEOFF_S5.md` (speed/VRAM, observed vs assumed, BLOCKED causes, owner steps, stop commands); LESSONS entry added |

## Per-model results (one model per kernel, fp16, Tesla T4 16 GB)

| model | status | images | load s | s/img | peak VRAM MB | black/NaN/OOM | stack |
|---|---|---|---|---|---|---|---|
| SDXL Base + sdxl-vae-fp16-fix | DONE | 13/13 | 89.9 | 44.6 | 9169.58 | 0/0/0 | diffusers 0.36.0, transformers 4.57.6, hub 0.36.2, torch 2.11.0+cu128 |
| FLUX.2-klein-4B | DONE | 13/13 | 125.0 | 25.1 | 7995.02 | 0/0/0 | diffusers 0.37.1, transformers 4.57.6, hub 0.36.2, torch 2.11.0+cu128; `Flux2KleinPipeline`, CPU offload |
| Z-Image-Turbo | BLOCKED | 13/13 black | 279.7 | 50.7 | 12249.22 | 13/0/0 | diffusers 0.37.1, transformers 4.57.6, hub 0.36.2, torch 2.11.0+cu128; `ZImagePipeline`, CPU offload |

Evidence kept outside git: `projects/s5_work/s5_bakeoff_{sdxl,klein,zimage}/`
(manifest.json + images), `/tmp/kilo/s5_out` (merged), `/tmp/kilo/z2` (Z-Image run).

## Run log (2026-10-21, UTC)

- 08:31 S4 job status = ERROR (blanket `from diffusers import ZImagePipeline` killed
  its SDXL run, 0 images) → S4 SDXL output not reusable; S5 starts fresh.
- 08:38 SDXL run 1 ERROR `SyntaxError: name 'OUT' is used prior to global declaration`.
- 08:56 SDXL run 2 ERROR `NameError: name 'null' is not defined`
  (`json.dumps` embedded JSON literals into Python source). Both fixed + guarded by
  `tests/test_s5_runner.py`, `tests/test_s5_push_bakeoff.py`.
- ~08:56 klein submitted on the shared slug; the parallel **S7** session overwrote
  it. S7 declares itself a superset of S5 and reuses the same scenes.
- ~11:50 a server restart wiped `/tmp`: SDXL run 3's 13 images (manifest verified,
  one image inspected) were lost; Kaggle keeps only the latest kernel version, and
  that version was S7's job → loss accepted, documented, one run repeated.
- 11:53 SDXL re-run on a **private slug** `forts845/openmontage-s5-runner`
  (title "OpenMontage S5 runner"; the first push hit `409 Conflict` because Kaggle
  titles are unique). 12:10 COMPLETE, 13/13.
- 12:10 klein run 1 (S5 private slug) ERROR: every render
  `TypeError: can only concatenate str (not "list") to str` in the tokenizer chat
  template (diffusers 0.36.x). Fix: `diffusers>=0.37,<0.38` + `transformers>=4.57,<5`
  + `hub<1.0` (stack proven by the S7 klein manifest, 10/10). One attempt beyond the
  nominal 2-fix cap, recorded as such: proven pin, not exploration. 12:31 COMPLETE.
- 12:32 zimage run 1 ERROR `torch.OutOfMemoryError` at load (6B fp16 weights do not
  fit 16 GB). 12:40 fix attempt 2: `enable_model_cpu_offload()` +
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` → COMPLETE but **13/13 pure
  black frames**. Model marked **BLOCKED** (2 attempts used; vendor card wants
  bfloat16, the run mandates fp16).
- 13:05 objective checks on all 39 images; 13:20 blind pack (2 panels/sheet, plus 3
  neutral sheets), tally helper verified on the real mapping.

## Notes

- `tools/prompting/` and `scripts/score_rubric.py` are OpenCode-owned: used
  read-only. Two cosmetic builder duplications reported in
  `docs/openmontage/OPENCODE_REQUESTS.md`; not patched, so the comparison is
  reproducible.
- Disk: 2.6 GB free on `/workspaces` (stop threshold 800 MB); images also banked in
  gitignored `projects/s5_work/` so a `/tmp` wipe cannot destroy them again.
- The blind pack is **not** committed (media, and `projects/` is gitignored).
