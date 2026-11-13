# Kilo CLI — Kaggle T4×2 Production Stack Audit

```text
RUN_STAGE: A

You are Kilo CLI acting as a senior ML/DevOps engineer. Execute this assignment autonomously in the current GitHub Codespaces repository. Do not ask the user questions. Do not claim that a test ran unless it actually ran on Kaggle and its logs and output artifacts were retrieved and inspected.

MISSION
Perform a reproducible commercial-readiness and runtime smoke-test audit of the exact AI video-production stack listed below on Kaggle T4 ×2. Codespaces is the control plane only. All GPU/runtime test results must come from Kaggle notebooks running on NVIDIA Tesla T4 GPUs (two if the platform allocates two, otherwise one), each with its own 16 GB-class VRAM. Never treat two GPUs as one 32 GB device. Every model is tested on one GPU at a time, so a single T4 is sufficient.

The target is a monetized English-language scientific/educational YouTube channel.

The production pipeline must use FFmpeg and Python/PIL/OpenCV. Remotion and HyperFrames are prohibited.

SOURCE OF TRUTH
1. Search the repository for the attached decision document named FINAL_PRODUCTION_DECISION (including .md, .docx, .pdf, and similar filename variants).
2. Read it completely. Extract its exact component names, versions, model IDs, source URLs, license decisions, test queue, and acceptance thresholds.
3. Use that document and the explicit component lists in this assignment as the only approved stack.
4. Do not add models, substitute checkpoints, or silently change versions.
5. If the document is absent, continue using the exact component lists and thresholds in this assignment. Record that FINAL_PRODUCTION_DECISION was not found and do not invent any missing thresholds, model IDs, commits, or license terms.
6. Resolve every missing source/revision from the official repository or official model card. If the canonical source cannot be resolved unambiguously, mark that component BLOCKED. Do not guess.

EXECUTION STAGES
Read the `RUN_STAGE:` line at the very top of this assignment and execute ONLY that stage, then stop and report.
- Stage A: Phase 0, Phase 1, Phase 2 (shared helper script and a minimal GPU smoke notebook that only runs the environment snapshot and P2.2 FFmpeg/NVENC test), and Phase 3 license collection (CPU/network only, no GPU). Goal: prove the Codespaces -> Kaggle control plane, the GPU type, the logs retrieval and the licenses. Expected GPU use: well under 1 hour.
- Stage B: P0 (Phase 4) and Phase 6 fixtures.
- Stage C: P1 (Phase 5).
- Stage D: P2.1 (DepthFlow), Phase 8 render integration, Phases 9-12.
Each stage first checks that the previous stage's evidence exists under audit/ and has not been marked BLOCKED for a shared cause. At the end of every stage write audit/STAGE_<letter>_SUMMARY.md (what ran, statuses, GPU hours used, blockers, next stage preconditions) and run Phase 13. Do not start the next stage on your own. If RUN_STAGE is missing or unrecognised, run Stage A.

HARD RULES
- Never use torch.bfloat16, BF16 autocast, or BF16 weights.
- Never install or use FlashAttention 2 (flash-attn, flash_attn, or FA2).
- Use FP16 or FP32 only. Record the actual dtype used by every model component, not merely the requested dtype.
- Do not use quantization to disguise a failed FP16/FP32 test. Do not use NF4, GPTQ, AWQ, GGUF, INT8, or INT4 for this audit.
- Do not use Remotion or HyperFrames.
- Do not modify existing working project files, application code, configuration, lockfiles, AGENTS.md, or user data. Create new audit files only under audit/. Before replacing any existing audit deliverable, copy it into a timestamped backup directory under audit/backups/.
- Run git status --short before making changes. Never reset, clean, stash, or overwrite unrelated user changes.
- Do not claim PASS without a real completed Kaggle run, a retrieved Kaggle log, and the corresponding output artifact.
- License PASS and runtime PASS are separate statuses. Human quality acceptance is a third separate status.
- A component is production-approved only after all three are PASS: commercial license, runtime on Kaggle T4 using FP16/FP32, and human quality acceptance.
- The agent cannot approve its own human-quality output. Mark that gate BLOCKED / NEEDS HUMAN REVIEW until a human has explicitly reviewed it.
- If a component fails, preserve its complete error log and proceed to the next independent component. Do not let one model's dependency conflict corrupt the environment for later tests.
- Stop the GPU test campaign after a critical shared-environment failure: wrong GPU, CUDA/driver failure, Kaggle credentials failure, Kaggle notebook execution failure, no usable notebook internet when downloads are required, or exhausted GPU quota.
- Do not repeatedly retry a failed setup. Permit at most one documented recovery attempt for a transient infrastructure failure. If it fails again, mark BLOCKED and continue only with independent tests that do not depend on that failure.
- Never publish API tokens, credentials, private source files, raw model weights, or unlicensed datasets.
- Do not use results from RTX 4090, A100, H100, P100, or any other accelerator as proof of T4 compatibility.
- Each T4 must be measured separately. Never combine their VRAM figures.

STATUS DEFINITIONS
Use these exact status values:
- PASS: the specified test ran successfully and all stated automatic criteria passed.
- FAIL: the test ran and a stated criterion failed, or commercial weight licensing could not be established.
- BLOCKED: the test could not be performed because of a documented external prerequisite, missing credential, missing source, quota, or infrastructure blocker.
- NOT TESTED: the test was deliberately not run; state why.
- NEEDS HUMAN REVIEW: automatic checks completed, but a person must evaluate subjective quality.
For each component, report independent fields: license_status, runtime_status, automatic_quality_status, human_review_status, and production_status. Never collapse these into one ambiguous PASS.

RED LIST — NEVER DOWNLOAD OR RUN THESE COMPONENTS
The following are explicitly prohibited for this audit. Do not clone their repositories for inference, download their checkpoints, install their packages, or execute their inference code. If an existing cache contains them, do not load or run them; do not delete user-owned files. Record any discovery as NOT USED.
- FLUX.2 9B/dev
- LTX-2 and LTX-2.5
- Fish Audio
- Breeze TTS 2
- IndexTTS-2
- Ming-3.0-TTS
- Qwen3-TTS (BF16/FlashAttention 2 path)
- SwinIR and base RIFE weights (checkpoint license not approved)
- Wan 14B and Wan2.2 large
- SeedVR2
- FlashVSR
- Chatterbox
- Real-ESRGAN x2plus
Do not replace a prohibited item with a similarly named model or checkpoint. Do not add any other model not named in the approved P0/P1/P2 list.

PHASE 0 — REPOSITORY INSPECTION AND AUDIT WORKSPACE

0.1 Inspect the repository. Run:
    pwd
    git status --short
    git rev-parse --show-toplevel
    find . -maxdepth 5 -iname '*FINAL_PRODUCTION_DECISION*' -o -iname '*production*decision*'
Read the decision file and extract the approved test matrix. Record its path and SHA256 in audit/PRODUCTION_SMOKE_TEST_REPORT.md.

0.2 Prepare directories without modifying existing project files. Create:
    audit/
    audit/config/
    audit/scripts/
    audit/kaggle/
    audit/kaggle/p0/
    audit/kaggle/p1/
    audit/kaggle/p2/
    audit/logs/
    audit/logs/codespaces/
    audit/logs/kaggle/
    audit/licenses/
    audit/provenance/
    audit/results/
    audit/previews/
    audit/backups/
If a required output file already exists, back it up first into audit/backups/<UTC_TIMESTAMP>/.

0.3 Record the Codespaces control-plane environment to audit/logs/codespaces/codespaces_environment.txt:
    date -u
    uname -a
    python --version
    python -m pip --version
    git --version
    df -h
    free -h
    nvidia-smi
If nvidia-smi is unavailable in Codespaces, record that fact. Do not treat Codespaces GPU information as Kaggle evidence.

0.4 Install or verify Kaggle CLI. Check:
    kaggle --version
    kaggle kernels push --help
    kaggle kernels status --help
    kaggle kernels output --help
    kaggle datasets init --help
    kaggle datasets create --help
    kaggle datasets version --help
If Kaggle CLI is missing, install the current official kaggle package in an isolated audit virtual environment. Record exact package version and installation log. Do not change the repository's existing Python environment.

0.5 Verify Kaggle credentials without exposing them. Accept credential methods documented by the installed Kaggle CLI, including its supported token environment variable or standard ~/.kaggle/ credential file. Check only whether credentials exist and whether permissions are safe. Never print token values, secret JSON, or credential environment variables. If using ~/.kaggle/kaggle.json, check file permissions and set them to 600 if necessary. Run an authenticated minimal API request, e.g.:
    kaggle datasets list -s titanic -p 1
Save output and exit code. If credentials are absent/invalid, STOP Kaggle execution and report exactly what is missing and where the user must configure it. Do not fabricate a kernel ID, notebook run, log, or result.

PHASE 1 — OFFICIAL KAGGLE LIMITS AND NOTEBOOK CONFIGURATION

1.1 Read and preserve current official documentation:
    https://www.kaggle.com/docs/notebooks
    https://www.kaggle.com/docs/efficient-gpu-usage
Save retrieved text or stable local snapshots where possible under audit/provenance/. Record UTC retrieval time, exact URL, short verbatim quotations supporting each limit, reported T4 ×2 configuration, CPU/RAM, session duration, autosaved /kaggle/working capacity, weekly GPU quota statement, and account/availability caveats. Do not copy old limits from the decision document as current facts without checking the official page. If documentation and actual runtime differ, report both.

1.2 Build Kaggle kernel metadata using the installed CLI's actual schema. Run:
    kaggle kernels init -p audit/kaggle/p0
Inspect generated kernel-metadata.json and:
    https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md
Set enable_gpu=true, enable_internet=true, request NVIDIA Tesla T4 (×2 if the currently documented schema offers it, otherwise a single T4; record which was obtained), keep the kernel private, and use valid metadata types. The current schema commonly uses machine_shape with NvidiaTeslaT4 for T4 ×2. Add an accelerator field only if the installed CLI/API schema explicitly supports it. Do not insert unsupported keys. Do not invent a Kaggle username or kernel slug; determine authenticated identity from supported CLI/configuration without printing credentials. Save metadata and SHA256.

1.3 Kaggle execution from Codespaces. For every notebook, create a dedicated directory containing notebook, scripts, and kernel-metadata.json. Push using:
    kaggle kernels push -p <KERNEL_DIRECTORY>
Save complete stdout/stderr and exit code. Obtain exact kernel ID from metadata or successful response. Check:
    kaggle kernels status <OWNER>/<KERNEL_SLUG>
Poll at a controlled interval until completion/failure, but stop before platform session limits or GPU budget would be exceeded. Inspect `kaggle kernels logs --help` before using `kaggle kernels logs`; do not assume that subcommand exists. Retrieve actual output using:
    kaggle kernels output <OWNER>/<KERNEL_SLUG> -p audit/logs/kaggle/<KERNEL_SLUG> -o
Save status, logs, downloaded files, output manifest, and kernel URL. Verify downloaded files by existence, size, SHA256, and parseability. A successful push is not proof of execution; completed status is not proof that expected artifacts exist.

1.4 Kaggle datasets workflow. Use `kaggle datasets create` / `kaggle datasets version` only when persistent artifact storage is needed or kernel output retrieval is insufficient. Never upload model weights or private data. For a new private audit dataset:
    kaggle datasets init -p <DATASET_DIRECTORY>
    kaggle datasets create -p <DATASET_DIRECTORY>
For an existing dataset:
    kaggle datasets version -p <DATASET_DIRECTORY> -m "<UTC timestamp> audit evidence update"
Inspect dataset-metadata.json first; use authenticated owner; set privacy per supported schema; include only compact logs, JSON, license snapshots, checksums, permitted previews. Never exceed 20 GB in /kaggle/working. Save dataset ID/version/status/CLI logs/URL. Search for existing dataset first; do not create duplicates. If dataset persistence is unavailable, use kernel output retrieval and document that no dataset was used.

PHASE 2 — SHARED KAGGLE ENVIRONMENT SNAPSHOT

Create one shared helper script: audit/scripts/kaggle_environment_snapshot.py. Copy and execute exactly the same helper in every Kaggle notebook. Do not create notebook-specific variants.

For every notebook, save an environment snapshot before installation and after tests. Capture UTC timestamp; Python version/executable; pip freeze; torch.__version__; torch.version.cuda; torch.cuda.is_available(); torch.cuda.device_count(); per-device index/name/total memory/compute capability/free memory; full nvidia-smi output; GPU name/memory/driver/utilization/process memory; ffmpeg -version; ffmpeg -hide_banner -encoders; ffprobe -version; df -h /kaggle/working; df -h /kaggle/temp if present; free -h; CPU count; network check to an official package/model host with short timeout; free space and output-directory size. Save raw command output and structured JSON. Never silently omit a failed command.

2.1 Verify accelerator. Assert that every visible CUDA device is an NVIDIA Tesla T4 and that torch.cuda.device_count() is 1 or 2. Record the actual count, and per-device name, total memory and compute capability. Never treat memory as pooled. A single T4 is acceptable: continue the campaign on it and record `t4_count` in the environment JSON. If any visible GPU is not a T4, or no CUDA device is visible, mark all T4-specific tests BLOCKED and stop GPU testing. CPU-only tests may run only if they do not consume reserved GPU budget and are labelled CPU-only.

2.2 For every model test, explicitly select one GPU with CUDA_VISIBLE_DEVICES or torch.cuda.set_device. Run one model instance on one GPU at a time unless official inference explicitly requires independent distributed workers. Do not use model/tensor parallelism to combine the two 16 GB devices. Reset CUDA peak statistics before inference. Record torch.cuda.max_memory_allocated, max_memory_reserved, nvidia-smi memory, host RAM high-water mark where measurable, wall time, GPU-active time where measurable, device index/name.

2.3 Dependency isolation. Do not install all models into one shared Python environment. Use a separate environment or isolated subprocess environment for each component or compatible group. Reuse preinstalled PyTorch/CUDA only when compatible. Use virtual environments with system site packages only when they do not overwrite the base environment. Install dependencies from official source and exact revision. Never upgrade/downgrade PyTorch/CUDA/torchvision/torchaudio blindly. If dependencies conflict, preserve logs, mark component BLOCKED, and move to an independent environment. Record commands, versions, pip freeze, exit code.

2.4 Resource constraints. /kaggle/working must never exceed 20 GB. Put temporary caches/scratch outside /kaggle/working only after verifying the path and free space; do not assume /kaggle/temp exists or has a particular capacity. Download/test one large model at a time. After each component, remove only that component's temporary cache and generated temporary data; preserve audit evidence/previews. Run gc.collect() and torch.cuda.empty_cache(). Check space before downloads; mark BLOCKED rather than filling disk. Record disk use before/after every component.

2.5 GPU-hour budget. Read current account quota from Kaggle account interface or officially supported source if available. Use official documentation as reference, not guarantee of remaining quota. Use 30 GPU-hours/week as conservative planning ceiling unless account shows smaller quota; do not assume 30 hours remain. Reserve safety margin and stop new GPU tests at estimated 24 GPU-hours or smaller actual remaining quota. After each notebook record allocated GPU wall time, number of allocated GPUs, GPU-active time if measurable, and conservative upper-bound estimate = elapsed GPU-enabled wall time × number of allocated GPUs. Label this as estimate, not official quota measurement. Record visible quota evidence. Never exceed actual quota.

PHASE 3 — LICENSE AND PROVENANCE AUDIT

For every component and separately distributed weight/subcomponent:
1. Resolve canonical official code repository and exact official model/checkpoint ID or author-provided checkpoint URL.
2. Resolve permanent Git commit SHA or immutable Hugging Face revision SHA.
3. Record release/version string.
4. Download/save code LICENSE at pinned revision.
5. Save full model card and complete weight license, including linked/separate license documents.
6. Record original URL, exact revision, retrieval date, SHA256 of each saved license/card file.
7. After downloading weights, calculate SHA256 for every weight file.
8. Save PROVENANCE.json with source URLs, revisions, filenames, file sizes, license identifiers, retrieval timestamps, SHA256 values.
Use:
    audit/licenses/<component>/LICENSE-code.txt
    audit/licenses/<component>/LICENSE-weights.txt
    audit/licenses/<component>/MODEL_CARD.md
    audit/licenses/<component>/PROVENANCE.json
    audit/licenses/<component>/SHA256SUMS.txt

For diffusion/video models, inspect licenses/revisions for transformer/UNet, VAE, text encoder, tokenizer, vocoder, and auxiliary weights. A permissive repository license does not prove every checkpoint is commercially usable.

License rules: commercial-license PASS requires explicit permission for commercial use of exact code and exact downloaded weights, with satisfiable obligations. If weight license cannot be found, set license status FAIL for monetization. Do not infer weight license from code LICENSE or model-card badge. Record revenue/MAU/written-permission restrictions; do not call them unconditional clearance. Legal ambiguity = BLOCKED / LEGAL REVIEW.

Mandatory special checks:
A. DeepFilterNet3: manually open official repository; inspect LICENSE, README, issue #697, commit 7b14b89. Resolve conflicting license links and exact ONNX asset provenance. Save issue, commit diff, exact ONNX checkpoint license, asset URL, SHA256. If ONNX commercial license is not explicit, license FAIL.
B. LTX-Video 2B v0.9.5: model card has `license: other`. Save card unchanged and full underlying license governing this exact checkpoint and all required subcomponents. `other` is not proof. PASS only with explicit commercial permission and satisfiable conditions.
C. SDXL Base 1.0: read/save complete official card and license. Do not assume unrestricted commercial use. If eligibility cannot be established, mark legal review required; no production PASS.
D. Real-ESRGAN x4plus: verify BSD-3-Clause code license and, separately, the license of the exact `RealESRGAN_x4plus.pth` weight file from the official xinntao/Real-ESRGAN release. The code license does not prove the weight license: search the repository README, release notes and issues for an explicit statement and save it. Pin tag/revision and SHA256. Do not substitute `amd/realesrgan-x4plus` or another mirror.
E. Practical-RIFE 4.25: verify `hzwer/Practical-RIFE` MIT code license and exact 4.25 archive referenced by maintainer. Save maintainer statement that linked models use same MIT license. Save archive and SHA256. Do not replace with base RIFE weights.
F. Music/SFX: for each YouTube Audio Library track, save title, author, source URL/ID, download date, license field, attribution requirement/text. For each Sonniss file, save bundle/file/download date/license version. Apply Sonniss GDC Bundle License v2.0 effective 2026-08-27 to relevant downloads; check older downloads against applicable terms. No standalone redistribution. No use of Sonniss sounds for AI training/development/improvement.

PHASE 4 — PRIORITY P0: ONE KAGGLE NOTEBOOK PER COMPONENT

Create and execute five separate P0 Kaggle notebooks, one per component, each in its own directory audit/kaggle/p0/<component>/ with its own kernel-metadata.json and slug. Run them sequentially, never in parallel on one account unless the quota allows, and never reuse a failed notebook's environment:
1. CosyVoice 3 — Fun-CosyVoice3-0.5B-2512.
2. LTX-Video 2B v0.9.5.
3. FLUX.2 klein 4B.
4. Practical-RIFE 4.25.
5. Real-ESRGAN x4plus.
Run the shared environment snapshot before installation in every notebook. A component failure must not prevent the next independent notebook. A shared T4/CUDA/credentials/quota failure stops the remaining GPU notebooks.

P0.1 COSYVOICE 3 — Fun-CosyVoice3-0.5B-2512
Source: official `https://github.com/FunAudioLLM/CosyVoice`; resolve exact official model ID, immutable revision, and required subcomponents from decision document/official repository. Never guess a replacement.
Install only official repo/dependencies at resolved commit. No FA2/BF16. Use FP16 on one T4. FP32 only if official supported path requires it; report FP16 requirement not met. Prefer supported PyTorch SDPA/eager attention. If BF16/FA2 is required, runtime FAIL.
Input: fixed English scientific script from Phase 6, approximately 10 minutes of generated speech, with the reference/prompt voice defined in Phase 6.5; chunk only as official interface requires. Preserve text, chunk boundaries, voice config, seed if supported, WAV.
Run official inference entry point after discovering exact CLI/API from pinned README/examples. Measure synthesis wall time, generated duration, RTF = synthesis seconds/audio seconds, dtype, attention backend, peak allocated/reserved VRAM, host RAM, sample rate, channels, clipping, NaN/Inf, WAV validity.
PASS: no OOM/NaN/Inf/BF16/FA2; RTF <= 2.0; peak VRAM < 15 GB; valid decodable WAV. FAIL: RTF > 2.0, peak VRAM >=15 GB, OOM/crash/invalid audio/BF16/FA2. Assess license separately.

