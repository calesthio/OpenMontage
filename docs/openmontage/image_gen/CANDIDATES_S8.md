# S8-1 — Candidate license & fit gate (read-only, official Hugging Face cards)

**Scope:** decide which extra models may be *run* on the Kaggle T4 for the
5-model bake-off. Only official Hugging Face model cards, licences and the
public model API were read (`scripts/s8_candidates.py`, evidence:
`docs/openmontage/image_gen/S8_CANDIDATE_FACTS.json`). **No weights were
downloaded, nothing was executed from the hub, no blog or community source was
used as a specification.**

Access date for every URL below: **2026-10-22** (UTC).

Verdicts: `FITS_T4` | `NEEDS_OFFLOAD` | `TOO_BIG` | `LICENSE_BLOCKED` | `UNKNOWN`.
A model whose commercial-use terms are `LICENSE_BLOCKED` or `UNKNOWN` is
**NOT run** and is reported to the owner.

Hardware reference (measured in S7 on the same Kaggle GPU): **Tesla T4, 14.56 GiB
usable**; SDXL Base 1.0 in fp16 peaked at **9169.58 MB** with a plain
`pipe.to("cuda")`, FLUX.2-klein-4B peaked at **7995.02 MB** with CPU offload.

---

## 1. The three candidates the brief names

### 1.1 ByteDance/SDXL-Lightning — verdict **FITS_T4** (RUN)

| Field | Value | Source |
|---|---|---|
| Licence | `openrail++` (CreativeML Open RAIL++-M, dated July 26, 2023; "Copyright (c) 2024 Bytedance Inc. Copyright (c) 2023 Stability AI") | card `license:` field + `LICENSE.md` |
| Licence quote (commercial use is granted) | "**Grant of Copyright License.** Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare, publicly display, publicly perform, sublicense, and distribute the Complementary Material, the Model, and Derivatives of the Model." | https://huggingface.co/ByteDance/SDXL-Lightning/raw/main/LICENSE.md (2026-10-22) |
| Licence quote (what is restricted) | "**Use-based restrictions.** The restrictions set forth in Attachment A are considered Use-based restrictions. Therefore You cannot use the Model and the Derivatives of the Model for the specified restricted uses. You may use the Model subject to this License, including only for lawful purposes and in accordance with the License." — Attachment A lists prohibited uses (illegal use, harming minors, false information, PII, defamation, discrimination, medical advice, law-enforcement prediction); **no commercial-use prohibition**. | same URL (2026-10-22) |
| Gated | **No** (`"gated": false`) | HF API model card metadata (2026-10-22) |
| Parameters | SDXL family: 2.567 B (the repo ships no diffusers-format weights, so the hub reports no parameter count for the repo itself; the UNet checkpoint is the SDXL UNet) | file sizes below + S7 SDXL Base manifest (2.567 B) |
| Total weight size | repo total **49.47 GB** (16 checkpoint variants); the file we load, `sdxl_lightning_8step_unet.safetensors`, is **5135.15 MB** (fp16, 2 bytes/param) | HF API `?blobs=true` (2026-10-22) |
| Official dtype | **float16** — card snippet: `UNet2DConditionModel.from_config(base, subfolder="unet").to("cuda", torch.float16)` | card README (2026-10-22) |
| Official scheduler / steps / guidance | "Ensure sampler uses 'trailing' timesteps": `pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")`; "Ensure using the same inference steps as the loaded model and CFG set to 0": `pipe(prompt, num_inference_steps=8, guidance_scale=0)` for the 8-step UNet checkpoint | card README (2026-10-22) |
| Stated VRAM | none on the card | — |
| Pipeline class in RELEASED diffusers | `StableDiffusionXLPipeline` — present in v0.36.0, v0.37.0 and v0.41.0 (`src/diffusers/__init__.py`) | diffusers release tags on GitHub (2026-10-22) |
| fp16 on T4 reports | no vendor statement about T4 / 16 GB. Fit is inferred: the same SDXL Base UNet + text encoders ran fp16 on this T4 at 9169.58 MB peak (S7 `s7-sdxl-1`) | S7 manifest |
| **Verdict** | **FITS_T4** — OpenRAIL++ permits commercial use (use restrictions only), not gated, fp16 UNet checkpoint 5.1 GB, SDXL-family footprint already measured on this GPU | |

