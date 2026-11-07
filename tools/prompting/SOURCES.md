# Prompt builder source notes — tools/prompting/SOURCES.md

All source URLs below were retrieved live (webfetch) on 2026-10-21.
Each claim is labeled **vendor-official** (the model maker's own docs) or
**blog/community** (third-party; treat as a hint, not a specification).
No facts from memory.

## Targets

- **sdxl** = Stable Diffusion XL (stabilityai/stable-diffusion-xl-base-1.0).
- **zimage** = Tongyi-MAI Z-Image / Z-Image-Turbo.
- **klein** = FLUX.2-klein-4B family (Black Forest Labs FLUX).

## Sources

### SDXL (Stable Diffusion XL)

| URL | Label | What it supports |
|-----|-------|------------------|
| https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/stable_diffusion_xl | vendor-official (HF diffusers, the reference SDXL pipeline) | SDXL exposes `prompt`, `negative_prompt`, `guidance_scale` (default 5.0), `num_inference_steps` (default 50), two text-encoders (`prompt`/`prompt_2`), `negative_prompt_2`. CFG is enabled when `guidance_scale > 1`; `negative_prompt` is ignored when `guidance_scale < 1`. |
| https://stable-diffusion-art.com/sdxl-prompts/ | blog/community | "Easy on negative prompts" — SDXL needs fewer/lighter negatives than SD 1.5; only include things to avoid. Describing in detail in natural language works well. |

SDXL design decision in this builder: structured keyword phrases + a SEPARATE
negative prompt ("extra limbs, fused legs, duplicate subject, text, watermark,
photorealism"), guidance 7.5, 50 steps. The negative-prompt contents are a
project choice (anatomy failure modes), not a vendor claim; SDXL's
`negative_prompt` parameter and `guidance_scale`/`num_inference_steps` are
vendor-official (HF diffusers).

### Z-Image (Z-Image-Turbo)

| URL | Label | What it supports |
|-----|-------|------------------|
| https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/discussions/8 | vendor-official (Tongyi-MAI org on HF) | "About negative prompt: … this is a few-step distilled model that does not rely on classifier-free guidance during inference. … does not use negative prompts at all." Sample code uses `guidance_scale=0.0`, `num_inference_steps=9`, `max_sequence_length=1024`. Recommends long, detailed prompts; prompt enhancing via LLM. |
| https://zimage.net/docs | vendor-official (Z-Image project docs) | Z-Image-Turbo: 8 NFEs, sub-second latency, guidance should be 0 for Turbo models. |
| https://huggingface.co/docs/diffusers/main/api/pipelines/z_image | vendor-official (HF diffusers ZImage pipeline) | `ZImagePipeline` accepts `prompt`, `guidance_scale` (default 5.0), `negative_prompt`, `num_inference_steps` (default 50), `max_sequence_length` (default 512). Confirms a `negative_prompt` argument exists at the pipeline level even though Turbo guidance is 0. |
| https://github.com/TheAIHorizon/SanctumWriter/blob/main/Z-Image%20Prompting%20Cheat%20Sheet%20(Markdown).md | blog/community | Z-Image responds best to natural, descriptive language (not keyword soup); 4-part structure subject→environment→lighting→style; keep negative prompt empty/minimal on Turbo. |

Z-Image design decision in this builder: descriptive prose, style FIRST,
3–5 key visual concepts, constraints phrased positively, NO negative prompt,
guidance 0, 9 steps. The "guidance 0 / 9 steps / no negative prompt" values
are vendor-official (Tongyi-MAI HF discussion + zimage.net docs). The
prose-first structure is informed by the blog cheat sheet (non-vendor).

### klein (FLUX.2-klein-4B, Black Forest Labs FLUX family)

| URL | Label | What it supports |
|-----|-------|------------------|
| https://docs.bfl.ai/guides/prompting_unified_building | vendor-official (Black Forest Labs) | "Building a Good Prompt": structure subject → action/state → mood/context/visual direction; components image type, subject, location, style, camera settings, lighting, colors, effect, additional elements. Start with a clear subject; specific detail helps, filler hurts. |
| https://docs.bfl.ai/guides/prompting_summary | vendor-official (Black Forest Labs) | FLUX Prompting Guide covers the entire FLUX family (FLUX.1, FLUX.1 Kontext, FLUX.2). |
| https://docs.bfl.ml/guides/prompting_unified_basics | vendor-official (Black Forest Labs) | Prompting Basics: FLUX 3 Image has NO `negative_prompt`, NO `guidance`, NO `seed` field; template `[Subject], [location], [style], [camera settings], [lighting], [colors], [effect], [additional elements]`; medium and style first, then subjects and placement, then light/color/background. |
| https://docs.bfl.ai/guides/prompting_unified_style | vendor-official (Black Forest Labs) | Style, Aesthetics & Text: illustration styles, lighting, legible typography; aspect ratios; working without negative prompts. |

klein design decision in this builder: narrative prose, subject + anatomy in
the FIRST sentence, constraints phrased positively, NO negative prompt,
4 steps. BFL official sources confirm FLUX works without negative prompts and
recommends subject-first structure. **The 4-step value is a project
configuration choice, not a vendor claim** (BFL docs do not prescribe a step
count for klein). BFL docs also note FLUX has no `seed` field; this builder
still records a `seed` for run reproducibility in the manifest.

## Variant styles (project conventions, not vendor claims)

- A = tags (comma-separated keyword phrases).
- B = prose (full sentences, standard order).
- C = prose with anatomy first (anatomy details moved to the front).

## Negation vs positive switch ("no text" constraint)

- negation  -> "no text, no watermark, no letters, no numerals"
- positive  -> "clean image without text, text-free, no letters, no numerals, no watermark"

This switch is a project convention; neither approach is mandated by a vendor.

## Deny-list (no real people / brands / logos)

The builder refuses subjects or anatomy that mention real people, brands, or
logos (see `_DENY_TERMS` in tools/prompting/builder.py). This is a project
policy rule (aligned with AI_IMAGE_POLICY.md: no real people, no logos), not a
vendor quoting.

## What is NOT claimed

- No vendor guarantees specific anatomy counts (limb/eye/horn) will render
  correctly; anatomy correctness is measured by the S3-3 rubric scorer.
- No step count is mandated for klein by BFL (4 steps = project config).
- Z-Image pipeline technically accepts a `negative_prompt` argument (HF
  diffusers), but the Turbo vendor guidance says do not use one; this builder
  omits it for zimage/klein.