P0.2 LTX-VIDEO 2B v0.9.5
Source: exact official repo/model ID and v0.9.5 checkpoint revision from decision document/official card. Save actual license text because card field is `other`. Pin every required VAE, text encoder, tokenizer, auxiliary revision. Never substitute LTX-2/2.5 or another release.
Run official inference path with FP16, or FP32 only if documented. Use supported non-FA2 backend. If BF16/FA2 mandatory with no supported FP16/FP32 path, runtime FAIL.
Input: fixed video prompt and seed 424242; one short 512×512, 49-frame clip, or nearest documented valid frame multiple if architecture requires another; record actual dimensions/frames/duration. Do not silently reduce after OOM; one separate smaller diagnostic retry may be reported but cannot replace primary result.
Measure dtype/backend, peak VRAM/RAM, inference time, seconds/frame, output FPS, frame count/resolution, CPU offload, decode integrity, black/frozen frames.
PASS: exact v0.9.5 generates valid clip on one T4 in FP16/FP32 without BF16/FA2/OOM/NaN/Inf/corrupt frames; exact checkpoint and all subcomponents have explicit commercial licenses. Do not invent speed threshold. FAIL: no supported path, OOM, invalid output, or missing license.

P0.3 FLUX.2 KLEIN 4B
Source: exact official 4B model ID/revision from decision document and official card. Do not substitute FLUX.2 9B/dev, FLUX 3 Klein, or any other model. Pin all encoders/tokenizers/VAE/auxiliary weights.
Input: three exact shared image prompts/seeds from Phase 6; three 512×512 images, one at a time; same prompts, seeds, dimensions, and count as SDXL. Save metadata.
Use official path; explicitly set FP16/FP32; no FA2. If BF16/FA2 required and no supported FP16/FP32 path, runtime FAIL.
Measure actual dtype/backend, peak VRAM/RAM, seconds/image, dimensions, decode integrity, offload/tiling.
PASS: all three valid 512×512 images on one T4 without OOM/NaN/Inf/BF16/FA2 and exact commercial licenses for all weights. Save previews; human visual review remains separate. FAIL: unsupported path/OOM/corrupt output/missing license.