### 1.2 Lykon/dreamshaper-xl-lightning — verdict **FITS_T4** (RUN)

| Field | Value | Source |
|---|---|---|
| Licence | `openrail++` (card field; the repo ships no LICENSE file, the licence family is the SDXL one) | card `license:` field (2026-10-22) |
| Licence quote | same OpenRAIL++ grant and use-based restrictions as 1.1 (CreativeML Open RAIL++-M, quoted verbatim there): "…each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare, publicly display, publicly perform, sublicense, and distribute the Complementary Material, the Model, and Derivatives of the Model." | https://huggingface.co/ByteDance/SDXL-Lightning/raw/main/LICENSE.md (2026-10-22) — the licence text of the `openrail++` family; the Lykon card declares the same licence id |
| Gated | **No** (`"gated": false`) | HF API (2026-10-22) |
| Parameters | **2 567 463 684** (2.57 B), hub reports `F32` only | HF API `safetensors` (2026-10-22) |
| Total weight size | repo total **34.69 GB** (fp32 + fp16 copies + single-file checkpoints). The fp16 set actually downloaded is ≈ **7.5 GB** (`unet/diffusion_pytorch_model.fp16.safetensors` 5135.15 MB + `text_encoder_2` fp16 1389.38 MB + `text_encoder` fp16 + `vae` fp16) | HF API `?blobs=true` (2026-10-22) |
| Official dtype | **float16** — card snippet: `AutoPipelineForText2Image.from_pretrained('lykon/dreamshaper-xl-lightning', torch_dtype=torch.float16, variant="fp16")` | card README (2026-10-22) |
| Official scheduler / steps / guidance | `pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)`; `pipe(prompt, num_inference_steps=4, guidance_scale=2)` | card README (2026-10-22) |
| Stated VRAM | none on the card | — |
| Pipeline class in RELEASED diffusers | `StableDiffusionXLPipeline` (`model_index.json` `_class_name`), present in v0.36.0 / v0.37.0 / v0.41.0 | repo `model_index.json` + diffusers release tags (2026-10-22) |
| fp16 on T4 reports | no vendor statement about T4 / 16 GB; fit inferred from the S7 SDXL Base fp16 run (9169.58 MB peak) | S7 manifest |
| **Verdict** | **FITS_T4** — OpenRAIL++ (commercial OK with use restrictions), not gated, 2.57 B params, fp16 variants published | |

### 1.3 krea/Krea-2-Turbo — verdict **LICENSE_BLOCKED** (NOT RUN)

| Field | Value | Source |
|---|---|---|
| Licence | `other` — `license_name: krea-2-community-license`, `license_link: https://cdn.jsdelivr.net/gh/krea-ai/krea-2@db3984fbc6e13b34c0064990fc2d95ac64d00058/assets/hf_samples/LICENSE.pdf` | HF API `cardData` (2026-10-22) |
| Licence quote | Card gate text: "By clicking 'Agree', you agree to the [Krea 2 Community License Agreement](…) and acknowledge the [Acceptable Use Policy](https://www.krea.ai/krea-2-use-policy)." — **the licence itself is a PDF that this environment cannot read** (no `pdftotext`, no PDF library), so its commercial terms could not be quoted or verified | card `extra_gated_prompt` (2026-10-22) |
| Gated | **Yes — `"gated": "auto"`**: access requires an account, name, e-mail, company and an explicit checkbox agreeing to the licence | HF API (2026-10-22) |
| Parameters | **12 820 073 036** (12.82 B; hub reports BF16 12 498 501 632 + F32 321 571 404) | HF API `safetensors` (2026-10-22) |
| Total weight size | repo total **61.95 GB**; fp16 would be ≈ **25.6 GB** of weights (`transformer` 26.3 GB BF16 sharded + `text_encoder` 8.9 GB + `vae` 0.5 GB) | HF API `?blobs=true` (2026-10-22) |
| Official dtype | BF16 (hub dtype breakdown) | HF API (2026-10-22) |
| Stated VRAM | none on the card | — |
| Pipeline class in RELEASED diffusers | `Krea2Pipeline` — **absent in v0.36.0 and v0.37.0**, present only in v0.41.0 | diffusers release tags on GitHub (2026-10-22) |
| fp16 on T4 reports | none. S7 already proved that diffusers 0.41.0 cannot be installed next to transformers 4.57.6 (`ResolutionImpossible`) and that the 0.41.0 + transformers 5.20.2 stack fails to import (`cannot import name 'FqnToConfig' from 'torchao.quantization'`) | S7 `logs/s7-sdxl-1/install_log.json` |
| **Verdict** | **LICENSE_BLOCKED** — a gated, non-OpenRAIL community licence whose commercial terms could not be read, on top of a 12.8 B model that would need ≈25.6 GB of fp16 weights (TOO_BIG for a 16 GB T4 even with offload), and the only diffusers release that ships `Krea2Pipeline` is the 0.41.0 stack that S7 could not install. **Not run; the owner decides.** | |

