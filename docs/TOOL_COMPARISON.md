# OpenMontage — Tool Comparison & Selection Justification

**Purpose:** Compare already-installed tools against available alternatives for each factory capability. Replacement is justified only where the installed tool is genuinely unsuitable; no tool is swapped for mere name recognition.  
**Constraint:** No Google Flow generation, no credit spend. All judgments based on observed behavior, installed versions, license files, and documented pricing — never assumed capability.  
**Date:** 2026-11-02  
**Auditor:** Kilo

---

## 1. Method

For each capability family:

1. **Installed** — what is present in the repo/registry right now, its version, runtime, license, and observed status.
2. **Alternatives** — credible replacements (cloud or local) with quality, cost, license, commercial-use, and Codespaces compatibility.
3. **Verdict** — KEEP, REPLACE, or KEEP-AS-OPTIONAL, with a one-line justification.

Ratings: quality/performance/cost are qualitative (High/Medium/Low) grounded in observed evidence where available. "Commercial use" = permitted for monetized YouTube without extra clearance. "Codespaces" = runs in this container without GPU or paid keys.

---

## 2. Image generation

### 2.1 Installed: gflow-cli 0.92.0 → Google Flow / Nano Banana 2.1 (NARWHAL)

| Attribute | Observed value |
|---|---|
| Version | `gflow 0.92.0`, `/home/vscode/.local/bin/gflow` |
| Default model | NARWHAL (Nano Banana 2.1), `ref_cap=10` |
| Auth | Profile `flow_remote` (`vvv86357482@gmail.com`), 50 credits (read-only verified) |
| Spend control | `--no-spend`, `GFLOW_MCP_NO_SPEND=1`, MCP Security Proxy default-deny; generate tools hidden from MCP |
| Modes | t2i, i2i, batch (≤5), run JSON (≤50 prompts), upload, upscale (2k/4k) |
| Aspect ratios | 9:16, 16:9, 1:1, 4:3, 3:4 |
| Output | PNG, flat write to `--out`, local catalog + `gflow data` |
| Resume | `--resume` skips executed rows; `--continue-on-error` |
| Character consistency | Native multi-reference via `--reference-entity` (ref_cap=10) — no IP-Adapter needed |
| Observed output | One test image: `assets/generated/d745409c…_1.jpg`, 1376×768 (16:9), 208 KB |
| License | Google Flow terms (per-model); commercial use per Google's generative AI terms — owner must confirm |
| Codespaces | Runs headless with `GFLOW_CLI_HEADLESS=true` + Chrome `--no-sandbox` wrapper; confirmed working |

**Quality/performance:** One observed output at 1376×768; prior session generated 78 frames via FLUX.2 Klein on Kaggle T4 (~90s/frame, 11.15GB VRAM, zero NaN/black). Nano Banana per-frame speed not measured in this container (no spend). Quality assessed as acceptable for ink-illustration documentary style per the visual foundation in `lib/prompt_engineer.py`.

**Cost:** 50 credits remaining; per-image cost not measured (blocked by `--no-spend`). Unknown unit cost → BLOCKED under zero-cost gate until measured on a dry-run/sample.

### 2.2 Alternative: FLUX.2 Klein 4B (diffusers, local/Kaggle)

| Attribute | Value |
|---|---|
| Status | Prior session: 78 frames on Kaggle T4, 11.15GB VRAM, ~90s/frame, bfloat16, 0 failures |
| License | Apache-2.0 (Black Forest Labs) — commercial use confirmed |
| Codespaces | Not runnable here (no GPU, no torch/diffusers installed); requires Kaggle GPU bridge |
| Cost | $0 on Kaggle free tier (within quota); GPU bridge adds complexity |
| Character consistency | 4 reference images native; no IP-Adapter |

**Verdict:** KEEP-AS-OPTIONAL. FLUX.2 Klein is a proven alternative (Apache-2.0, commercial-clear) but requires GPU/Kaggle. Nano Banana via gflow is already wired and zero-setup for this container. Do not switch unless Nano Banana's per-image cost or character consistency proves inadequate after a measured sample.

### 2.3 Alternative: FLUX.1 / FLUX.2 via fal.ai or Atlas Cloud

