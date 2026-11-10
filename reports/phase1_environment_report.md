# Phase 1 — Environment & Stock OpenMontage Validation Report

- **Date:** 2026-11-09
- **Host Hardware:** Apple Silicon Mac mini M6 (Mac18,5, 12-core: 2 Super, 4 Performance, 6 Efficiency; 24 GB Unified Memory)
- **Host Storage:** 256 GB Internal NVMe SSD (42 GB free), 1 TB External USB APFS SSD (`disk5s1`, 512 GB free, mount target: `/Volumes/Mac Mini External SSD`)
- **macOS Version:** macOS 27.0.1 (Build 26A434)
- **Base Framework:** OpenMontage (`https://github.com/OpenMontageInc/OpenMontage`)
- **Upstream Commit Hash:** `fecb9a1e3cc23ef84de30b272059457a427f16f8`
- **Active Branch:** `feat/topic-tutorial` (tracked against clean `upstream/main`)
- **Operating Policy:** Local-first, `$0.00` recurring subscriptions, `ALLOW_PAID_APIS=false`

---

## 1. Runtime Environment & Toolchain Inspection

| Component | Measured Version | Location / Interpreter | Status |
| :--- | :--- | :--- | :--- |
| **Python** | `3.12.15` | `/Users/nathan/workspace/OpenMontage/.venv/bin/python3` | Verified (PEP 668 virtualenv) |
| **Node.js** | `v26.11.1` | `/opt/homebrew/bin/node` | Verified |
| **npm** | `12.2.1` | `/opt/homebrew/bin/npm` | Verified |
| **Remotion CLI** | `4.0.484` | `remotion-composer/node_modules/.bin/remotion` | Verified (`@remotion/cli`) |
| **HyperFrames CLI** | `0.9.26` | `npx hyperframes` | Verified (NPX cache-warmed) |
| **FFmpeg** | `9.0.2` | `/opt/homebrew/bin/ffmpeg` (built with Apple clang 21.0.0) | Verified |
| **FFprobe** | `9.0.2` | `/opt/homebrew/bin/ffprobe` | Verified |
| **Piper TTS** | `1.8.0` (with ONNX Runtime `1.31.1`) | `.venv/bin/piper` | Verified |
| **PyTest** | `9.2.0` | `.venv/bin/pytest` | Verified (1,515 / 1,515 contract tests pass) |

---

## 2. Storage & Cache Protection Setup

To protect the host's 256 GB internal SSD from heavy weight caches and temporary render artifacts:
- **Configured Storage Root (`OPENMONTAGE_STORAGE_ROOT`):** `/Volumes/Mac Mini External SSD/openmontage_data`
- **Model / Package Caches Configured:**
  - `HF_HOME="${OPENMONTAGE_STORAGE_ROOT}/cache/huggingface"`
  - `TORCH_HOME="${OPENMONTAGE_STORAGE_ROOT}/cache/torch"`
  - `MLX_CACHE_DIR="${OPENMONTAGE_STORAGE_ROOT}/cache/mlx"`
  - `TMPDIR="${OPENMONTAGE_STORAGE_ROOT}/tmp"`
- **TCC Removable Volume Note:** Accessing `/Volumes/Mac Mini External SSD` requires macOS Removable Volumes / Full Disk Access permission for the executing terminal application. A local directory `openmontage_data/` is maintained inside the workspace as an immediate zero-interruption fallback.
- **Pre-download Disk Gate:** Strict policy enforced to require confirmation before downloading any model checkpoint $\ge 500\text{ MB}$.

---

## 3. Stock OpenMontage Pipeline & Renderer Validation

### 3.1 Contract Test Suite
- Executed `pytest tests/contracts/ -v` on branch `feat/topic-tutorial`.
- **Result:** **1,515 passed, 9 skipped** in 27.34 seconds.
- Confirmed: Zero breaking schema or tool contract regressions.