**Owner decision needed for Krea 2 Turbo (not taken by the agent):** accept the
Krea 2 Community Licence + Acceptable Use Policy under a real account and
confirm the commercial terms, and provide a GPU with ≥ 32 GB, and allow
diffusers 0.41.0 (which forces transformers 5.x and a working `torchao`).

### 1.4 Replacement for the blocked Krea slot: Sana Sprint 1.6B — verdict **FITS_T4** (RUN)

Selected because the brief allows it *only* if the weights licence is
explicitly commercial-OK: **Apache-2.0**, whose grant clause is quoted verbatim
below and contains no revenue cap, no non-commercial clause and no use
restriction.

| Field | Value | Source |
|---|---|---|
| Licence | `apache-2.0` | HF API `cardData` (2026-10-22) |
| Licence quote (commercial use granted) | "Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form." | https://huggingface.co/Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers/raw/main/LICENSE (2026-10-22) |
| Gated | **No** (`"gated": false`) | HF API (2026-10-22) |
| Parameters | **1.6 B** (SANA-Sprint 1.6B; `SanaTransformer2DModel` 3220.53 MB of bf16 weights + `Gemma2Model` text encoder 5228.71 MB + `AutoencoderDC` 1249.04 MB) | card README + HF API `?blobs=true` (2026-10-22) |
| Total weight size | **9.70 GB** for the whole pipeline (text encoder 4988.02 + 240.69 MB, transformer 3220.53 MB, vae 1249.04 MB) | HF API `?blobs=true` (2026-10-22) |
| Official dtype | **bfloat16** — card: "Model precision: torch.bfloat16 (BF16)"; snippet `SanaSprintPipeline.from_pretrained("Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers", torch_dtype=torch.bfloat16)` | card README (2026-10-22) |
| Official steps | "reducing inference steps from 20 to 1-4"; snippet: `pipeline(prompt=prompt, num_inference_steps=2)`; scheduler `SCMScheduler` | card README + `model_index.json` (2026-10-22) |
| Stated VRAM | none on the card | — |
| Pipeline class in RELEASED diffusers | `SanaSprintPipeline` (`model_index.json` `_class_name`) — present in v0.36.0, v0.37.0 and v0.41.0 | diffusers release tags (2026-10-22) |
| fp16 on T4 reports | no vendor statement about T4 / 16 GB. **Note the deviation:** the card mandates bf16 while the S8 brief mandates fp16 only, so the run uses fp16 and carries the S7 Z-Image risk of an fp16 numerical overflow (black frames) — the runner's black/NaN check is the fail-closed guard. | card + S8 brief |
| **Verdict** | **FITS_T4** — Apache-2.0 is explicitly commercial-OK, not gated, 9.7 GB of weights against 14.56 GiB of usable VRAM (offload as a safety margin) | |

---

## 2. Backups checked (the "3 others" plus the sdxl-turbo control)