| Attribute | Value |
|---|---|
| Status | Registered in registry (`flux_image`, `atlas_image`) but UNAVAILABLE (no API keys) |
| Cost | Paid per image; unknown unit cost → BLOCKED under zero-cost gate |
| Codespaces | Needs `FAL_KEY`/`ATLASCLOUD_API_KEY` env vars |

**Verdict:** KEEP-AS-OPTIONAL. Unlock only if owner supplies keys and approves spend. Not a replacement for the zero-cost default.

### 2.4 Alternative: local_diffusion (SDXL/Stable Diffusion via diffusers)

| Attribute | Value |
|---|---|
| Status | Registered, available in registry, but torch/diffusers NOT installed in this container |
| License | Model-dependent (SDXL: research/commercial per Stability license) |
| Codespaces | No GPU → CPU diffusion too slow for 160–250 images |

**Verdict:** KEEP-AS-OPTIONAL. Not viable for a 20–25 min film on CPU.

### 2.5 Image selection verdict

| Choice | Verdict | Justification |
|---|---|---|
| Default image engine | **gflow-cli Nano Banana 2.1** | Installed, authenticated, `--no-spend` enforced, native 10-ref character consistency, 16:9 support, resume. One observed successful output. |
| Paid alternatives (fal/Atlas/OpenAI/Recraft) | Keep as optional | Require keys + spend approval; zero-cost gate blocks by default. |
| Local diffusion | Keep as optional | No GPU in Codespaces; too slow for 160–250 images. |
| FLUX.2 Klein via Kaggle | Keep as fallback | Proven on T4; use if Nano Banana quality/cost unsatisfactory after measured sample. |

**Character consistency decision:** Use gflow `--reference-entity` (CHARACTER) with a single master reference. Do NOT revisit IP-Adapter (failed 5× in prior session; root cause was hand-constructed embeds instead of official `load_ip_adapter()` API).

---

## 3. Text-to-speech (narration)

### 3.1 Installed: Kokoro-82M (`af_heart`) in `/tmp/kilo/z1_venv`

| Attribute | Observed value |
|---|---|
| Version | kokoro==0.2.2, misaki==0.7.4, Python 3.12.3 |
| Voice | `af_heart` confirmed working |
| Output | 10 narration files, 18:20 total (~10% under 20–21 min target) |
| Runtime | Local CPU, no API key, $0 |
| License | Kokoro-82M weights Apache-2.0 (verified from HF model page); kokoro/misaki packages Apache-2.0. Training-data provenance partially unknown (CC BY + synthetic origin UNKNOWN) → owner sign-off required |
| Codespaces | Works in venv; not installed in main project env (`soundfile` missing) |
| Word timestamps | Not yet confirmed for Kokoro |

**Quality:** Technically verified (decode clean, RTF ~1.6–1.75 on CPU). Naturalness not assessed by agent (owner must listen per FACTORY_100_SPEC §1 rule 17 — "Quality of images/audio is judged by the OWNER").

**Cost:** $0 local.

### 3.2 Installed-but-absent: Piper (`en_US-lessac-medium`)

| Attribute | Value |
|---|---|
| Version | piper-tts 1.8.0 (installed in prior session) |
| License | Engine GPL-3.0-or-later (commercial permitted); VOICE `en_US-lessac-medium` license UNKNOWN — sidecar has dataset="lessac", no license field; manifest's CC-BY-4.0 claim UNVERIFIED |
| Status | Refused in `FACTORY_100_SPEC.md` L5 ("Piper en_US-lessac voices are REFUSED in code") |

**Verdict:** REPLACE. Do not use Piper for commercial publication until voice license is confirmed. Kokoro has clearer weights-level licensing.

### 3.3 Alternatives: cloud TTS (ElevenLabs, Google TTS, OpenAI, Azure, Cartesia, DashScope, Doubao, Fish Audio)

| Attribute | Value |
|---|---|
| Status | All registered, all UNAVAILABLE (no API keys) |
| Cost | Paid per character; unknown → BLOCKED under zero-cost gate |
| Quality | Generally higher than local (ElevenLabs especially) |
| Codespaces | Needs env var + key |

**Verdict:** KEEP-AS-OPTIONAL. Premium quality but violates $0 default. Unlock only with owner key + spend approval.

### 3.4 TTS selection verdict

| Choice | Verdict | Justification |
|---|---|---|
| Default narration | **Kokoro-82M `af_heart`** | $0, local, Apache-2.0 weights, measured output (18:20). Reinstall into main env. Owner to confirm voice by listening. |
| Piper | Replaced | Voice license unknown; explicitly refused in spec. |
| Cloud TTS | Optional | Higher quality but paid; zero-cost gate blocks by default. |

