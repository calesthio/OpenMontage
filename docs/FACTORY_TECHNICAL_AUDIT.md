# OpenMontage — Factory Technical Audit

**Repository:** `sora73636-stack/OpenMontage` (fork of `calesthio/OpenMontage`), AGPL v3  
**Branch observed:** `factory/business-documentary-pilot` (working branch; `main` untouched per resume) — AGENT_GUIDE.md references `kilo/mega-100`; reconcile before work.  
**Audit date:** 2026-11-02  
**Auditor:** Kilo (ponytail full mode — minimal-change principle applied)  
**Constraint honored:** No Google Flow generation, no credit spend, no auth/browser-profile changes, `--no-spend` and MCP Security Proxy left intact, no working-module rewrites, no assumed capabilities — only observed behavior is reported.

---

## 0. Executive summary

OpenMontage is a mature, instruction-driven, agent-first video production framework. Its design (pipeline manifests + stage director skills + tool registry + checkpoint protocol) is sound and well-documented. A complete preproduction stack (research → evidence → script → fact-check → scene plan → prompt packets → character consistency → quality control → production manifest → audio sync → motion → render integration) already exists as pure local Python code with passing contract tests in prior sessions.

**However, the current container runtime is NOT production-ready.** ffmpeg/ffprobe, piper, kokoro/soundfile/torch, pytest, and most generator CLI dependencies are absent. The `PROJECT_STATE_HANDOFF.md` describes a different environment (ffmpeg 6.1.1 via apt, piper-tts 1.8.0, kokoro venv, pytest 9.1.1) that does not match this machine. The registry reports 141 discovered tools but only a small fraction are runnable here: `direct_clip_search`, `image_gen` (deprecated), `local_diffusion` (needs torch, absent), `diagram_gen`, `code_snippet`, character-animation tools, and a few analysis/post tools. Everything that needs ffmpeg (`video_compose`, `finish_audio`, `qc`, `render_integration` stub) is blocked.

**Headline finding:** The factory design is complete on paper and in code; what is missing is the runtime environment plus one integration layer that wires `script_analyzer → prompt_engineer → gflow image t2i → production_manifest → audio_sync → render_integration`. No paid API or credit is required to reach a pilot; the whole stack is $0-capable.

---

## 1. Documents consulted (requirements trace)

| Document | Status | Notes |
|---|---|---|
| `AGENT_GUIDE.md` | Read | Full agent contract, pipeline rules, registry protocol, present-both-runtimes hard rule |
| `PROJECT_CONTEXT.md` | Read | Architecture source of truth, 3-layer knowledge model |
| `PROJECT_STATE_HANDOFF.md` | Read | Consolidated handoff; describes env state not present in this container |
| `docs/GFLOW_CLI_COMPLETE_GUIDE.md` | Read | gflow-cli 0.92.0 reference; Nano Banana 2.1 default, ref_cap=10, `--no-spend` |
| `docs/AUTONOMOUS_VIDEO_PRODUCTION_GUIDE.md` | Read | 1 sentence = 1 image rule, 20–25 min target, 160–250 sentences, stage pipeline |
| `docs/PROJECT_READINESS_AUDIT.md` | Read | Readiness audit; lists 13 lib modules + 93-test suite (from prior env) |
| `docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md` | Read | Master plan v1.0, superseded by v3.2 for milestone ordering |
| `docs/OPENMONTAGE_PLAN_V3_2.md` | Read | Authoritative plan: aviation/spaceflight niche, max-3 runtime stack, stage-0 viability gate |
| `FACTORY_100_SPEC.md` | Read | Target "100% done" definition, 10 layers, build order F0–F7 |
| `pipeline_defs/factory.yaml` | Read | 14-stage factory manifest |
| `pipeline_defs/business-documentary.yaml` | Read | 12-stage evidence-first documentary manifest |
| `lib/*.py` (13 modules) | Read | All preproduction/render modules reviewed |
| `tools/tool_registry.py` | Read | 141 tools discovered; capability/availability catalogued |
| `schemas/artifacts/` | Read | 28 artifact JSON schemas |
| `docs/OPENMONTAGE_RESUME.md` / `WORK_LOG.md` | Read | Session history; P1 pilot complete in prior env |