P0.4 PRACTICAL-RIFE 4.25
Source: `https://github.com/hzwer/Practical-RIFE`; resolve official repo commit and exact maintainer-linked 4.25 archive. Do not use base RIFE or substitute. Save archive and SHA256.
Input: deterministic 30-second 24 FPS 640×360 test clip with moving geometry and scene transitions. Create a 48 FPS ground-truth reference first, then downsample every second frame to 24 FPS. Preserve seed and ground truth.
Run maintainer-documented 4.25 inference. Interpolate 24 to 48 FPS. FP16 if supported else FP32. Measure VRAM/RAM, time, seconds/interpolated frame, frame count/FPS, decode/missing frames, NaN/Inf. Compare intermediate frames to deterministic ground truth with a documented metric; report metric without inventing a threshold. Save contact sheet, especially scene cuts.
PASS: exact 4.25 weights/provenance, valid 48 FPS output, no OOM/crash/missing/corrupt frames/NaN/Inf. Human ghosting/artifact review separate. FAIL: wrong/unlicensed weights, broken archive, runtime failure, OOM, corrupt output, severe objective reconstruction failure.

P0.5 REAL-ESRGAN X4PLUS
Source: `https://github.com/xinntao/Real-ESRGAN`; exact file `RealESRGAN_x4plus.pth` taken from the official xinntao/Real-ESRGAN GitHub release assets. Any other mirror or repackaged checkpoint (including `amd/realesrgan-x4plus`, named in the decision document but not independently verified) may be recorded only as a secondary comparison, never as the tested checkpoint, unless its own card gives explicit commercial permission. Save code LICENSE, the release notes/asset URL, any license statement that covers this specific weight file, revision/tag and SHA256. If no explicit permission for this exact weight file can be found, license_status = FAIL.
Input: ten deterministic 256×256 RGB frames, batch size 1, scale ×4.
Run documented x4plus inference. Tile mode only if necessary, record tile/overlap. FP16 if supported else FP32.
Measure VRAM/RAM, seconds/image, dimensions (must be 1024×1024), read integrity, NaN/Inf/clipping, checksums. Save contact sheets.
PASS: all ten files valid 1024×1024, exact provenance and commercial license, no OOM/crash/NaN/Inf/corruption. Human perceptual review separate. FAIL: wrong/missing checkpoint/license, OOM, corrupt files, wrong dimensions.

