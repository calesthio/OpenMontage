# LORA FEASIBILITY — locked model family on a Kaggle T4 (read-only note, P2)

**Status: NOT TRAINED. Nothing was trained for this milestone.**
**Locked model:** `klein` → `black-forest-labs/FLUX.2-klein-4B`
(`config/image_engine.json`, status `OWNER_GATED`).
**Question:** could a LoRA for this model family be trained on a Kaggle T4
under the project's $0 rule, and what would the adapter's licence be?

## 1. Verdict (short)

| Question | Answer | Source |
|---|---|---|
| Does the family support LoRA training? | **Yes** — train against the **base** checkpoint `FLUX.2-klein-base-4B`, then run the adapter on the distilled `FLUX.2-klein-4B` | BFL blog (below) |
| VRAM a LoRA run needs | **~24 GB** ("A LoRA run on the 4B model lands under 24 GB") | BFL blog |
| Kaggle T4 VRAM | **16 GB** (T4 x1, ~15 GB usable) | Kaggle accelerator spec |
| Fits on a Kaggle T4? | **NO** — 24 GB > 16 GB | derived from the two rows above |
| Time on a 4090 | ~**60 min** for an 1800-step run (visual peak often at step 750-1500) | BFL blog |
| Time on a T4 | **NOT_CHECKED** — no measured run here; the T4 is materially slower than a 4090, but no factor was measured in this repo | - |
| Cost of the documented path | ~**$0.50 per run** on rented GPU (RunPod template in the guide) | BFL blog |
| Licence of the base model | **Apache-2.0** ("FLUX.2-klein-base-4B is Apache 2.0, so you can ship what you train") | BFL blog + model card |
| Licence of existing adapters | per adapter; the examples are **Apache-2.0** | Hub pages |

**Net:** LoRA training for this family is **NOT feasible on a Kaggle T4 as
documented**, and the documented alternative (a rented 24 GB GPU) is a
**paid route**, which the project forbids. The 4B *inference* does fit (the
measured klein run peaked at **7995 MB** VRAM with CPU offload, job
`s7-klein-1`), so the model itself is fine — it is the *training* memory that
does not fit.

## 2. Facts and citations

1. **Model card** — https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
   (accessed 2026-10-22):
   - licence Apache-2.0; "~13GB VRAM", "runs on consumer GPUs like the
     RTX 3090/4070";
   - text-to-image **and** image-to-image multi-reference editing in one model;
   - the card's out-of-scope-use list (law violations, harm to minors,
     deceptive/fraudulent content, PII abuse, harassment, non-consensual
     intimate imagery, fully automated high-risk decisions) applies to the
     model **and its derivatives**;
   - C2PA / pixel watermarking in the inference code; the card mentions
     "Self-Hosted Commercial License Terms" for commercial open-weight users
     (see §4, NOT_CHECKED);
   - the Hub model tree lists **81 adapters** for `FLUX.2-klein-4B`
     (accessed 2026-10-22).
2. **BFL / Hugging Face community article** — "Fine-tune FLUX.2 [klein] with a
   LoRA under 60 minutes", https://huggingface.co/blog/black-forest-labs/flux-2-klein-lora
   (published 2026-06-04, accessed 2026-10-22):
   - "A LoRA run on the 4B model fits in 24 GB of VRAM, takes about an hour
     on an RTX 4090, and costs roughly $0.50 if you rent the GPU.";
   - train against the **base** checkpoint (`FLUX.2-klein-base-4B`), run
     inference on the **distilled** `FLUX.2-klein-4B` (4 steps) — "in our
     testing, usually gives even better results";
   - dataset: 15-40 images sharing one look, >= 1024 px on the long edge,
     content-only captions with a made-up trigger word;
   - trainer: `ostris/ai-toolkit` (also BFL's own config example at
     https://docs.bfl.ai/flux_2/flux2_klein_training_example);
   - checkpoints every 250 steps; the visual peak is usually **step 750-1500**,
     not the last step; an 1800-step run on a 4090 takes under an hour;
   - loading an adapter: `pipe.load_lora_weights(...)` (needs `peft`).
3. **Measured inference footprint in this repo** — `s7-klein-1`:
   peak VRAM **7995 MB** with model CPU offload, 24.691 s/image,
   10/10 usable images (`docs/openmontage/image_gen/logs/s7-klein-1/manifest.json`).
4. **Kaggle accelerator spec** — the T4 x1 accelerator exposes 16 GB of VRAM
   (~15 GB usable). The bridge jobs in this repo run on that accelerator
   (`scripts/run_illustrations.py`, `KERNEL_SLUG`).

## 3. What a T4 attempt would have to change (NOT_CHECKED)

None of these has been measured here; each would need a real trial run and a
recorded memory profile before it could be claimed:

- resolution 512 instead of 1024 (the guide notes klein wants
  `(W*H)/256 <= 4096` and multiples of 16);
- a smaller LoRA rank / smaller target block set;
- gradient checkpointing + 8-bit optimizer + CPU offload of the text encoder;
- bf16 (the card's dtype) instead of the project's fp16 rule.

Even if one of these fits in 15 GB, the step time on a T4 is unknown, so the
"~60 min" figure cannot be transferred. Any such run would also have to
respect the project's $0 rule — Kaggle's free T4 quota is the only free
option, and the guide's own path is paid.

## 4. Licence of the adapter (and of what we may ship)

- The base model `FLUX.2-klein-base-4B` is **Apache-2.0**; the blog states
  explicitly: "Apache 2.0, so you can ship what you train."
- Community adapters exist and carry their own licences (the two examples in
  the article are Apache-2.0). An adapter we train ourselves would be
  published under **Apache-2.0** to keep the chain compatible with the base.
- The model card's out-of-scope-use list applies to derivatives, so an
  adapter inherits it.
- **NOT_CHECKED:** the card refers to BFL's "Self-Hosted Commercial License
  Terms" for commercial open-weight users. Whether those terms add anything
  to Apache-2.0 for a *hosted, commercial* deployment of a fine-tuned
  derivative was not verified here. Before any commercial use of an adapter
  (or of a derivative of it), a human has to read
  https://huggingface.co/black-forest-labs/FLUX.2-klein-4B (Licence section)
  and the BFL terms and confirm the chain. This is an `OWNER_GATED` legal
  question, not an agent decision.

## 5. Options that stay inside the rules today

1. **Use an existing adapter instead of training one** — the Hub lists 81
   adapters for this model; the documented examples are Apache-2.0. Zero GPU
   training cost, no paid route. Requires a rights record per adapter.
2. **Stay with seed + prompt anchoring** — the current consistency kit
   (`docs/openmontage/image_gen/CONSISTENCY_KIT.md`) gets character
   consistency from the canonical silhouette + anatomy counts + fixed seeds +
   the card-supported reference-image workflow, without any training.
3. **OWNER_GATED:** the owner may decide to fund a 24 GB GPU run. Until that
   decision is recorded, training stays BLOCKED. The agent does not wait on
   it and does not spend anything.

## 6. Explicitly not done

- No training was started, no trainer was installed, no dataset was
  assembled, no adapter was produced.
- No paid GPU was rented, no Kaggle kernel for training was submitted.
- The measurements in §2 are quoted from the cited sources; the only number
  measured in this repo is the inference footprint of `s7-klein-1`.