**Documents NOT found (referenced in task but absent):** `docs/MASTER_VISUAL_STYLE_GUIDE.md` and `docs/VIDEO_PRODUCTION_FACTORY_MASTER_PLAN.md` do not exist in this repository. Their content is partially covered by `FACTORY_100_SPEC.md`, `OPENMONTAGE_PLAN_V3_2.md`, `AGENT_GUIDE.md` style playbooks, and `styles/*.yaml`. This is itself a documentation gap to close (see roadmap).

---

## 2. Existing system audit — component by component

Each component rated: Works / Partial / Missing / Duplicate / Fix / Keep / Replace.

### 2.1 Pipeline & orchestration

| Component | State | Verdict |
|---|---|---|
| Pipeline manifests (`pipeline_defs/*.yaml`) | Works | `animated-explainer`, `business-documentary` (12-stage), `factory` (14-stage), plus 8 others. Declarative, schema-validated. | Keep |
| Stage director skills (`skills/pipelines/<pipe>/`) | Works | 13 business-documentary skills + executive-producer. | Keep |
| `lib/checkpoint.py`, checkpoint protocol | Works | JSON checkpoints per stage, `human_approval_default` enforced, history archival. | Keep |
| `lib/pipeline_loader.py` | Works | Manifest loading + helpers. | Keep |
| Agent contract (`AGENT_GUIDE.md`) | Works | Present-both-runtimes hard rule, decision_log binding, escalation protocol. | Keep |

### 2.2 Research, fact-checking, sources