PHASE 5 — PRIORITY P1 COMPONENTS

Run P1 after P0 completes or independent failures are recorded. Use one separate notebook and environment per component, as in P0. Use same environment snapshot helper.

P1.1 KOKORO 82M — VOICE BASELINE
Resolve exact official repo/checkpoint corresponding to Kokoro 82M / `kokoro-v1_0.pth` from decision doc. Pin revision and SHA256. Verify code/weight licenses separately.
Use same 10-minute science script as CosyVoice. Generate Kokoro baseline before comparison. Keep text, voice, chunking, sample rate and comparable settings fixed. Use supported FP16; if unsupported but FP32 supported, report FP16 not verified. No BF16/FA2.
Measure dtype/device, peak VRAM/RAM, RTF/time, audio integrity/clipping/NaN/Inf, pronunciation review assets. PASS: valid 10-minute output without OOM/crash/NaN/Inf/license mismatch. Report measured speed; do not invent threshold. Human quality pending.

P1.2 WHISPER LARGE-V3-TURBO + JIWER
Resolve official `openai/whisper-large-v3-turbo` checkpoint and immutable revision. Record code and weight terms separately. Resolve actual `jiwer` version; do not guess.
Use same labelled English ASR dataset as Parakeet, preferably existing licensed corpus; otherwise retrieve a small officially licensed benchmark and pin revision/license. Target 30–60 minutes labelled speech. Also score Phase 6 scientific-term sample separately. Never call synthetic TTS output a human-recorded benchmark.
Use exact checkpoint, FP16/FP32, non-FA2 backend. Transcribe same audio as Parakeet. Use jiwer for normalized WER/CER. Identical normalization for both models. Score scientific terms separately with documented aliases/rules.
Measure overall WER/CER, scientific-term WER/per-term result, number/unit errors, proper nouns, runtime/RTF, VRAM/RAM, dtype/backend, timestamp drift when available.
PASS: overall clean-speech WER <=5%; scientific-term results separately reported; valid output; no BF16/FA2/runtime failure; commercial weight license. FAIL: WER >5%, unsupported path/OOM/invalid output/missing commercial weight license.