**Alignment note:** Kokoro word-level timestamps must be confirmed. If unavailable, use stable-ts forced alignment (tested: 82 timestamps / 80 words, ~100% coverage, RTF 0.27) or fall back to segment-level timing with manual correction via `lib/audio_sync.py`.

---

## 4. Audio synchronization & subtitles

### 4.1 Installed: `lib/audio_sync.py`

| Attribute | Value |
|---|---|
| Function | Binds production-manifest scenes to narration segments; computes start/end; flags too_long/too_short/gap/overlap/missing_audio; supports manual `adjust_segment` |
| Thresholds | too_long 1.5s, too_short 1.0s, gap 0.5s (configurable) |
| Cost | $0, local, pure Python |
| Status | Code works; not yet connected to gflow image outputs or Kokoro output in this container |

**Verdict:** KEEP. It is the correct alignment layer. Wire it to narration manifest + scene plan.

### 4.2 Installed: `tools/subtitle/subtitle_gen.py`

| Attribute | Value |
|---|---|
| Function | SRT/VTT generation from timestamps |
| Prior output | Reworked into per-line SRT (2–5s chunks, ≤42 chars/line) in pilot; spot-checked, not fully reviewed |
| Cost | $0 |

**Verdict:** KEEP. Use word-level timestamps (Kokoro or stable-ts) for precise subtitle sync; validate drift ≤0.5s per `tools/qa/qc.py`.

### 4.3 Alternative: stable-ts forced alignment

| Attribute | Observed |
|---|---|
| Tested | stable-ts 2.19.1 + faster-whisper tiny (72.1 MB); 82 timestamps / 80 reference words (~100% coverage), RTF 0.27 |
| Known-text `result.align` | Not present in API; not exercised |
| Cost | $0 local |

**Verdict:** KEEP-AS-OPTIONAL. Good fallback if Kokoro lacks word timestamps.

### 4.4 Subtitle burn-in

| Tool | Status |
|---|---|
| `tools/video/remotion_caption_burn.py` | Word-level caption burn via Remotion; needs Remotion |
| FFmpeg subtitle filter | Needs ffmpeg (not installed) |

**Verdict:** KEEP Remotion path; FFmpeg fallback once ffmpeg installed.

---

## 5. Composition / render engine

### 5.1 Installed: Remotion (via `remotion-composer/`)

| Attribute | Value |
|---|---|
| Version | node_modules installed (React/Remotion) |
| License | Free (solo project, ≤3 employees) confirmed |
| Scene types | `text_card`, `stat_card`, `callout`, `comparison`, `hero_title`, `terminal_scene`, `anime_scene`, `bar_chart`, `line_chart`, `pie_chart`, `kpi_grid`, `progress_bar` |
| Strengths | Spring animations, animated text/stat cards, charts, callouts, comparisons, word-level caption burn, TalkingHead avatar |
| Weaknesses | Prior session abandoned Remotion render at ~3% (multi-hour ETA); heavy Node stack; slower than FFmpeg for simple stills-led video |
| Codespaces | Node v26 + npx available; `node_modules` present |

**Verdict:** KEEP for motion-graphics/explainer pipelines. NOT default for a pure stills-led 20–25 min documentary unless motion is required.

### 5.2 Installed: HyperFrames (via npx)

| Attribute | Value |
|---|---|
| Version | 0.9.2 resolvable via `npx hyperframes` |
| `hyperframes doctor` | Passes version/node/cpu/memory/disk; docker not found; chrome-headless-shell not installed (falls back to screenshot mode) |
| Strengths | HTML/CSS/GSAP, kinetic typography, product promos, registry blocks, SVG character rigs, website-to-video |
| Weaknesses | Needs Node ≥22 + ffmpeg + npx; ffmpeg missing here; browser capture needs headless Chrome |

**Verdict:** KEEP-AS-OPTIONAL. Good for graphics-heavy pieces; not the base renderer for stills-led documentary.

### 5.3 Installed: FFmpeg

| Attribute | Value |
|---|---|
| Status | **NOT installed** in this container (`which ffmpeg` → not found) |
| Prior | ffmpeg 6.1.1 --enable-gpl confirmed in prior session (via apt) |
| Role | Base assembler: concat, trim, overlay, subtitle burn, audio mix, encode H.264/AAC |

