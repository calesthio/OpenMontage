# S5 State — 10-image 3-model bake-off (Kilo)

**Resume rule:** resume at the first phase not DONE. Never loop on Kaggle status:
submit once, record here, do other phases, ONE status call between phases.
STOP RULE: max 2 fix attempts per model → BLOCKED with the exact error, then move on.
Never commit media; no secrets printed; fp16 only; no bitsandbytes; no paid routes;
no CPU fallback; stop if free disk < 800 MB.

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| S5-1 FIXED TEST SET | DONE | 10 scenes (s02 + s07 dropped as the 2 easiest), 1 seed/scene, 1024x1024, sdxl=A / zimage=B / klein=C, 3-scene identical-text neutral check: `docs/openmontage/image_gen/S5_TEST_SET.json` (39 renders), mapping `S5_TEST_SET_MAPPING.json` |
| S5-2 RUN ORDER | IN_PROGRESS | SDXL run A COMPLETE (13/13, 48.07 s/img, 9169.58 MB, T4) but its images were lost when /tmp was wiped by a server restart; now re-running on the private slug `forts845/openmontage-s5-runner`. klein + zimage PENDING. S4 SDXL job was NOT reusable: `ERROR` with 0 images (blanket `from diffusers import ZImagePipeline` in the S4 runner crashed the SDXL run) |
| S5-3 OBJECTIVE CHECKS | PENDING | scripts/s5_checks.py (laplacian blur, text-like artifact, phash dupes, resolution) |
| S5-4 BLIND PACK | PENDING | projects/s5_blind/ (gitignored) |
| S5-5 TALLY HELPER | PENDING | scripts/s5_tally.py + tests |
| S5-6 REPORT | PENDING | docs/openmontage/image_gen/BAKEOFF_S5.md |

## Run log

- 2026-10-21: S4 `forts845/openmontage-runner` status = ERROR (one status call).
  Fetched log: `ImportError: cannot import name 'ZImagePipeline'` — S4 runner imported
  all four pipelines for every model, so the released-diffusers SDXL run died too.
  S5 runner imports only the class the job needs.
- SDXL/klein use `diffusers>=0.36,<0.37` (released); Z-Image needs a release that
  ships `ZImagePipeline`, so its attempt 2 is `diffusers>=0.37` — both attempts are
  logged in the kernel's `install_log.json`.

## Notes

- `tools/prompting/` and `scripts/score_rubric.py` are OpenCode-owned: used read-only.
  Two cosmetic duplications found in builder output (see
  `docs/openmontage/OPENCODE_REQUESTS.md`) — not patched here.
- Disk: checked before each phase (stop below 800 MB free).

## 2026-10-21 11:52Z — kernel collision with the parallel S7 session (what happened)

- S5's SDXL run A finished COMPLETE (13/13 images, verified manifest + one image
  inspected by eye). Its output lived only in `/tmp/kilo/s5_out`; a server restart
  wiped `/tmp`, so the images are gone. Kaggle retains only the latest kernel
  version for the shared slug, and by then that version held the S7 job.
- The parallel **S7** session uses the same kernel slug
  `forts845/openmontage-runner` and declares itself a superset of S5. Its klein
  job overwrote S5's queued klein job (S5 klein never produced images:
  `NotImplementedError: Cannot copy out of meta tensor` on `pipe.to("cuda")`).
- Actions taken: S5 now pushes to its own kernel
  **`forts845/openmontage-s5-runner`** (title "OpenMontage S5 runner", since
  Kaggle requires a unique title → the first attempt returned `409 Conflict`).
  S5 reuses S7's *finding* (klein = `Flux2KleinPipeline` + CPU offload,
  `low_cpu_mem_usage=False`) but not its artifacts, so both packs stay
  self-contained. Nothing was pushed to the shared slug after 08:56Z.
- Cost of the loss: one SDXL GPU run (~17 min) repeated. Recorded, not hidden.