| Component | State | Verdict |
|---|---|---|
| `lib/script_analyzer.py` | Works | Splits script into meaning blocks, flags scientific claims, repetition. Local, zero-cost. | Keep |
| `lib/artifact_ids.py` | Works | Cross-artifact ID resolution (evidence/source/scene/asset/claim). Fail-closed dangling-reference detection. | Keep |
| `schemas/artifacts/` (evidence_ledger, fact_check_report, research_brief, topic_brief) | Works | 7 new business-documentary schemas registered. | Keep |
| Web search tool in registry | Missing | No registered web-search tool; research depends on human-supplied URLs (per resume blocker #5). | Fix — add |
| Primary-source verification | Partial | P1 pilot used tertiary sources (Wikipedia); primary sources (IPPC ISPM 15, NWPCA/USDA, pooler filings) identified but not retrieved. Publication blocked on this. | Fix — owner action |
| Niche research | Partial | `docs/openmontage/NICHE_PROFILE_SPEC.md`, `NICHE_DECISION.md` exist (aviation & spaceflight). Demand measurement not done (YouTube quota exhausted in prior session). | Fix |

### 2.3 Storyboard / scene planning

| Component | State | Verdict |
|---|---|---|
| `lib/scene_planner.py` | Works | Maps blocks → scenes with framing, camera, lighting, composition, duration, transitions. Role-based shot language. | Keep |
| `lib/visual_director.py` | Works | Enforces shot variety, caption space, composition rules. | Keep |
| `lib/prompt_engineer.py` | Works | Builds per-scene prompt packets (main/negative prompt, style, character, environment, references, 16:9). Visual foundation: bold ink illustration, no text/watermark. | Keep |
| `lib/quality_control.py` | Works | 9 per-scene QC criteria (script alignment, scientific accuracy [human review], character ref, duplicates, anatomy, contradictions, variety, no-text, technical suitability). | Keep |
| `lib/character_consistency_manager.py` | Works | Character anatomy, references, cross-scene consistency checking (limb count, features, clothing). | Keep |

### 2.4 Image generation — Nano Banana / Google Flow / gflow-cli

| Component | State | Verdict |
|---|---|---|
| `gflow-cli 0.92.0` | Works (verified via docs + CLI help) | Installed at `/home/vscode/.local/bin/gflow`. Profile `flow_remote` authenticated (`vvv86357482@gmail.com`), 50 credits balance read-only. | Keep |
| `gflow image t2i / i2i / batch / run` | Works (CLI confirmed; not called from Python) | Nano Banana 2.1 (NARWHAL) default, ref_cap=10 (native multi-reference character consistency — no IP-Adapter needed). 16:9 aspect, `-n 1`, `--reference-entity`. `--resume`, `--continue-on-error`. | Keep |
| `gflow character create` | Works (CLI confirmed) | CHARACTER entities with face/body prompt, voice, personality; returns entity_id. | Keep |
| `gflow movie.toml` | Works (template exists) | Multi-scene film from TOML. Not wired into OpenMontage pipeline. | Keep (unused) |
| OpenMontage → gflow Python wrapper | Missing | No Python module calls `gflow image`/`gflow run`; only manual CLI. No parsing of media_id/output_path/dimensions into `production_manifest`. | Fix — build wrapper |
| `gflow video t2v/i2v/r2v/chain/extend` | Works (CLI confirmed) | Veo/omni-flash clips 4–10s. Not needed for still-led factory (1 sentence = 1 image). | Keep (unused) |
| `--no-spend` / `GFLOW_MCP_NO_SPEND=1` | Enforced | Generate tools hidden in MCP; state machine stops at `READY_FOR_APPROVAL`. | Keep |
| `lib/mcp_security_proxy.py` | Works (13/13 tests in prior env) | Default-deny allowlist for browser-use, playwright, gflow. | Keep |
| Flow Job Manager (`lib/flow_job_manager.py`, `flow_integration.py`) | Works | DRAFT→VALIDATED→READY_FOR_APPROVAL→APPROVED→SUBMITTED→COMPLETED/FAILED. Auto-stops at READY_FOR_APPROVAL. Duplicate prevention by job_id + SHA-256. | Keep |

**Rule "one sentence = one prompt = one image":** Fully supported by gflow-cli design (one `t2i` call per prompt, `-n 1`, `--reference-entity` for character). NOT yet automated end-to-end (missing Python wrapper + sentence segmentation integration). No duplicate-image guard at the gflow level besides QC; needs a pHash/uniqueness check in the wrapper.

### 2.5 Characters & references

| Component | State | Verdict |
|---|---|---|
| `lib/character_consistency_manager.py` | Works | Local anatomy + reference management. | Keep |
| `gflow character create` | Works (CLI) | Nano Banana native multi-ref (ref_cap=10) replaces IP-Adapter (which failed 5× in prior session). | Keep — prefer gflow character over IP-Adapter |
| Master host reference chosen | Missing | 8 candidates exist (`contact_sheet_master.jpg`); owner has not picked one. Blocks downstream consistency. | Fix — owner decision |
| IP-Adapter path | Retired | Failed 5×; root cause was hand-constructed embeds instead of official `load_ip_adapter()`. Replaced by FLUX.2 Klein + gflow character. | Replace — do not revisit |

### 2.6 Batch generation

| Component | State | Verdict |
|---|---|---|
| `gflow run --config <json>` | Works (CLI) | Up to 50 prompts per config, max 5 per batch, `--continue-on-error`, `--resume`. | Keep |
| `gflow image batch` | Works (CLI) | Max 5 prompts. | Keep |
| OpenMontage batch orchestration | Missing | No Python driver that chunks 160–250 sentences into gflow batches with resume and dedup. | Fix — build |

### 2.7 Voice / TTS

| Component | State | Verdict |
|---|---|---|
| Kokoro-82M (`af_heart`) | Works in `/tmp/kilo/z1_venv` (Python 3.12.3, kokoro==0.2.2) | 10 narration files, 18:20 total, ~10% under 20–21 min target. NOT installed in main project env (soundfile/kokoro missing). | Keep — reinstall in main env |
| Piper (`en_US-lessac-medium`) | Works in prior session | Voice license UNKNOWN (CC-BY-4.0 asserted, not verified). Refused in `FACTORY_100_SPEC.md` L5. | Replace — do not use Piper for commercial |
| `tools/audio/piper_tts.py` | Code present | Unavailable (`cmd:piper` absent). Bare-voice resolution fix exists. | Keep code, not runnable |
| `lib/audio_sync.py` | Works | Binds scenes to narration segments, flags too_long/too_short/gap/overlap/missing_audio, manual correction. | Keep |
| `lib/finish_audio.py` | Code present | Two-pass loudnorm + limiter + ducking (I=-14, TP=-1.5). Unavailable (needs ffmpeg). | Keep — install ffmpeg |
| `tools/audio/finish_audio.py` | Code present | Unavailable (needs ffmpeg/ffprobe). | Keep |
| Cloud TTS (ElevenLabs/Google/Azure) | Missing | Not configured; unknown pricing → BLOCKED under zero-cost gate. | Keep as optional extra |
| Word-level timestamps | Partial | stable-ts forced alignment tested (82 timestamps / 80 words). Piper has 0% word timestamps. Kokoro timestamps need confirmation. | Fix |

### 2.8 Speech recognition & timings

| Component | State | Verdict |
|---|---|---|
| `tools/analysis/transcriber.py` (whisperx/faster-whisper) | Missing | `python:faster_whisper` not installed. | Fix — optional |
| `tools/analysis/azure_stt.py` | Missing | Needs `AZURE_SPEECH_KEY`. | Optional |
| Subtitle generation | Partial | `tools/subtitle/subtitle_gen.py` available; SRT rework done in prior pilot (2–5s chunks, ≤42 chars/line) but not fully reviewed. | Keep |

### 2.9 Remotion

| Component | State | Verdict |
|---|---|---|
| `remotion-composer/` | Present | `node_modules` installed (has @babel, @mediabunny, etc.). License Free confirmed (solo project). | Keep |
| `video_compose` remotion engine | Reported True | `render_engines.remotion = True`, but ffmpeg engine False. | Verify render actually works |
| Remotion scene types | Works | `text_card`, `stat_card`, `callout`, `comparison`, `hero_title`, `terminal_scene`, `anime_scene`, `bar_chart`, `line_chart`, `pie_chart`, `kpi_grid`, `progress_bar`. | Keep |
| Remotion render of pilot | Abandoned | Prior session abandoned Remotion render at ~3% (multi-hour ETA). Pilot used FFmpeg instead. | Investigate |

### 2.10 FFmpeg

| Component | State | Verdict |
|---|---|---|
| ffmpeg/ffprobe binary | Missing in this container | `which ffmpeg` → not found. Contradicts handoff (ffmpeg 6.1.1 via apt). | Fix — install |
| `lib/render_integration.py` | Works (code) | 8-check readiness validation, edit_decisions generation, stub-image test render. Test skipped (no ffmpeg). | Keep |
| `tools/motion/motion_variety.py` | Works | Pan/zoom/parallax/detail_crop/chapter-card FFmpeg filter generation + variety lint. | Keep |
| FFmpeg-based compose (`_render_via_ffmpeg`) | Blocked | Needs ffmpeg binary. | Fix — install ffmpeg |

### 2.11 Motion engine

| Component | State | Verdict |
|---|---|---|
| `lib/motion_engine.py` | Works | Per-scene MotionSpec (pan_zoom/detail_crop/parallax/static/chapter_card), ffmpeg filter strings, variety enforcement (no identical consecutive moves), seeded RNG for reproducibility. | Keep |

### 2.12 Rendering

| Component | State | Verdict |
|---|---|---|
| `lib/render_integration.py` | Works (code) | 8 pre-render checks (integrity, schema, sequence, assets, format, audio sync, duration match, transitions). `build_edit_decisions`, `create_test_render` (stub images only). | Keep |
| `tools/video/video_compose.py` | Blocked | Routes to Remotion/HyperFrames/FFmpeg based on `edit_decisions.render_runtime`. ffmpeg engine False here. | Fix — install ffmpeg |
| `tools/video/hyperframes_compose.py` | Partial | hyperframes_not available per registry (npx works on demand though). | Verify |
| Final MP4 render (20–25 min) | Missing | Pilot render was 85s (10 SDXL frames). Not rebuilt on 78 Klein frames. No 20-min render exists. | Fix — build |

### 2.13 Quality control

| Component | State | Verdict |
|---|---|---|
| `tools/qa/qc.py` | Works (code) | ffprobe_streams, full_decode, blackdetect, freezedetect, silencedetect, ebur128, duration_vs_script, subtitle_sync, credits_complete, claim_ids, rights_basis, added_value. Fail-closed (NOT_RUN/BLOCKED ≠ PASS). | Keep |
| `config/qc_thresholds.json` | Works | Initial guesses (LUFS -14±2, TP -1.5, black 0.05, freeze 2.0s, silence 0.10). | Keep |
| `qa_report.json` artifact | Missing | Schema exists; pilot never wrote `qa_report.json`. Gap in artifact completeness. | Fix |
| `tools/qa/` | Works | QA integration test scripts. | Keep |

### 2.14 Error recovery / resumability

| Component | State | Verdict |
|---|---|---|
| `lib/zero_cost_gate.py` | Works | Strict $0 gate, failure taxonomy (auth/billing/rate_limit/transport/no_results/unknown), `reroute_allowed()=always False`, run budget ledger. | Keep |
| `lib/production_manifest.py` | Works | Versioned manifest + SHA-256 integrity, seal/verify/load/save. | Keep |
| `lib/flow_job_manager.py` | Works | Job state machine, duplicate prevention, resume (`--resume-from`), `gflow data errors/sync`. | Keep |
| gflow `--resume` | Works (CLI) | Skips already-executed rows. | Keep |
| Checkpoint resume | Works | `checkpoint.get_next_stage()`, `in_progress` refresh, `awaiting_human` gating. | Keep |

### 2.15 Duplication

- Two pipeline families overlap: `business-documentary` (12-stage, evidence-first) and `factory` (14-stage). Both are valid; `factory` is the newer, more complete target. No code conflict.
- `image_gen` (deprecated selector-compat) vs `image_selector` + per-provider tools (`flux_image`, `local_diffusion`, etc.): `image_gen` marked DEPRECATED. Use `image_selector`.
- TTS: `piper_tts.py` in `lib/` (old) vs `tools/audio/piper_tts.py` (registry). Unify on `tools/audio/`.
- QC: `lib/quality_control.py` (preproduction scene QC) vs `tools/qa/qc.py` (post-render media QC). Complementary, not duplicate — keep both.

---

## 3. Runtime reality vs documented state (critical gap)

| Item | Documented (handoff/resume) | Actual in this container | Impact |
|---|---|---|---|
| ffmpeg / ffprobe | 6.1.1 installed via apt | **Not installed** | All video_compose/finish_audio/qc/render blocked |
| piper-tts | 1.8.0 + `en_US-lessac-medium` | **Not installed** | TTS unavailable |
| kokoro / soundfile / torch | venv at `/tmp/kilo/z1_venv`, working | **Not in main env** (`kokoro_tts` import fails) | TTS unavailable |
| pytest | 9.1.1 | **Not installed** | Test suite cannot run |
| `tests/factory/` results | 150 passed | Cannot run (no pytest) | Unverified |
| remotion `node_modules` | Reported empty | **Installed** | Remotion possibly usable |
| hyperframes | npx resolvable | npx works (0.9.2) | Usable on demand |
| gflow-cli | 0.92.0, profile authenticated | Confirmed installed | Image generation path OK |
| Python | 3.14.2 (handoff) | 3.12.16 | Fine |

**Conclusion:** The codebase is complete; the runtime is not. Before any factory work, install ffmpeg, piper/kokoro, and pytest. Cost: $0 (apt/pip, no API keys).

---

## 4. Capability inventory (registry, observed now)

| Capability | Configured | Available tools | Notes |
|---|---|---|---|
| clip_acquisition | 1/1 | `direct_clip_search` | archive.org/nasa/wikimedia keyless |
| image_generation | 2/23 | `image_gen` (deprecated), `local_diffusion` (needs torch) | Nano Banana via gflow-cli, NOT in registry |
| tts | 0/13 | — | kokoro/piper absent |
| video_generation | 0/31 | — | all need keys or GPU |
| video_post | 0/10 | — | video_compose needs ffmpeg |
| audio_processing | 0/2 | — | needs ffmpeg |
| audio_finishing | 0/1 | — | needs ffmpeg |
| analysis | 1/13 | `composition_validator` | transcriber needs faster-whisper |
| subtitle | 1/2 | `subtitle_gen` | remotion_caption_burn needs remotion |
| character_animation | 6/6 | all | local rig tools |
| graphics | 2/3 | `code_snippet`, `diagram_gen` | |
| music_search | 1/2 | `pixabay_music` | freesound needs key |
| publish | 1/1 | `export_bundle` | |
| kaggle_bridge | 0/1 | — | Kaggle CLI authenticated in prior env |

**Registry gap:** gflow-cli image generation is not represented as a registry tool. The factory must either add a `gflow_image` tool to the registry or drive gflow via subprocess in a dedicated wrapper module (recommended: `lib/gflow_wrapper.py`).

---

## 5. Assessment of the "one sentence = one prompt = one image" rule

The rule is **architecturally supported but not implemented**:

- gflow `image t2i` accepts a single positional prompt and `-n 1` → exactly one image per call. ✔
- Nano Banana 2.1 `ref_cap=10` gives native character consistency across calls via `--reference-entity` → same hero character across sentences without IP-Adapter. ✔
- `prompt_engineer.py` builds one `ScenePromptPacket` per scene with a unique `main_prompt` derived from `scene_plan.visual_idea` → unique per sentence. ✔
- `quality_control.check_no_text_in_image` enforces no text in main prompt + text prohibition in negative. ✔
- `quality_control.check_duplicate_frames` + `check_composition_variety` guard against duplicate/near-duplicate scenes. ✔
- **Missing:** (a) sentence-level segmentation producing `S001…S250` IDs tied to narration; (b) Python wrapper calling gflow per sentence and writing `production_manifest` rows; (c) automatic pHash/uniqueness re-roll on duplicate; (d) per-sentence audio binding via `audio_sync`.

Verdict: **Keep the rule.** Implement the wrapper + segmentation; do not change the rule.

---

## 6. Current state conclusion

OpenMontage is **design-complete, runtime-incomplete**:

- **Complete:** pipeline manifests, stage skills, artifact schemas, preproduction lib (13 modules), zero-cost gate, checkpoint/resume protocol, QC tooling, Motion engine, render integration, MCP security proxy, Flow Job Manager, gflow-cli + Nano Banana integration path.
- **Incomplete / blocked:** runtime deps (ffmpeg, piper/kokoro, pytest, torch), gflow Python wrapper, sentence segmentation → image pipeline, character master reference selection, music bed, final 20–25 min MP4 render, `qa_report.json` artifact, primary-source verification, web-search tool.

**Overall status:** BLOCKED on runtime install + one integration wrapper, not on design. The path to a pilot film is short and $0.

---

## 7. What to keep / replace / fix

| Decision | Item | Reason |
|---|---|---|
| KEEP | gflow-cli + Nano Banana 2.1 | Already integrated, ref_cap=10 native character consistency, `--no-spend` enforced, 50 credits verified |
| KEEP | Kokoro-82M (`af_heart`) | Measured, Apache-2.0 weights, $0 local, preferred over Piper (license unknown) |
| KEEP | All 13 lib modules + registry + checkpoint protocol | Sound design, tests passed in prior env |
| KEEP | `business-documentary` + `factory` manifests | Evidence-first, gated, fail-closed |
| KEEP | MCP Security Proxy + `--no-spend` | Spend governance, must not be disabled |
| KEEP | Remotion + HyperFrames | Both present; present both at proposal per hard rule |
| REPLACE | Piper TTS | Voice license unknown; FACTORY_100_SPEC refuses it |
| REPLACE | IP-Adapter character consistency | Failed 5×; superseded by gflow `--reference-entity` |
| FIX | Install ffmpeg/ffprobe, piper/kokoro, pytest | Runtime prerequisites |
| FIX | Build `lib/gflow_wrapper.py` + sentence-segmentation driver | The one missing integration layer |
| FIX | Write `qa_report.json`, populate `music_library/`, select master reference | Pilot completion items |

Next document: `docs/TOOL_COMPARISON.md`, then `docs/FACTORY_IMPLEMENTATION_ROADMAP.md`.
