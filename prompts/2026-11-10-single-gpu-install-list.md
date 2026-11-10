---
title: Single-GPU open-weight stack — extend the vastai-comfyui install
created: 2026-11-10
status: draft
source_request: "เขียน prompt รายการที่ต้องติดตั้งเพิ่ม" (rent ONE vast.ai machine that runs everything; what must be installed on top of the vastai-comfyui toolkit)
stopping_point: Stop 1 after Phase 0 (four decisions put to the user). Stop 2 after Phase 2 (offline work done, report, ask before any rent). Phase 3 (OpenMontage edits) only after approval. Never rent a GPU.
verified_paths:
  - ~/Documents/Workspaces/max/vastai-comfyui/CLAUDE.md
  - ~/Documents/Workspaces/max/vastai-comfyui/RUNBOOK.md
  - ~/Documents/Workspaces/max/vastai-comfyui/vast.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/setup_h3.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/setup_voice.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/setup_tools.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/rent_check.py
  - ~/Documents/Workspaces/max/vastai-comfyui/text-to-image/setup_qwen21.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/tests/run_all.sh
  - ~/Documents/Workspaces/max/vastai-comfyui/tests/test_vast_guards.py
  - ~/Documents/Workspaces/max/vastai-comfyui/tests/test_vast_ssh.py
  - docs/vast-ai-open-weight-stack.md
  - tools/_comfyui/metadata.py
  - tools/_comfyui/workflows/minimax-h3-t2v.json
  - tools/_comfyui/workflows/minimax-h3-i2v.json
  - tools/_comfyui/workflows/ace-step-1-t2a.json
  - tools/audio/comfyui_music.py
  - tests/contracts/test_comfyui_open_weight_workflows.py
  - AGENT_GUIDE.md
---
You are extending the vast.ai toolkit in ~/Documents/Workspaces/max/vastai-comfyui so that ONE rented GPU can run every open-weight model the user wants for English short clips, and so that OpenMontage (~/Documents/Workspaces/max/opensource/OpenMontage) can use that machine. Start this session in the vastai-comfyui directory. Reply to the user in Thai; write code, comments, commit messages and docs in English.

## Context (read from files and the Hugging Face API on 2026-11-10; nothing was run on a GPU)

Target machine, from OpenMontage `docs/vast-ai-open-weight-stack.md` section 2: one RTX PRO 6000 (96 GB), CUDA 13 host driver, host RAM at least 120 GB, disk 300 GB, the `vastai/comfy` template. The toolkit has never run on this card: its timings are RTX 5090 (H3) and RTX 4090 (Qwen).

What the toolkit installs today (`vast.sh setup` runs its jobs one after another):
- H3: `setup_h3.sh` (download block near lines 62-68) fetches `minimax_h3_fl2va_pruned_fp8_scaled`, `qwen3vl_32b_minimax_h3_nvfp4_awq`, both VAEs and the 8-step turbo LoRA (about 43 GB). `--with-ref2va` adds the ref2va int8 file and its 4-step LoRA.
- Qwen-Image-2.1 int8 through `text-to-image/setup_qwen21.sh` (3 files, about 17.3 GB; `--with-pe` adds 9.47 GB).
- VoxCPM2 (`voxcpm==2.0.3`) in `/workspace/stylevenv` through `setup_voice.sh`, and SyncNet through `setup_tools.sh`.

Not covered by the toolkit: music, speech-to-text, any TTS besides VoxCPM2, and a tunnel for OpenMontage. `vast.sh offers` is fixed to `gpu_name=RTX_5090` and `cpu_ram>=48` (around line 366). `DL_GB` defaults to 120 (around lines 368, 383, 413). `rent` defaults to a 200 GB disk.

Known mismatch: OpenMontage's bundled H3 graphs and its `BUNDLED_MODEL_STACKS` name `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (`tools/_comfyui/metadata.py` line 36, `minimax-h3-t2v.json` line 5, `minimax-h3-i2v.json` line 11). The toolkit downloads the fp8_scaled file instead, so a machine prepared only by the toolkit fails OpenMontage's missing-model check. Both files exist in `Comfy-Org/MiniMax-H3` (HF API). The contract test `tests/contracts/test_comfyui_open_weight_workflows.py` requires graph model names to equal the metadata stack, so graphs and metadata must change together.

Files to add (sizes from the HF API; the licence column is the HF tag only, the licence texts were NOT read):

