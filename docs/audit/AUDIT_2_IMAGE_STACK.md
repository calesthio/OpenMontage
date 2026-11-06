# AUDIT_2_IMAGE_STACK — Image generation stack

Read-only audit. No code changes, no generation, no GPU/Kaggle/Flow spend.
Date: 2026-11-06. Active branch: `kilo/mega-100`.

## 1. Core image-generation modules

| File | Exists | Lines | Status | Tests |
|---|---|---|---|---|
| `lib/gflow_wrapper.py` | yes | 546 | Real code: subprocess driver for gflow-cli, zero-cost gate, FlowJob integration, READY_FOR_APPROVAL stop | `tests/lib/test_gflow_wrapper.py` |
| `lib/image_generation_engine.py` | yes | 762 | Real code: full pipeline orchestrator (plan/execute/resume/QC/duplicate check), dry-run default | `tests/lib/test_image_generation_engine.py` |
| `lib/gflow_provider.py` | yes | 184 | Real code: adapter GflowWrapper -> engine, READY_FOR_APPROVAL only | none direct |
| `lib/asset_registry.py` | yes | 391 | Real code: manifest/prompts/jobs persistence, sha256, integrity check | none direct |
| `lib/batch_scheduler.py` | yes | 238 | Real code: chunks into 1-4 prompts/call, batch state, retryable | none direct |
| `lib/recovery_manager.py` | yes | 155 | Real code: checkpoint resume, skip completed, re-attempt failed | none direct |
| `lib/image_uniqueness.py` | yes | 157 | Real code: aHash + Hamming duplicate detection, revision prompt builder | `tests/lib/test_image_uniqueness.py` |
| `lib/flow_job_manager.py` | yes | 814 | Real code: SQLite job lifecycle DRAFT->...->READY_FOR_APPROVAL, read-only, stops before spend | `tests/test_flow_job_manager.py`, `tests/test_flow_job_manager_mock.py` |
| `lib/zero_cost_gate.py` | yes | 492 | Real code: fail-closed gate, null cost blocks, failure taxonomy, budget ledger | `tests/factory/test_zero_cost_gate.py` |

Notes:
- No stubs found in these files (only normal `pass` in exception handlers).
- `image_generation_engine.py` defaults to dry-run/mock; credit-bearing execution requires explicit approval and passes through zero-cost gate.
- `gflow_wrapper.py` never transitions jobs to APPROVED/SUBMITTED automatically.
- `asset_registry.py`, `batch_scheduler.py`, `recovery_manager.py`, `gflow_provider.py` have no dedicated test files; they are exercised indirectly via engine/flow tests.

## 2. Kaggle bridge and model runs

`tools/kaggle_bridge/kaggle_bridge.py` — 907 lines, real generic bridge (build/push/poll/fetch/verify/QC/run). Not model-specific.

Models actually run (from state files and bakeoff reports):
- SDXL Base 1.0 + sdxl-vae-fp16-fix: DONE (10/10, ~41.4 s/img, ~9.17 GB VRAM).
- FLUX.2-klein-4B: DONE (10/10, ~24.69 s/img, ~7.995 GB VRAM).
- SDXL-Lightning: DONE (10/10, ~3.94 s/img).
- DreamShaper XL Lightning: DONE (10/10, ~5.11 s/img).
- Z-Image-Turbo: BLOCKED (4 attempts, 0 usable images; fp16 NaN -> black frames; CUDA OOM on load).
- SANA-Sprint 1.6B: BLOCKED (4 attempts, 0 usable images; fp16 NaN; OOM without offload).
- G2 bake-off (SDXL-Lightning + Z-Image + klein): FAILED (0 images, 2 runs; T4 CPU float32 fallback broken; bitsandbytes missing).

G1/G2/G3 references:
- G1 (image license evidence + policy): DONE — `docs/openmontage/image_gen/LICENSE_EVIDENCE.md`, `AI_IMAGE_POLICY.md`, `G1_REPORT.md`.
- G2 (image bake-off): CONCLUDED FAILED — `G2_STATE.md`, 0 images, no `G2_REPORT.md`.
- G3 (episode pipeline): DONE (engine) + CONFIG-LOCKED P1 in `MEGA_STATE.md`/`PIPE_STATE.md` (klein locked, sdxl-lightning FAST_FALLBACK, model-adapter interface, 40 new tests).

## 3. docs/openmontage/image_gen/ contents

Files: see directory listing (38+ files). Key:
- `LICENSE_EVIDENCE.md` (5483 bytes): license evidence from HF cards. SDXL-Lightning + SDXL base = OpenRAIL++/Open RAIL++-M commercial OK. FLUX.1-schnell apache-2.0. Z-Image-Turbo apache-2.0. FLUX.2-klein-4B apache-2.0 (pilot base model). FLUX 3 Image Klein = flux-kommunity-license, commercial only for Qualifying Users (<$5M). Verdict: no component blocked on license; FLUX 3 Image Klein needs owner decision (revenue threshold + diffusers compatibility unconfirmed).
- `AI_IMAGE_POLICY.md` (3324 bytes): AI images only as illustrations (backdrops/schematics/sketches/textures), never as real footage. No real people/events/emblems/insignia. No text in image. Not photoreal. Every AI image must carry visible "Illustration" label. Max 10-15% of runtime. Synthetic-content disclosure per YouTube rules. Records: sha256, prompt, seed, params, model/revisions, rights_basis=ai_generated_illustration, generator=AI.

## 4. Stickman SVG / seed locking / reference image / LoRA

- Stickman SVG rig: IMPLEMENTED as pure-Python SVG emitter in `lib/stickman_rig.py` (RigProfile, Pose/Expression/Prop, forward kinematics, SVG emission, keyframe validation, content-addressed cache key). Zero-cost, no rendering/network. Tests: `tests/lib/test_stickman_rig.py`.
- Seed locking: IMPLEMENTED in style kit / creature sheet pipeline. Fixed seed per creature+view (range 3000-3999), deterministic job files (byte-identical), seed log append-only unique. See `tools/illustration/style_kit.py`, `creature_sheet.py`, `docs/openmontage/image_gen/CONSISTENCY_KIT.md`.
- Reference image (img2img): IMPLEMENTED only for klein (FLUX.2-klein-4B), documented in `REFERENCE_IMAGE_SUPPORT` table with HF card citation. Other models (sdxl, sdxl-lightning, dreamshaper, zimage) explicitly NOT supported -> fallback to seed + prompt anchoring. Canonical creature sheets use front view as reference for other views when model supports it.
- LoRA: NOT IMPLEMENTED (no training). Feasibility documented in `docs/openmontage/image_gen/LORA_FEASIBILITY.md`: ~24 GB VRAM needed, T4 16 GB insufficient, rented GPU = paid route BLOCKED. 81 community adapters exist; examples Apache-2.0. No LoRA trained in repo.

## Reproduce commands
```
wc -l lib/gflow_wrapper.py lib/image_generation_engine.py lib/gflow_provider.py lib/asset_registry.py lib/batch_scheduler.py lib/recovery_manager.py lib/image_uniqueness.py lib/flow_job_manager.py lib/zero_cost_gate.py
ls docs/openmontage/image_gen/
cat docs/openmontage/image_gen/LICENSE_EVIDENCE.md
cat docs/openmontage/image_gen/AI_IMAGE_POLICY.md
grep -rni "seed lock\|reference image\|lora" lib/ tools/ scripts/
```
