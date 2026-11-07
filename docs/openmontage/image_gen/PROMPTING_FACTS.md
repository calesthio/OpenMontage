# Prompting Facts — Speculative Evolution Model Bakeoff (S4-1)

**Purpose:** Verify every prompting claim against official model cards/docs before the
bakeoff runs. Label: **vendor-official** = the model maker's own docs/card;
**blog/community** = third-party hint, not a specification; **UNVERIFIED** = not yet
confirmed by an official source. No facts from memory. Access date: 2026-10-21.

## Per-model fact table

| Model | Official steps | Official guidance | Negative prompt supported? | Prompt length limit | Word-order advice | Source (URL) | Access date | Label |
|---|---|---|---|---|---|---|---|---|
| Z-Image-Turbo | 8 NFE (vendor card); diffusers default 50, example uses 8/9 | guidance_scale 0.0 for Turbo (vendor); diffusers default 5.0 | **Yes at pipeline level, IGNORED when guidance_scale < 1** (diffusers: "Ignored when not using guidance") | max_sequence_length default 512 (diffusers); vendor recommends long detailed prompts | HF discussion + blog cheat sheet: natural descriptive language, subject→environment→lighting→style (blog = non-vendor) | https://huggingface.co/Tongyi-MAI/Z-Image-Turbo ; https://huggingface.co/docs/diffusers/main/api/pipelines/z_image ; https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/discussions/8 ; https://zimage.net/docs | 2026-10-21 | vendor-official (card + diffusers) / blog (cheat sheet structure) |
| SDXL Base | default 50 (HF diffusers) | guidance_scale default 5.0; CFG enabled when guidance_scale > 1 | **Yes** — separate `negative_prompt` (+ `negative_prompt_2`); ignored when guidance_scale < 1 | not stated by vendor | structured keyword phrases + separate negative; natural language detail works well | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 ; https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/stable_diffusion_xl | 2026-10-21 | vendor-official (card + diffusers) |
| FLUX.2-klein-4B (local diffusers FluxPipeline) | default 28 (diffusers FluxPipeline); 4 steps = project config, NOT vendor-mandated | guidance_scale default 3.5, enabled when > 1 | **Yes, but only when true_cfg_scale > 1** — "Ignored when not using guidance (i.e., ignored if true_cfg_scale is not greater than 1)"; `true_cfg_scale > 1 AND negative_prompt provided` enables true CFG | max_sequence_length default 512 (diffusers) | subject first, then setting/light/framing; structure matters more than length; omit quality tags | https://huggingface.co/docs/diffusers/main/api/pipelines/flux (local pipeline) ; https://docs.bfl.ai/guides/prompting_unified_building ; https://huggingface.co/black-forest-labs/FLUX.2-klein-4B | 2026-10-21 | vendor-official (diffusers FluxPipeline + BFL card) |

## Key distinction: BFL API service vs local diffusers pipeline (klein)

- **BFL API service** (docs.bfl.ai): FLUX has NO `negative_prompt`, NO `guidance`, NO `seed` field. Template `[Subject], [location], [style], [camera settings], [lighting], [colors], [effect], [additional elements]`; medium and style first. → This applies to the cloud API, NOT the local pipeline.
- **Local diffusers FluxPipeline** (diffusers docs): accepts `negative_prompt`, `negative_prompt_2`, `true_cfg_scale` (default 1.0), `guidance_scale` (default 3.5). negative_prompt is honoured only when true_cfg_scale > 1; guidance_scale enabled when > 1. → This is what S4-2 will run locally on Kaggle.

## Confirmed vs assumed (S4-1 verdict)

| Claim | Source | Status |
|---|---|---|
| Z-Image-Turbo: 8 NFE, sub-second, fits 16G VRAM | vendor card | CONFIRMED |
| Z-Image-Turbo: guidance should be 0 for Turbo | vendor card + HF discussion | CONFIRMED |
| Z-Image-Turbo: does not use negative prompts at all | vendor HF discussion | CONFIRMED (vendor guidance) |
| Z-Image pipeline accepts negative_prompt arg | diffusers docs | CONFIRMED (but ignored when guidance_scale < 1) |
| SDXL: negative_prompt + guidance_scale + num_inference_steps | HF diffusers docs | CONFIRMED |
| SDXL: guidance default 5.0 | HF diffusers docs | CONFIRMED |
| klein (local diffusers): guidance_scale honoured (>1 enables) | diffusers FluxPipeline docs | CONFIRMED |
| klein (local diffusers): negative_prompt honoured only when true_cfg_scale > 1 | diffusers FluxPipeline docs | CONFIRMED |
| klein: 4 steps recommended | NONE — BFL docs do not prescribe step count for klein | UNVERIFIED / project config |
| klein (BFL API): no negative_prompt/guidance/seed | docs.bfl.ai | CONFIRMED for the API service only (not local pipeline) |

## OpenCode change request

No change to tools/prompting/ needed: builder.py already encodes
- sdxl: negative_prompt + guidance 7.5 + 50 steps
- zimage: guidance 0 + 9 steps + no negative_prompt
- klein: 4 steps + no negative_prompt

These match the verified facts above. The small discrepancy (builder hardcodes klein 4 steps / no guidance; diffusers FluxPipeline default guidance 3.5) is a project configuration choice, not an error — record it in S4-5 as observed vs assumed.

## Files not touched

tools/prompting/ and scripts/score_rubric.py are owned by OpenCode — read only, not edited here.
