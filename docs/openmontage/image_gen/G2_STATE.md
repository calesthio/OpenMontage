# G2 State — AI Image Generation Bake-off (Kilo) — FINAL (concluded FAILED)

**Kernel slug:** forts845/g2-image-bakeoff  
**Job id:** g2-bakeoff-1  
**Submit time:** 2026-10-20T08:45:00Z (v1), re-push v2 ~2026-10-20T16:15Z  
**Final status:** ERROR (both versions). NO images produced, 0.0 GPU min. G2 bake-off concluded FAILED — ONE fix + ONE re-push already used; no further re-push allowed per G-rules.  
**Resume:** N/A (G2 concluded). Owner judges visually from logs; G2_REPORT.md not written (kernel never produced outputs).

## Root causes (from g2-image-bakeoff.log, /workspaces/OpenMontage/projects/image_gen/g2_v2/)
- **v1:** every model failed at fp16 load attempt 0; error swallowed; bitsandbytes 8-bit fallback NOT installed on Kaggle image → pipe=None for all 3 models → 0 images.
- **v2:** load_pipe fixed (logs attempt-0 errors, skips missing bitsandbytes, CPU float32 fallback). Models loaded via cpu_float32 fallback (peak VRAM 0.0 MB) but generation raised `TypeError: 'dict' object is not callable` for every seed on Model A (SDXL-Lightning) and Model B (Z-Image-Turbo). Model C (FLUX.2-klein-4B): fp16 variant files unavailable → fell to CPU float32 → OOM `Killed` during pipeline load (~340s, T4 16GB). Result: 0 images across all 3 models, 30 prompts total.
- **Conclusion:** Kaggle T4 CPU float32 fallback is too slow/broken for these diffusion pipelines (dict-not-callable generation bug on CPU; FLUX OOM). G2 bake-off FAILED under the zero-cost/no-paid-route constraint. If owner wants image bake-off, use a GPU-enabled Kaggle job with bitsandbytes installed, or run locally with a GPU.

## License pre-check (unchanged, informational only)
- SDXL-Lightning + SDXL base: OpenRAIL++ — commercial OK.
- Z-Image-Turbo: apache-2.0 — commercial OK.
- FLUX.2-klein-4B: apache-2.0 — commercial OK.

## M_STATE handoff
G2 concluded FAILED (recorded in docs/openmontage/M_STATE.md). M2 AI illustration module proceeds independently via scripts/iss_narrate_all.py-style Kaggle bridge batch generation (new module, not the G2 kernel).