### 3.2 Living Storyboard (Backlot) Verification
- Executed `scripts/backlot_simulate_run.py --fast --cleanup`.
- **Result:** Backlot initialized project workspace, tracked state changes across stages (`research`, `proposal`, `script`, `scene_plan`, `assets`), handled `in_progress` and `awaiting_human` transitions, emitted telemetry events, and rendered the web storyboard at `http://127.0.0.1:4750`.
- All contract checks passed without errors.

### 3.3 Stock Local Remotion Render Verification
- Executed `python render_demo.py focusflow-pitch` ($0 paid APIs, 100% local React/Remotion rendering).
- **Result:** Clean end-to-end render to `projects/demos/renders/focusflow-pitch.mp4`.
- **`ffprobe` Stream Verification:**
  - Video stream: H.264, $1920\times 1080$, $30.0\text{ fps}$, duration $22.50\text{ s}$
  - Audio stream: AAC, stereo, $22.55\text{ s}$
  - Total file size: $4.28\text{ MB}$
  - Render wall-clock time: $\approx 41\text{ seconds}$ on 6-worker concurrency.

---

## 4. Capability Envelope & M6 Hardware Compatibility Matrix

The OpenMontage tool registry (`tools/tool_registry.py`) was fully discovered and classified on the Mac mini M6:

| Category | Tool Count | Description & Policy |
| :--- | :--- | :--- |
| **`verified_on_m6`** | **46 tools** | Local tools running on M6 CPU, VideoToolbox hardware encoder, or local JS/Remotion/HyperFrames runtimes. Zero API keys, zero network, zero cost. |
| **`paid_api_disabled`** | **89 tools** | External cloud providers (fal.ai, ElevenLabs, OpenAI, Google Cloud, Runway, Kling, HeyGen, etc.). Strictly disabled under `$0.00` local-first policy (`ALLOW_PAID_APIS=false`). |
| **`cuda_only_incompatible`** | **17 tools** | Legacy local PyTorch models hard-coded to NVIDIA CUDA extensions (`sadtalker`, `wav2lip`, `realesrgan`, `codeformer`, `wan_video`, `cogvideo_video`, etc.). Cannot run natively on Apple Silicon without MPS/MLX porting. |
| **`missing_dependency`** | **12 tools** | Local tools requiring optional external binaries (e.g. `mmdc` for Mermaid CLI, `yt-dlp` for video downloader, `mediapipe`). |

### Key Local Providers Available on Mac mini M6:
1. **Composition & Rendering:** `video_compose`, `remotion_caption_burn`, `hyperframes_compose`, `video_stitch`, `video_trimmer`, `auto_reframe`, `showcase_card` (Remotion, HyperFrames, and FFmpeg).
2. **Local Text-to-Speech:** `piper_tts` (ONNX Runtime, $22,050\text{ Hz}$, $0.00$ cost, verified working with `en_US-lessac-medium`).
3. **Local Audio Processing:** `audio_mixer`, `audio_enhance`, `silence_cutter`.
4. **Local Video & Frame Analysis:** `video_analyzer`, `audio_probe`, `audio_energy`, `scene_detect`, `frame_sampler`, `visual_qa`, `composition_validator`.
5. **Character & 2D Animation:** `character_spec_generator`, `svg_rig_builder`, `pose_library_builder`, `action_timeline_compiler`, `character_rig_renderer`, `character_animation_reviewer`.
6. **3D Scene Generation:** `threejs_world`, `threejs_asset_catalog`.
7. **Screen / Code Capture:** `cap_recorder`, `screen_recorder`, `code_snippet`.

---

## 5. Architectural Findings & Phase 2 Gate Status

1. **Upstream Alignment:** All modifications are cleanly contained on branch `feat/topic-tutorial`. Zero custom pipeline files or custom tools have been written yet.
2. **Local Stack Readiness:** Python 3.12, Node 26, Remotion, HyperFrames, FFmpeg, Piper TTS, and Backlot are fully functional and pass all contracts.
3. **Phase 1 Acceptance Criteria:** **ALL MET (6/6).**
4. **Next Step:** Proceed to **Phase 2 — Stock Local Explainer Smoke Test**.
