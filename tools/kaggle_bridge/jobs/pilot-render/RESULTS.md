# Pilot Render Results — 10 Section Images

**Kernel:** `forts845/om-pilot-render` (version 2), Kaggle T4  
**Completed:** 2026-10-27T06:33:02Z  
**Model:** `stabilityai/stable-diffusion-xl-base-1.0` (SDXL Base 1.0)  
**Method:** SDXL Base 1.0 + fixed text-prompt consistency (no IP-Adapter)  
**Parameters:** 768×768, 25 steps, CFG 7.5, seed 42, fp16, vae_slicing + vae_tiling + model_cpu_offload  
**Peak VRAM:** 5196 MB  
**Model load:** 89.59 s  
**Total GPU time:** ~90 s load + 10 × ~18 s gen ≈ 4.5 min of T4 time

## Important: klein 4B NOT used

The task P.S. requested "klein 4B без ip adapter", but **klein 4B is blocked** on diffusers 0.37.0 (pinned, cannot upgrade per dependency-guard). It fails to load with missing components: `feature_extractor`, `image_encoder`, `text_encoder_2`, `tokenizer_2`. Per `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md`, the locked model is **SDXL Base 1.0**. This is what was used.

## Character consistency method (FINAL)

Per `EPISODE_IMAGE_PIPELINE.md` §10: baseline SDXL Base 1.0 + детальный фиксированный text-prompt в каждом кадре (без IP-Adapter). IP-Adapter Plus/Plus Face tested on Kaggle T4 via official API — **0 usable frames** (embedding dim mismatch 1664 vs 1280). Adapter deferred to post-pilot timebox.

## Results: 10/10 sections rendered

| Section | File | Title | Status | Gen time (s) | Peak VRAM (MB) |
|---------|------|-------|--------|--------------|----------------|
| §1 | `images_sdxl/section_01.png` | Hook and the question | OK | 19.700 | 5196 |
| §2 | `images_sdxl/section_02.png` | The world: an ocean with no shores | OK | 18.188 | 5196 |
| §3 | `images_sdxl/section_03.png` | Energy: no sunlight, two answers | OK | 17.169 | 5196 |
| §4 | `images_sdxl/section_04.png` | Life near the ice: mats and filter-feeders | OK | 17.695 | 5196 |
| §5 | `images_sdxl/section_05.png` | Predators, and the logic of an arms race | OK | 18.347 | 5196 |
| §6 | `images_sdxl/section_06.png` | The deep, the vents, and the animals that stay | OK | 19.198 | 5196 |
| §7 | `images_sdxl/section_07.png` | Chance and law: would this world repeat? | OK | 19.509 | 5196 |
| §8 | `images_sdxl/section_08.png` | What blocks technology without land or fire | OK | 18.750 | 5196 |
| §9 | `images_sdxl/section_09.png` | What is science, and what is a guess | OK | 18.608 | 5196 |
| §10 | `images_sdxl/section_10.png` | Closing and a question for you | OK | 18.787 | 5196 |

**Summary: 10/10 OK, 0 failed.**

## Known risks — character/visual consistency

1. **No automatic consistency verification.** All 10 images use the same style prefix/tail and seed 42, but cross-section visual consistency (creature designs: grazer 6 limbs, drifter limbless ribbon, burrower segmented cylinder; color palette: night ink/deep sea teal/pale bone/lime-teal/coral) has NOT been programmatically verified. Visual check by owner required.

2. **Single image per section.** Only one render per section (10 total). No per-section retries or alternatives generated. If a section's image is unusable, it must be re-rendered with a new seed.

3. **klein 4B unavailable.** If owner decides klein 4B is required, diffusers must be upgraded from 0.37.0 to git/dev — this is a blocked owner decision (dependency-guard).

4. **No human character in this pilot.** The script features moons, ice, water, vents, and invented sea creatures (grazer, drifter, burrower), not a human protagonist. The "fixed character description" from EPISODE_IMAGE_PIPELINE.md §10.2 ("young woman with short curly auburn hair…") does not apply to this script's content. Consistency is maintained via fixed style prefix/tail and fixed creature anatomy descriptions instead.

## Local paths

All images: `tools/kaggle_bridge/jobs/pilot-render/images_sdxl/section_01.png` … `section_10.png`  
Full results (with prompts): `tools/kaggle_bridge/jobs/pilot-render/output/pilot-render/results.json`  
Kernel log: `tools/kaggle_bridge/jobs/pilot-render/output/om-pilot-render.log`