P1.3 PARAKEET TDT 0.6B V3
Resolve official NVIDIA NeMo source and exact Parakeet TDT 0.6B v3 checkpoint from decision file. Pin model revision and NeMo dependency versions. Verify CC-BY-4.0 checkpoint terms and required component licenses. No substitute.
Use same 30–60 minute labelled set and science-term sample as Whisper. Install NeMo in isolated environment; FP16/FP32 only; no BF16/FA2. If dependency setup requires incompatible global PyTorch/CUDA changes, preserve log and mark BLOCKED.
Measure WER/CER, term/per-term errors, proper nouns/units, runtime/RTF, VRAM/RAM, dtype/backend, dependency conflicts.
PASS: same test set completed on T4 FP16/FP32 without BF16/FA2/OOM; WER <=5%; license PASS. FAIL: setup/runtime failure, unsupported path, OOM, WER >5%, missing license.

P1.4 DEEPFILTERNET3
Source: `https://github.com/Rikorose/DeepFilterNet`; resolve exact release/commit and ONNX checkpoint from decision file. Complete Phase 3 license checks.
Input: deterministic 30-second 48 kHz clean signal plus controlled seeded noise; save clean reference, noisy input, parameters.
Run exact DeepFilterNet3 ONNX path. Record CUDA vs CPU provider; do not call CPU inference GPU. FP16/FP32 only as supported by graph/provider.
Measure input/output duration, start/end drift in ms, sample rate/channels, NaN/Inf/clipping, file integrity, peak VRAM/RAM, runtime, objective measurements if available.
PASS: exact explicit commercial ONNX license; valid output without NaN/Inf/corruption; duration drift <=30 ms; provider/dtype/performance recorded. FAIL: license missing/ambiguous, drift >30 ms, invalid output/runtime error.

P1.5 WAN2.1 T2V 1.3B
Resolve exact official Wan2.1 T2V 1.3B model ID/revision and required subcomponents from decision file. Do not use Wan 14B/Wan2.2 large. Save all weight licenses.
Input: same fixed prompt/seed as LTX; one short 480p-class clip, 49 frames or documented valid multiple; record actual dimensions/frames.
Run official inference FP16, or FP32 if documented/necessary; no BF16/FA2. Use CPU offload only if officially supported and report it.
Measure dtype/backend, VRAM/RAM, generation time/seconds per frame, size/FPS/frame count, decode, black/frozen frames, NaN/Inf.
PASS: valid T4 FP16/FP32 video with no BF16/FA2/OOM/corrupt frames and commercial licenses; no invented speed threshold. FAIL: runtime/backend/OOM/output/license failure.