**Verdict:** FIX — install ffmpeg. It is the essential base renderer and is absent, blocking `video_compose` (ffmpeg engine False), `finish_audio`, `qc`, and `render_integration` stub.

### 5.4 Composition engine verdict

| Choice | Verdict | Justification |
|---|---|---|
| Base renderer / assembler | **FFmpeg** | Required for concat, encode, subtitle burn, audio mix. Must install. |
| Motion graphics / explainers | **Remotion** | Present, Free license, rich scene stack. Present both at proposal per hard rule. |
| HTML/GSAP graphics layers | **HyperFrames** | Present via npx; optional for original graphic layers. |
| Still-led documentary (factory default) | **FFmpeg Ken Burns / motion_engine** | `lib/motion_engine.py` generates pan/zoom/parallax FFmpeg filters with variety enforcement. Simplest, fastest path for 1-sentence=1-image. |

Per AGENT_GUIDE.md hard rule: when both Remotion and HyperFrames are available, present both before locking `render_runtime`. Never silently default.

---

## 6. FFmpeg & additional animation tools

| Tool | Installed | Status | Role | Verdict |
|---|---|---|---|---|
| ffmpeg / ffprobe | No | Missing | Concat, encode, subtitle burn, audio mix, QC decode | FIX — install |
| `lib/motion_engine.py` + `tools/motion/motion_variety.py` | Yes | Code works | Pan/zoom/parallax/detail_crop/chapter-card FFmpeg filters + variety lint | KEEP |
| `lib/finish_audio.py` | Yes | Unavailable (needs ffmpeg) | Two-pass loudnorm + limiter + ducking | KEEP, install ffmpeg |
| `tools/qa/qc.py` | Yes | Unavailable (needs ffmpeg) | ffprobe, full_decode, blackdetect, freezedetect, silencedetect, ebur128 | KEEP, install ffmpeg |
| `tools/video/video_compose.py` | Yes | Blocked (ffmpeg engine False) | Routes to Remotion/HyperFrames/FFmpeg | KEEP, install ffmpeg |
| `tools/enhancement/*` (upscale, bg_remove, face_enhance) | Yes | Unavailable (needs deps) | Upscale/background removal | Optional |
| `tools/analysis/transcriber.py` | Yes | Unavailable (faster-whisper missing) | STT with word timestamps | Optional fallback |
| `tools/capture/*` (screen_recorder, cap_recorder) | Yes | cap_recorder available | Screen/demo capture | Not needed for factory |
| `tools/graphics/diagram_gen` | Yes | Available | Mermaid/diagram render (8.5 KB PNG proven) | KEEP |
| `tools/graphics/threejs_world` / `blender_world` | Yes | Unavailable (Blender not installed) | 3D worlds | Not needed for still-led factory |

**Animation tools verdict:** No additional animation library needed. `lib/motion_engine.py` + FFmpeg filters cover pan/zoom/parallax for stills. Remotion covers motion graphics. Do not add Lottie/GSAP as standalone — they're already behind HyperFrames/Remotion.

---

## 7. Automation & job management

### 7.1 Installed: `lib/flow_job_manager.py` + `lib/flow_integration.py`

| Attribute | Value |
|---|---|
| State machine | DRAFT → VALIDATED → READY_FOR_APPROVAL → APPROVED → SUBMITTED → COMPLETED/FAILED |
| Auto-stop | At READY_FOR_APPROVAL (no auto-spend) |
| Duplicate prevention | job_id + content hash (SHA-256) |
| Resume | `--resume` / `--resume-from` skip executed rows |
| Load test | 100 jobs, duplicate detection, restart recovery, parallel (10 threads), malformed JSON — all passed (prior env) |
| Cost | $0 |

**Verdict:** KEEP. Complete job lifecycle with fail-closed spend control.

### 7.2 Installed: `lib/kaggle_bridge/kaggle_bridge.py` + tests

| Attribute | Value |
|---|---|
| Function | Submit/poll/fetch/verify Kaggle GPU jobs; fail-closed; token never logged |
| Live test | "hello" CPU job COMPLETE; sha256 verified (prior env) |
| GPU | T4 via Kaggle (30 h/week quota — unverified constraint) |

