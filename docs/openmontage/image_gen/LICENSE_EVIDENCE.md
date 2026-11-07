# License Evidence — AI Image Generation (Milestone G1)

**Retrieved date:** 2026-10-20  
**Source:** official Hugging Face model cards (read-only fetch; no downloads of model weights in this step).  
**Rule applied:** exclude non-commercial components (e.g. FLUX.1-dev, SDXL-Turbo). A component is included only if its license clearly permits commercial use. "UNKNOWN" marks fields not stated on the card.

## Component license table

| Component | License | Commercial use | Restrictions | Evidence URL | Retrieved |
|---|---|---|---|---|---|
| ByteDance/SDXL-Lightning (4-step UNet distilled checkpoints) | openrail++ (model-card frontmatter) | YES (OpenRAIL++ permits commercial use; use-based restrictions apply) | OpenRAIL++ responsible-AI use-based restrictions; model distilled from stabilityai/stable-diffusion-xl-base-1.0 (both must be compliant); 1-step checkpoint experimental/lower quality | https://huggingface.co/ByteDance/SDXL-Lightning | 2026-10-20 |
| stabilityai/stable-diffusion-xl-base-1.0 (base model SDXL-Lightning requires) | CreativeML Open RAIL++-M (`openrail++`) | YES (royalty-free, perpetual, worldwide; commercial use permitted) | Attachment A use-based restrictions (no harming minors, no disinformation/harm, no PII for harm, no non-consensual nudity, no fully automated adverse decision-making, no protected-class discrimination, no law-enforcement/justice administration, no medical advice, etc.); no trademark/endorsement use; license + restrictions must pass to downstream recipients; Licensor claims no rights in generated output | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md | 2026-10-20 |
| black-forest-labs/FLUX.1-schnell (comparison, optional) | apache-2.0 | YES (card states: "can be used for personal, scientific, and commercial purposes") | Apache-2.0 terms; card out-of-scope use list (unlawful use, harming minors, disinformation for harm, PII for harm, harassment, non-consensual nudity, automated adverse decisions, large-scale disinformation); model files require accepting HF access conditions (gated) | https://huggingface.co/black-forest-labs/FLUX.1-schnell | 2026-10-20 |
| Tongyi-MAI/Z-Image-Turbo (bake-off candidate) | apache-2.0 | YES (card frontmatter `license: apache-2.0`; card states open weights available for commercial use) | Apache-2.0 terms; requires diffusers from source (merged PRs #12703/#12715) for ZImagePipeline; 8 NFE distilled model; text rendering/bilingual capability noted | https://huggingface.co/Tongyi-MAI/Z-Image-Turbo | 2026-10-20 |
| black-forest-labs/FLUX.2-klein-4B (bake-off candidate) | apache-2.0 | YES (card explicitly: "Fully open under Apache 2.0", "Open weights available for commercial use") | Apache-2.0 terms; card out-of-scope use list (unlawful use, harming minors, deceptive/fraudulent/misleading content, PII for harm, harassment, non-consensual intimate imagery, automated adverse/high-risk decisions); requires diffusers from source for Flux2KleinPipeline; ~13GB VRAM; C2PA pixel watermarking in inference code | https://huggingface.co/black-forest-labs/FLUX.2-klein-4B | 2026-10-20 |

## Verdict

SDXL-Lightning + its required base (stabilityai/stable-diffusion-xl-base-1.0) are both clearly commercial-OK (OpenRAIL++ / Open RAIL++-M). FLUX.1-schnell is apache-2.0 and clearly commercial-OK. Z-Image-Turbo (apache-2.0) and FLUX.2-klein-4B (apache-2.0) are both clearly commercial-OK and eligible for the G2 bake-off.

**No component is BLOCKED on license grounds.**

## Notes

- SDXL-Lightning LICENSE file was not directly fetchable (404 at `/raw/main/LICENSE`); the license is taken from the model-card YAML frontmatter (`license: openrail++`). Full OpenRAIL++ text not re-parsed here; commercial-use status recorded from the license family.
- FLUX.1-schnell model files are gated behind an HF access agreement; the license (apache-2.0) and commercial-use statement are read from the public model card.