P1.6 DEPTH ANYTHING V2 SMALL
Resolve exact official repo/model ID/revision. Verify Apache-2.0 code and checkpoint separately.
Input: ten fixed 1024×1024 RGB images.
Run official Small inference on one T4 using FP16/FP32.
Measure peak VRAM/RAM, total time/images per minute, output dimensions/depth range/finite values/integrity, preprocessing.
PASS: ten valid depth maps, no OOM/NaN/Inf/corruption, peak VRAM <8 GB, commercial license. FAIL: peak VRAM >=8 GB/OOM/invalid output/license mismatch.

P1.7 VIDEO DEPTH ANYTHING SMALL
Resolve exact official repo/model ID/revision. Verify Apache-2.0 code/checkpoint separately.
Input: deterministic 30-second 24 FPS 480p-class video.
Run official inference on one T4 FP16/FP32. Measure peak VRAM/RAM, time/FPS/seconds per frame, output dimensions/frame count, temporal continuity/flicker metrics where available, NaN/Inf. Save preview/contact sheet.
PASS: complete valid sequence without OOM/NaN/Inf/missing frames/corruption and commercial license. Report throughput; do not invent FPS threshold. FAIL: OOM/invalid frames/NaN/Inf/corruption/license failure.

P1.8 SDXL BASE 1.0
Resolve exact official SDXL Base 1.0 ID/revision. Save complete official model card/license. Verify all text encoders/tokenizers/VAE/auxiliary checkpoints.
Input: the same three prompts, seeds, dimensions and count as FLUX; three 512×512 images.
Run official inference FP16/FP32, no BF16/FA2. Measure actual dtype/backend, peak VRAM/RAM, time/image, dimensions, decode, NaN/Inf, offload.
PASS: three valid T4 images FP16/FP32 without OOM/BF16/FA2/corruption and exact commercial permission for model/subcomponents. Human visual review separate. FAIL: unsupported path/OOM/corrupt output/unresolved commercial terms.

PHASE 6 — FIXED TEST CORPORA AND PROMPTS

Create fixtures deterministically under audit/config/ and copy them to Kaggle inputs. Save creation code, seed, SHA256, and licenses.

6.1 Scientific speech script. Create a natural English science-education script sufficient for approximately 10 minutes of speech. Include scientific vocabulary, Latin biological names, scientists/space missions, abbreviations, decimals/dates/percentages/math, units/conversions, and a long multi-clause sentence. Include these exact examples:
- James Webb Space Telescope
- spectroscopy
- exoplanet
- gravitational waves
- mitochondrion
- Homo sapiens
- Escherichia coli
- photosynthesis
- 9.81 meters per second squared
- 37 degrees Celsius
- 1.5 × 10^8 kilometers
- 3.0 × 10^8 meters per second
Also include additional terms/Latin names. Save `audit/config/science_voice_script.txt` and `audit/config/science_terms.json`. JSON must include canonical term, accepted normalized variants, exact token span/rule for term-specific scoring. Do not normalize away term errors.

6.2 ASR reference corpus. Use licensed labelled data already in repository if available. Otherwise retrieve small official clean-speech benchmark with exact revision/license and reference transcripts. Target 30–60 min for main Whisper/Parakeet comparison. Score science-term sample separately and label as synthetic if generated by TTS. Save reference text/audio provenance. Never report synthetic TTS WER as human-recorded benchmark WER.

6.3 Identical image prompts for FLUX and SDXL. Use unchanged:
PROMPT 1: "A scientifically accurate, highly detailed educational cutaway illustration of a mitochondrion, showing the outer membrane, inner membrane, cristae, matrix, and ATP synthase complexes, clean studio lighting, clear scientific composition, no labels, no text, no watermark."
PROMPT 2: "A scientifically grounded visualization of the James Webb Space Telescope observing a distant exoplanet, realistic engineering details, accurate telescope proportions, deep-space background, educational documentary visual style, no labels, no text, no watermark."
PROMPT 3: "A precise scientific visualization of a gravitational-wave observatory with two perpendicular interferometer arms, laser beam paths, mirrors, realistic facility scale, clean explanatory composition, no labels, no text, no watermark."
Use seeds 424242, 202607, 271828; output 512×512, one per prompt/seed. Keep pairing identical for both models. Do not change prompts/seeds/count.

6.4 Video prompt for LTX and Wan2.1. Use unchanged:
"Create a short, scientifically grounded educational documentary shot of a spacecraft approaching a distant exoplanet. Show a slow continuous camera movement, stable object geometry, physically plausible lighting, realistic space-science visual style, no text, no labels, no watermark, no abrupt scene changes."
Use seed 424242 if supported. Use fixed short-clip configuration specified in component test. Save actual dimensions, frames, FPS, guidance, scheduler.

6.5 Reference voice for cloning/prompted TTS (CosyVoice 3). Use only (a) a reference recording made by the user or the agent-generated synthetic audio from an already-approved permissively licensed voice (e.g. a Kokoro voice, with its license recorded), or (b) a CC0 / CC-BY recording with a saved license, author, source URL and retrieval date. Never use a recording of a real person without documented permission, never a voice taken from YouTube, audiobooks or films. Save the file, its transcript, SHA256 and license evidence under audit/licenses/cosyvoice3/reference_voice/. If no cleared reference exists, mark the cloning test BLOCKED and test only built-in speaker/instruct modes if the official interface provides them.

PHASE 7 — PRIORITY P2