**Verdict:** KEEP-AS-OPTIONAL. Path to FLUX.2 Klein / future video generation on GPU. Not needed for the Nano Banana stills pilot.

### 7.3 Installed: `lib/checkpoint.py` + checkpoint protocol

| Attribute | Value |
|---|---|
| Per-stage checkpoints | `completed`/`failed`/`awaiting_human`/`in_progress` |
| Human gates | Enforced (`human_approved=True` required for gated stages) |
| History | Superseded checkpoints archived to `projects/<id>/history/` |

**Verdict:** KEEP. Core resumability mechanism.

### 7.4 Missing: workflow orchestrator (Temporal/Prefect/etc.)

| Attribute | Value |
|---|---|
| Status | Not installed; Master Plan §2 principle 9: "metrics first, then new dependencies" |
| Need | None — the agent (Kilo) IS the orchestrator; Python is tools+persistence only |

**Verdict:** Do not add. Agent-driven checkpoint protocol is sufficient; adding an orchestrator violates the minimal-change principle.

---

## 8. License & commercial-use summary

| Tool | License | Commercial use | Notes |
|---|---|---|---|
| OpenMontage repo | AGPL-3.0 | Yes (copyleft) | Derivative works must be AGPL |
| gflow-cli / Nano Banana | Google Flow terms | Owner confirm | 50 credits; per-image cost unknown |
| Kokoro-82M weights | Apache-2.0 | Yes | Training-data provenance partially unknown |
| Remotion | Free (solo) | Yes | Company License not needed |
| HyperFrames | Apache-2.0 | Yes | |
| FFmpeg | GPL/LGPL (--enable-gpl) | Yes | |
| Piper voice | UNKNOWN | NO until confirmed | Refused |
| FFmpeg codecs (aac, libx264) | Various | Yes | Standard |

**Zero-cost gate:** `lib/zero_cost_gate.py` blocks any route with `cost_usd=null` or unknown route. All default-path tools above are $0 except Nano Banana (credit-based, blocked until sample measured) and cloud TTS/images (key-gated).

---

## 9. Codespaces compatibility

| Requirement | Status |
|---|---|
| No GPU needed for default path | Yes (ffmpeg + Kokoro CPU + gflow cloud) |
| ffmpeg binary | Missing — install via apt ($0) |
| Node ≥ 22 + npx | Present (v26.13.0) |
| Python 3.12 | Present (3.12.16) |
| Headless Chrome for gflow | `/opt/google/chrome/chrome` wrapped with `--no-sandbox`; `GFLOW_CLI_HEADLESS=true` |
| No secrets committed | `.env` gitignored; keys as Codespaces secrets |

---

## 10. Final selection matrix

| Capability | Selected tool | Reason |
|---|---|---|
| Image generation (default) | gflow-cli Nano Banana 2.1 | Installed, authenticated, ref_cap=10, `--no-spend`, one observed output |
| Image fallback | FLUX.2 Klein (Kaggle T4) | Proven 78-frame run, Apache-2.0 |
| Narration TTS | Kokoro-82M `af_heart` | $0 local, Apache-2.0 weights, measured |
| Alignment | `lib/audio_sync.py` + Kokoro timestamps (or stable-ts fallback) | Local, zero-cost |
| Subtitles | `tools/subtitle/subtitle_gen.py` | SRT, drift check ≤0.5s |
| Base render | FFmpeg | Must install; concat/encode/subtitle/audio |
| Motion on stills | `lib/motion_engine.py` + FFmpeg filters | Variety-enforced pan/zoom/parallax |
| Motion graphics | Remotion | Present, Free license |
| HTML/GSAP graphics | HyperFrames | Present via npx |
| Job management | `lib/flow_job_manager.py` | Fail-closed, READY_FOR_APPROVAL stop |
| Resumability | `lib/checkpoint.py` | Per-stage gates, history archival |
| Spend control | `lib/zero_cost_gate.py` + MCP Security Proxy | Default-deny, `--no-spend` |
| QC | `tools/qa/qc.py` + `lib/quality_control.py` | Pre-render scene QC + post-render media QC |
| GPU bridge | `lib/kaggle_bridge` | Optional, for FLUX/Kaggle fallback |

**No tool is replaced for fame.** Replacements (Piper → Kokoro, IP-Adapter → gflow character) are justified by observed failure or unverified license. Everything else is kept because it already works or is one install away.