| What | Repo / file | Size | Licence tag | How |
|---|---|---|---|---|
| Music: ACE-Step 1.5 turbo | `Comfy-Org/ACE-Step-1.5`, `checkpoints/ace_step_1.5_turbo_aio.safetensors` | 10.03 GB | apache-2.0 | into `models/checkpoints/` |
| STT: Qwen3-ASR-1.7B | `Qwen/Qwen3-ASR-1.7B` | 4.7 GB | apache-2.0 | `pip install -U qwen-asr` (its README) |
| STT word timestamps: Qwen3-ForcedAligner-0.6B | `Qwen/Qwen3-ForcedAligner-0.6B` | 1.8 GB | apache-2.0 | same package |
| H3 int8 fl2va (only if D1 = a) | `Comfy-Org/MiniMax-H3`, `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 21.0 GB (OpenMontage doc) | n/a | needs cu130 torch |
| Optional TTS: Drama 3 int4 | `fishaudio/drama-3-int4` | 22.1 GB per its README, 24 GB sum of files | other (fish-audio-community-license) | SGLang Omni in its own venv: clone `sgl-project/sglang-omni`, `uv venv -p 3.12`, `uv pip install --prerelease=allow -e ".[fishaudio]"`, then `sgl-omni serve --model-path <repo> --port 8000`. Its README serves `akhaliq/drama-3-int4` while the OpenMontage doc serves `fishaudio/drama-3-int4`: check which before use. |

Optional, not default: ACE-Step 1.5 XL turbo (9.97 GB plus `qwen_4b_ace15` 8.38 GB plus VAE 0.34 GB), Stable Audio 3 Medium (9.22 GB), Nemotron 3.5 Transcribe FP8 (34.7 GB, separate vLLM server, OpenMDW-1.1), YuE2 (`cc-by-nc-4.0`: skip unless the output is never sold).

Licence facts to carry (from OpenMontage's docs and metadata, not re-read): H3 is not authorised in the US, EU, UK or South Korea, outputs included; Qwen-Image-2.1 is research-only.

## Phase 0 — read, then ask (no edits)

Read the toolkit's `CLAUDE.md` (its rules bind this session: run `tests/run_all.sh` before committing, stage only your own files, commit and push each finished task as it authorises, never print keys, spending decisions stay with the user), `RUNBOOK.md` ("Quick start", "Set up a new instance", Known problems groups R and I), `vast.sh` (`offers`, `rent`, `setup`, `job`, `up`), `setup_h3.sh`, `setup_voice.sh`, `text-to-image/setup_qwen21.sh` and `rent_check.py`. Read OpenMontage's `docs/vast-ai-open-weight-stack.md` in full: it already lists manual `fetch` steps for this machine, so do not duplicate or contradict it.

Then put these four decisions to the user with AskUserQuestion, each with a recommendation:
- D1, the H3 diffusion file. (a) Add the int8 fl2va download to the toolkit (+21.0 GB; needs cu130 torch, which `setup_h3.sh` switches to when the driver reports CUDA 13; OpenMontage's graphs stay unchanged). Recommended. (b) Change OpenMontage's graphs, metadata and doc to fp8_scaled, the file the toolkit measured on an RTX 5090.
- D2, music default: ACE-Step 1.5 turbo (one file, 10.03 GB; recommended) or XL turbo (about 18.7 GB; its template is not confirmed).
- D3, STT: Qwen3-ASR plus ForcedAligner (6.5 GB, pip; recommended) or Nemotron FP8 (34.7 GB, separate vLLM server).
- D4, Drama 3 int4: install now, or later (recommended: later).

STOP 1: wait for the answers before editing anything.

## Phase 1 — toolkit changes (offline, on the Mac)

1. New `setup_audio.sh`, modelled on `setup_voice.sh` and `setup_qwen21.sh`: idempotent downloads with the byte-size check; a venv created with `--system-site-packages` on `/venv/main` so ComfyUI's torch stays untouched; package versions pinned from the package's own README at the time (verify the API before coding against it); fail at once when `nvidia-smi -L` fails (RUNBOOK R11). Flags follow D2 to D4.
2. `setup_h3.sh`: per D1(a), add the int8 file behind a flag, and only when the active torch is cu130.
3. `vast.sh`: add the new script to the `up` upload list and run it as a `job` after `setup_h3` and `setup_tools` (setup_h3 may reinstall torch, so jobs stay sequential). Let `offers` take `GPU_NAME` (default `RTX_5090`) and `MIN_RAM` (default 48). The PRO 6000 query is `gpu_name in [RTX_PRO_6000_WS,RTX_PRO_6000_S,RTX_PRO_6000] gpu_ram>=90 cpu_ram>=120` with disk at least 300. Make `DL_GB` and the disk size follow the chosen flags, computed from the sizes in the scripts, not a hard-coded guess.
4. New `vast.sh tunnel`: forward local 8188 to the instance's `127.0.0.1:18188` (and an optional extra port such as 8000), reusing vast.sh's key, known_hosts file and proxy fallback. Refuse when `.vast_instance` is missing. ComfyUI has no authentication, so never expose the port.
5. Tests: cover flag parsing, the `offers` query string and the tunnel command. Add any new test file to the `TESTS` list in `tests/run_all.sh`, and run it until it prints ALL CHECKS PASSED.
6. Docs: the `vast.sh` header comment and RUNBOOK "Set up a new instance", with a note that the PRO 6000 run is unverified.

Commit as the toolkit's CLAUDE.md requires.

## Phase 2 — verify without a GPU

Run `tests/run_all.sh`. Optionally run `./vast.sh offers` with the PRO 6000 filter to check the query and the table (a read-only API call). Never run `rent`, `vastai create`, `stop` or `destroy`. Mark everything that was not run on a GPU as unverified.

STOP 2: report in Thai the files changed, the test output and the open items: the first live run on a PRO 6000, H3 int8 on that card, the Qwen3-ASR API, Drama 3 serving. Say that the credit must be read live (the last value recorded in the repo, $1.21 on 2026-11-09, is stale), then ask whether the user wants to rent.

## Phase 3 — OpenMontage side (propose first, edit only after approval)

Read OpenMontage's `AGENT_GUIDE.md` first. Present a short plan covering: (i) H3 graph, metadata and doc consistency per D1; (ii) an ACE-Step 1.5 workflow, its metadata stack and the `_REQUIRED_MODELS` constant in `tools/audio/comfyui_music.py`, which still target ACE-Step v1 (see about lines 3-7, 43-44, 63, 240, and `ace-step-1-t2a.json`); (iii) a `BaseTool` for Qwen3-ASR, and for VoxCPM2 or Drama 3 if chosen, including how the Mac reaches the instance; (iv) the numbers in `docs/vast-ai-open-weight-stack.md` (disk 300 GB, file sizes).

OpenMontage's working tree holds uncommitted work of the user (modified: `.agents/skills/comfyui/SKILL.md`, `.agents/skills/minimax-h3/SKILL.md`, `tests/tools/test_new_video_model_support.py`, `tools/_comfyui/metadata.py`, `tools/graphics/comfyui_image.py`, `tools/video/comfyui_video.py`; untracked: `docs/vast-ai-open-weight-stack.md`, `tests/contracts/test_comfyui_open_weight_workflows.py`, the `minimax-h3-*.json` and `qwen-image-2-1-t2i.json` workflows, and more). Do not stage or commit those. If on `main`, branch first, and commit only when asked.

## Constraints

- Never rent, create, stop or destroy an instance. Spending stays with the user.
- Never print or log `hf_token.txt`, `VASTAI_API_KEY` or `HUGGINGFACE_API_KEY`.
- Label every size and timing by its source. Do not state that anything works on an RTX PRO 6000 as fact.
- Re-read each model's licence file before anyone relies on it for commercial use.

## Deliverable and stopping points

Phase 1 and 2 changes committed in the toolkit with passing tests, then the Thai report at STOP 2. The Phase 3 plan is presented as text only. Pause at STOP 1 (decisions), STOP 2 (report and rent question), and before any OpenMontage edit.

---
## Handoff notes
- Before writing this, I found that OpenMontage's `docs/vast-ai-open-weight-stack.md` already covers the same RTX PRO 6000 machine. My earlier chat answers had not read it. Corrections made here: disk is 300 GB (the doc), not my earlier 250 GB; the H3 file recommendation is now (a) add int8, because the doc's rent filter already requires CUDA 13 hosts, whereas I first suggested editing the graphs to fp8; Drama 3 size is 22.1 GB per its README and 24 GB as the sum of files.
- My defaults differ from the doc's optional list: ACE-Step turbo instead of XL, and Qwen3-ASR instead of Nemotron. Both are decisions D2 and D3 for the user.
- One prompt covers the toolkit (start the session in `vastai-comfyui`) and OpenMontage; OpenMontage edits are gated behind approval because its tree has uncommitted work. Line numbers are approximate and drift.
- Nothing here was run on a GPU. The HF sizes and licence tags were read on 2026-11-10; licence texts were not read.