P2.1 DEPTHFLOW HEADLESS OPENGL/EGL
Resolve exact DepthFlow repository/version/license from decision file; do not substitute. Read complete license and obligations. Record AGPL-3.0 if confirmed; do not treat as unrestricted permissive. If legal compliance not established, license review BLOCKED. Resolve exact CLI from pinned source/official instructions; do not guess flags.
Input: one 1280×720 approved test image; render five seconds 1280×720 30 FPS parallax clip.
Run documented headless EGL/OpenGL path. Record supported environment variables/backend. Do not claim headless if X server/interactive desktop needed.
Measure EGL/OpenGL init, renderer/backend, RAM/VRAM, time/FPS/frame count, integrity, black/frozen frames, decode errors.
PASS: headless without interactive display, valid five-second output, commercial legal clearance. FAIL: headless/render/license failure.

P2.2 FFMPEG NVENC
Record exact Kaggle FFmpeg build/version/configuration/encoder list. GPU availability does not imply NVENC.
Input: deterministic 10-second 1920×1080 30 FPS testsrc2 with 48 kHz tone.
Run separate software encode using libx264. If encoder list includes h264_nvenc, inspect `ffmpeg -h encoder=h264_nvenc` and run separate hardware encode using a documented supported preset; do not guess options.
Measure encoder presence, exit code, wall time, CPU/GPU utilization if available, file size, ffprobe codec/dimensions/FPS/frames/duration/pixel format, complete decode test `ffmpeg -v error -i <output> -f null -`.
libx264 PASS: present, valid decodable 10-second 1920×1080 30 FPS output. NVENC PASS: present and real encode completes on Kaggle T4 with valid decodable output and actual GPU recorded. NVENC FAIL: missing encoder/driver/CUDA init/encode/output error. libx264 PASS does not imply NVENC PASS.

PHASE 8 — RENDER INTEGRATION TEST
Use FFmpeg + Python/PIL/OpenCV and Manim CE 0.22.1. No Remotion/HyperFrames.

8.1 Manim. Resolve/pin official Manim Community Edition 0.22.1 release/source. Save MIT license/version. Read actual CLI help. Render deterministic scientific formula/diagram at 1920×1080 30 FPS. Save source, command, logs, video; validate with ffprobe and full decode.

8.2 Audio. Use one commercially cleared SFX and one commercially cleared music track from YouTube Audio Library or Sonniss GDC. Prefer already approved assets; otherwise use official source and preserve terms/attribution. No unlicensed substitute. If no valid assets, mark integration BLOCKED. Apply track attribution. Do not use Sonniss source sounds for AI training/development/improvement.

8.3 Build final 15-second video: 1920×1080, 30 FPS, English narration from a voice candidate that passed runtime; one Manim diagram; one SFX; one cleared music track; FFmpeg-only assembly; Python/PIL/OpenCV overlays; matching .srt. If no voice passed runtime, integration cannot PASS; diagnostic output must be labelled non-production preview.

8.4 Two-pass audio loudnorm. Pass 1 analyze mixed audio; save JSON loudness report (integrated loudness, true peak, range, threshold, offset). Pass 2 apply measured values. Target -16 LUFS ±1.5 LU; true peak <= -1.5 dBTP. Validate final with FFmpeg loudness/EBU R128 analysis. Save commands/output.

8.5 Synchronization. Use one timeline. Measure narration/subtitle start/end offsets using actual timestamps. Max measured subtitle/audio sync error <=0.1 seconds. Validate SRT syntax, timestamp ordering, cue durations, unintended overlaps. Do not claim tolerance unless measured.

8.6 Media validation. For every generated video run ffprobe and save JSON; complete FFmpeg decode; blackdetect; freezedetect. Record duration, resolution, FPS, frames, video/audio codecs, sample rate, channels, pixel format. Preserve detections. Save contact sheets and audio previews. State: "Human visual/audio quality review required."

8.7 Render automatic PASS only when valid 15-second 1920×1080 30 FPS video, audio and subtitles exist, ffprobe/decode pass, loudness is -17.5 to -14.5 LUFS, true peak <= -1.5 dBTP, measured sync <=0.1 s, one Manim diagram, one licensed SFX, one licensed music track, rights/attribution saved, and no Remotion/HyperFrames dependency. Otherwise report failed condition. Human approval is separate.

PHASE 9 — LOGGING AND EVIDENCE

For every component record exact source URL, commit/revision, checkpoint filenames/SHA256, code/weight license evidence paths, install command/log, test inputs/SHA256, inference command/config, UTC start/end, Kaggle kernel ID/version/URL, Kaggle status, notebook stdout/stderr, exit code, actual dtype/backend, GPU index/name, peak VRAM allocated/reserved, host RAM peak, runtime/RTF/FPS/seconds/frame, output paths/sizes/SHA256, media validation, independent statuses, traceback/next action.

Use one JSONL event log per notebook and component-specific logs. Preserve full errors. On exception: flush logs/traceback; save environment and partial outputs; set FAIL/BLOCKED accurately; delete only component cache; gc.collect(); torch.cuda.empty_cache(); continue next independent block. For interrupted notebook, retrieve available logs/outputs before deciding whether an individual test completed.

PHASE 10 — REPORTS AND RESULT SCHEMA

Create:
    audit/PRODUCTION_SMOKE_TEST_REPORT.md
    audit/results.json
    audit/provenance/source_manifest.json
    audit/provenance/kaggle_environment.json
    audit/provenance/kaggle_quota.json
    audit/results/component_results.json
    audit/previews/human_review_index.md
    audit/previews/human_review_checklist.md

Markdown report sections:
1. Executive summary.
2. Date, repo revision, decision-document provenance.
3. Kaggle CLI auth/execution evidence.
4. Official limits, quoted documentation, actual runtime comparison.
5. Verified T4×2 snapshot proving separate devices.
6. GPU budget and consumption per notebook.
7. License audit/missing/conditional permissions.
8. Per-component results.
9. P0 results.
10. P1 results.
11. P2 results.
12. Integrated render results.
13. Failures and preserved logs.
14. "What Must Not Be Considered Confirmed".
15. "Recommended Stack Based on Test Results".
16. "Human Review Required".
17. Production final gate.
18. Reproduction commands.
19. Output artifact inventory.