| Model | Licence | Gated | Params | Weight size | Official dtype / steps | Pipeline class in released diffusers | Verdict |
|---|---|---|---|---|---|---|---|
| `stabilityai/sdxl-turbo` | `other` → `sai-nc-community` | No | 2 567 463 684 | 41.63 GB repo, ≈7.5 GB fp16 set | fp16 variants; 1-step | `StableDiffusionXLPipeline` (0.36/0.37/0.41) | **LICENSE_BLOCKED** — "This Agreement is intended to allow research, non-commercial, and limited commercial uses of the Models free of charge. In order to ensure that certain limited commercial uses of the Models continue to be allowed, this Agreement preserves free access to the Models for people or organizations generating annual revenue of less than US $1,000,000 (or local currency equivalent)." (https://huggingface.co/stabilityai/sdxl-turbo/raw/main/LICENSE.md, 2026-10-22). A revenue ceiling is not a clean commercial licence for an own-channel monetised YouTube pipeline. **Not run.** |
| `Efficient-Large-Model/Sana_1600M_1024px_diffusers` | `apache-2.0` | No | 1.6 B | 25.79 GB repo (fp16 copies included), ≈10.7 GB fp16 set | bf16 official; SanaPipeline | `SanaPipeline` (0.36/0.37/0.41) | FITS_T4 — commercial-OK backup, held in reserve (the Sprint checkpoint is the faster one) |
| `segmind/SSD-1B` | `apache-2.0` | No | 1 331 334 404 | 26.79 GB repo; fp16 UNet 2662.79 MB | fp16 variants | `StableDiffusionXLPipeline` (0.36/0.37/0.41) | FITS_T4 — smallest commercial-OK backup (1.33 B) |
| `PixArt-alpha/PixArt-Sigma-XL-2-1024-MS` | `openrail++` | No | 610 856 096 (DiT only) | 21.83 GB; T5-XXL text encoder 19.05 GB **fp32 only, no fp16 file** | fp32 text encoder; `PixArtSigmaPipeline` | `PixArtSigmaPipeline` (0.36/0.37/0.41) | NEEDS_OFFLOAD — ≈11 GB in fp16, no vendor fp16 weight set, tight on a T4. Backup of last resort. |

**Backup ranking (if a run fails):** 1) `Sana_1600M_1024px_diffusers`
(Apache-2.0, 1.6 B, fits), 2) `segmind/SSD-1B` (Apache-2.0, 1.33 B, fits),
3) `PixArt-Sigma-XL-2-1024-MS` (OpenRAIL++, needs offload).

---

## 3. Run list decided by this gate

| # | Model | Repo | Licence | Verdict | Prompt variant | Scheduler / steps / guidance |
|---|---|---|---|---|---|---|
| 1 | SDXL-Lightning 8-step | `ByteDance/SDXL-Lightning` (UNet checkpoint) + `stabilityai/stable-diffusion-xl-base-1.0` | OpenRAIL++ | FITS_T4 | SDXL family → variant **A** (structured phrases + short negative prompt) | EulerDiscreteScheduler, `timestep_spacing="trailing"`, 8 steps, guidance 0.0 (card) |
| 2 | DreamShaper XL Lightning | `Lykon/dreamshaper-xl-lightning` | OpenRAIL++ | FITS_T4 | variant **A** | DPMSolverMultistep, 4 steps, guidance 2.0 (card) |
| 3 | SANA-Sprint 1.6B 1024px | `Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers` | Apache-2.0 | FITS_T4 | card prescribes no negative-prompt behaviour → prose, anatomy first, no negative prompt (same text as the S7 klein variant C) | SCMScheduler, 2 steps (card snippet), guidance 4.5 (diffusers `SanaSprintPipeline` default; card prescribes none) |

Reused from S7 without re-running: **SDXL Base 1.0** (OpenRAIL++, variant A)
and **FLUX.2-klein-4B** (BFL card, variant C). **Z-Image-Turbo is not submitted
in S8** (S7 verdict: BLOCKED).

## 4. What this gate did not check

- Whether the *outputs* are acceptable to a publisher (no content policy
  review of the frames) — that is the owner's call on the blind pack.
- Whether the OpenRAIL++ use-based restrictions are met by our end use: the
  restrictions are about the model's misuse, not about a science-documentary
  YouTube channel, but the owner keeps the final say.
- Commercial terms of the Krea 2 Community Licence (PDF not readable here).