Required component table columns:
Component | Priority | Exact version/revision | Code license | Weight license | Actual dtype | Attention backend | GPU | Peak VRAM | Runtime / RTF / FPS | License status | Runtime status | Human review | Final status | Kaggle log link
Use UNKNOWN/NOT MEASURED rather than blank cells and explain why.

Create valid machine-readable `audit/results.json` with at least:
{
  "audit_timestamp_utc": "...",
  "repository_commit": "...",
  "decision_document": {"path": "...", "sha256": "...", "found": true},
  "kaggle": {
    "cli_version": "...",
    "account_identity_redacted": "...",
    "kernel_ids": [],
    "official_limits_source_urls": [],
    "actual_gpu_devices": [],
    "weekly_quota_hours": null,
    "estimated_gpu_hours_used": null,
    "notebook_runs": []
  },
  "components": [],
  "render_integration": {},
  "recommendations": {},
  "unconfirmed_claims": [],
  "human_review_items": []
}
Each component object must include name, priority, version, source_url, revision, checkpoint_files, checkpoint_sha256, code_license, weight_license, license_evidence, license_status, dtype, attention_backend, gpu_index, gpu_name, peak_vram_allocated_mb, peak_vram_reserved_mb, peak_ram_mb, runtime_seconds, rtf, fps, automatic_quality_status, human_review_status, runtime_status, production_status, input_artifacts, output_artifacts, log_path, kaggle_kernel_url, errors. Use actual values or null/UNKNOWN; never present estimates as measurements.

Recommended stack: recommend winner and backup/candidate for Voice, Video, Animation, Render, using only approved stack. A license PASS without runtime PASS is not production-approved; runtime PASS with license FAIL is not production-approved; both passes with human review pending is not production-approved. If no component passes all three, state "NO PRODUCTION-APPROVED WINNER". Best measured candidate/fallback may be named but clearly labelled candidate. Do not invent video winner. For Render prefer validated libx264 unless NVENC separately passes. State conditions before production settings change.

PHASE 11 — HUMAN REVIEW PACKAGE

The user works from a phone. Produce a concise review index and checklist without asking them to run commands.
`audit/previews/human_review_index.md` must list direct relative paths to each final audio preview, generated image/contact sheet, video preview, 15-second render, SRT; what to evaluate; exact model/version and prompt/seed; music attribution; status `PENDING HUMAN REVIEW`.

Checklist must cover: voice naturalness/scientific and Latin pronunciation/numbers/units/stability/artifacts; image scientific accuracy/artifacts; video stability/flicker/deformation/black/frozen frames; RIFE ghosting/scene cuts; Real-ESRGAN halos/textures/artificial detail; depth stability; Manim correctness/readability; music/SFX suitability/rights; final loudness/true peak/sync/subtitles/editorial quality. Never fill human approval fields yourself.

PHASE 12 — FINAL PRODUCTION GATE

A component is PRODUCTION APPROVED only if all are true:
1. Exact code license permits intended commercial use.
2. Exact checkpoint/subcomponent licenses permit intended commercial use.
3. Code/weights pinned to recorded commit/revision.
4. Weight SHA256 recorded.
5. Component ran successfully on actual Kaggle T4 in FP16 or FP32.
6. No BF16 or FlashAttention 2 used.
7. Runtime/resource measurements attached to a real Kaggle log.
8. Required automatic quality checks passed.
9. Human quality acceptance explicitly supplied by a human.
10. No unresolved license condition, revenue threshold, or redistribution restriction prevents intended use.
Until all ten pass, set `production_status = "BLOCKED"`. Do not alter production configuration, dependency pins, model defaults, or current production stack based on an unapproved candidate. This is an audit, not permission to migrate production.

PHASE 13 — PERSIST EVIDENCE (run at the end of every stage)
Codespaces storage is ephemeral, so evidence must be committed:
1. Create (or reuse) branch `audit/kaggle-t4` from the current HEAD. Never commit to main/master directly, never force-push, never touch files outside audit/.
2. Before staging, create audit/.gitignore that excludes model weights and secrets: *.pth, *.pt, *.safetensors, *.ckpt, *.onnx, *.bin, *.gguf, *.npz, kaggle.json, *.token, .env, and any file larger than 50 MB. Record the SHA256 of excluded weights in the manifests instead.
3. Run `git status --short` and `git diff --cached --stat`; verify no credentials, tokens or weights are staged (grep staged text files for strings such as "KGAT", "username", "key" and report matches without printing values).
4. `git add audit/` only, commit with a message naming the stage and statuses, and push the branch. If the push fails (permissions, no remote), report the exact error and leave files in place; do not retry destructive git operations.
5. Record the branch name and commit SHA in audit/STAGE_<letter>_SUMMARY.md.

FINAL CHECKLIST — WHAT TO RETURN TO THE USER
Return a concise summary and exact repository paths to:
- audit/PRODUCTION_SMOKE_TEST_REPORT.md
- audit/results.json
- audit/results/component_results.json
- audit/provenance/source_manifest.json
- audit/provenance/kaggle_environment.json
- audit/provenance/kaggle_quota.json
- audit/scripts/kaggle_environment_snapshot.py
- P0/P1/P2 Kaggle notebooks and kernel-metadata.json under audit/kaggle/
- retrieved Kaggle logs under audit/logs/kaggle/
- installation logs and component tracebacks
- license/model-card copies under audit/licenses/
- weight/license SHA256 manifests
- audio/image/video previews under audit/previews/
- audit/previews/human_review_index.md
- Kaggle kernel URLs and, if used, Kaggle dataset URLs
- final PASS/FAIL/BLOCKED/NOT TESTED list
- estimated GPU-hour consumption per notebook and campaign total
- exact blockers preventing production approval
- branch name and commit SHA containing the audit evidence, plus the stage summary file

If Kaggle cannot be used because credentials, quota, internet, accelerator allocation, or CLI execution is unavailable, return partial audit evidence and a precise BLOCKED explanation. Never simulate Kaggle output, hardware, model inference, logs, licenses, or benchmark results.
```
