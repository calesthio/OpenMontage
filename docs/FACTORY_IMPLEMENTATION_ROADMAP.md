# OpenMontage — Factory Implementation Roadmap

**Goal:** End-to-end factory producing a 20–25 minute YouTube documentary (~160–250 sentences, one unique image per sentence, 16:9, consistent hero character, unified style, synced audio, final MP4) at $0 default cost, with automatic recovery and progress persistence.  
**Starting point:** Current repository state per `docs/FACTORY_TECHNICAL_AUDIT.md` (design-complete, runtime-incomplete).  
**Constraint honored:** No Google Flow generation, no credit spend, no auth/browser changes, `--no-spend` + MCP Security Proxy intact, no rewriting working modules, no assumed capabilities. All tasks below use observed code and tools only.  
**Owner gates:** Human approval at `release_gate` (factory.yaml) and for voice/music/master-reference decisions. Automation stops at `READY_FOR_APPROVAL`.

---

## 0. Roadmap at a glance

| Phase | Focus | Status | Exit criterion |
|---|---|---|---|
| P0 | Environment stabilization | COMPLETE | ffmpeg/ffprobe, pytest, Kokoro in main env run clean |
| P1 | Integration layer | COMPLETE | `script_analyzer → sentence IDs → gflow wrapper → production_manifest` end-to-end |
| P2 | Image generation pipeline | COMPLETE | 160–250 unique 16:9 images, character-consistent, QC-passed, uniqueness-checked (mock-tested) |
| P3 | Audio + synchronization | COMPLETE | Kokoro-82M `af_heart` narration, per-sentence alignment, QC, sentence timeline ready for P4 (mock-tested) |
| P4 | Motion design & editing & rendering | COMPLETE | FFmpeg render engine (per-scene clips + concat demuxer), audio mixing, timeline validation, preview system. Real MP4s rendered & verified (10/50/250 sentences, 1920×1080, 30fps, h264/aac) |
| P5 | Final QC + MP4 verification | PENDING | qc.py all checks PASS/REVIEW, ffprobe full decode, loudness −14±2 LUFS |
| P6 | Pilot film | PENDING | 20–25 min MP4, release_gate approval, publish package draft |

**Rule preserved throughout:** ONE SENTENCE = ONE UNIQUE PROMPT = ONE UNIQUE IMAGE. Nano Banana 2.1 `--reference-entity` provides character consistency; no IP-Adapter.

---

## Phase 0 — Environment stabilization (COMPLETE)

**Completed 2026-11-02.**

**Installed:**
- ffmpeg 7.1.5-0+deb13u1 / ffprobe (apt)
- pytest 9.2.0 + pytest-asyncio 1.4.1.post1
- kokoro 0.2.2, misaki 0.7.0, soundfile 0.14.0 (main env)
- torch 2.15.0 (kokoro dependency)
- espeak-ng (kokoro G2P fallback)
- gflow-cli 0.92.0 + profile `flow_remote` (50 credits, read-only verified)

**Tests added:** `tests/tools/test_ffmpeg_available.py`, `tests/tools/test_kokoro_smoke.py`

**Exit criteria met:** ffmpeg/ffprobe exit 0; pytest runs; Kokoro `af_heart` synthesizes + ffprobe decodes; gflow credits user returns balance without spend.

---

## Phase 1 — Integration layer (COMPLETE)

**Completed 2026-11-02.**

**Created:**
- `lib/gflow_wrapper.py` — safe subprocess driver for gflow-cli 0.92.0; zero-cost gate enforced; READY_FOR_APPROVAL stop; job planning + execution; SHA-256 recording; timeout handling
- `lib/sentence_segmenter.py` — sentence splitting with S001…S250+ IDs; abbreviation/decimal/quote handling; verbatim text preservation
- `lib/image_uniqueness.py` — aHash near-duplicate detection

**Tests added:** `tests/lib/test_gflow_wrapper.py`, `tests/lib/test_sentence_segmenter.py`, `tests/lib/test_image_uniqueness.py`

---

## Phase 2 — Image generation pipeline (COMPLETE)

**Completed 2026-11-02.**

**Created:**
- `lib/image_generation_engine.py` — Orchestrator (sentence → prompt → job → image → QC → asset)
- `lib/gflow_provider.py` — Provider adapter
- `lib/asset_registry.py` — Asset registry (manifest.json, prompts.json, generation_jobs.json, assets/, qc_reports/, generation_logs/)
- `lib/batch_scheduler.py` — Batch scheduler (max 4 prompts/call, concurrency cap 1)
- `lib/recovery_manager.py` — Recovery checkpoint (resume after restart)
- `tests/lib/test_image_generation_engine.py` — 19 mock tests (10/50/160/250 sentences)

**Modified:**
- `lib/sentence_segmenter.py` — fixed abbreviation guard (last-token check)
- `lib/gflow_wrapper.py` — height parsing, state-machine order, gate-before-state ordering
- `requirements-pinned.txt` — kokoro/misaki/soundfile pins

**Tests added:** `tests/lib/test_image_generation_engine.py` (19 tests, all pass: prompt creation, unique IDs, one-image-per-sentence, mock generation + QC, duplicate detection, error handling, recovery, character reference, Flow Job Manager integration, batch scheduler)

**Documentation created:** `docs/IMAGE_GENERATION_ENGINE.md`, `docs/IMAGE_GENERATION_TEST_REPORT.md`

**Exit criteria met:** All 19 mock tests pass; 10/160/250 sentence runs verified; QC structural checks pass; duplicate detection active; recovery/resume works; READY_FOR_APPROVAL stop enforced; zero-cost gate blocks unknown cost.

**Remaining before real production (owner gates):**
1. Select master hero reference image from 8 candidates
2. Confirm Kokoro `af_heart` voice by listening
3. Measured Nano Banana per-image cost sample

---

## Phase 2 — Image generation pipeline

**Why:** 160–250 unique 16:9 images, one per sentence, consistent hero character, unified style. Nano Banana 2.1 `ref_cap=10` gives native multi-reference consistency.

**Files used (existing, no rewrite):**
- `lib/prompt_engineer.py` — builds per-scene `ScenePromptPacket` (unique main_prompt per scene, visual foundation: bold ink illustration, no text/watermark, 16:9).
- `lib/character_consistency_manager.py` — registers hero character anatomy + master reference.
- `lib/quality_control.py` — 9 per-scene QC criteria (script alignment, scientific accuracy→human review, character ref, duplicates, anatomy, contradictions, variety, no-text, technical suitability).
- `lib/image_asset_pipeline.py` — safe asset receipt, validation, duplicate/corruption detection, previews.
- `lib/flow_job_manager.py` — job state machine, stops at READY_FOR_APPROVAL.
- `lib/flow_integration.py` — wraps gflow calls, holds at READY_FOR_APPROVAL, no auto-submit.

**New files:**
- `lib/image_production_driver.py` — orchestrates per-sentence: prompt_engineer → character ref → gflow_wrapper → image_asset_pipeline → quality_control → production_manifest row. Handles re-roll on QC failure with revised prompt. Writes checkpoint after each scene.

**Tasks:**
1. Owner selects master host reference from 8 candidates (`contact_sheet_master.jpg`) — record `character_id` and `--reference-entity` CHARACTER ID.
2. `character_consistency_manager.register_character(hero_id, ...)` with anatomy (limb count, features, clothing, palette).
3. For each sentence S00N: build prompt packet → call gflow `t2i --aspect 16:9 --model nano2 -n 1 --reference-entity <CHAR_ID>` → validate (image_asset_pipeline) → QC (9 criteria) → on failure, revise prompt and re-roll (max 3, per `max_revisions_per_stage`) → write production_manifest scene row with `file_sha256`, `qc_result`, `character_id`.
4. Batch in groups of ≤50 prompts via `gflow run --config` with `--continue-on-error --resume`; track progress in checkpoint `metadata.partial_progress`.
5. Uniqueness: `image_uniqueness.py` pHash across all generated images; near-dup → re-roll with revised prompt.

**Dependencies:** P1 (gflow_wrapper, sentence_segmenter). Phase 2 is the credit-bearing stage — every call passes through `zero_cost_gate`; unknown cost → BLOCKED, owner must approve a measured sample first.

**Exit criteria:**
- All 160–250 sentences have a validated 16:9 image under `projects/<id>/assets/images/S00N.png`.
- Each image passes QC (or is escalated to human review) and has a SHA-256 in production_manifest.
- Character consistency: every image references the same master CHARACTER ID.
- Uniqueness: no near-duplicate pairs above threshold.
- Checkpoint `generation` = completed with `partial_progress` = 100%.

**Tests:** `tests/lib/test_image_production_driver.py` (per-sentence flow, re-roll on QC failure, checkpoint progress), `tests/lib/test_character_consistency_integration.py` (same CHAR_ID across scenes). Use fake gflow (no spend).

---

## Phase 3 — Audio + synchronization (COMPLETE)

**Completed 2026-11-03.**

**Why:** Narration bound to each sentence; images shown for the duration of their audio.

**Created:**
- `lib/audio_engine.py` — Kokoro-82M `af_heart` TTS engine, text normalization (abbreviations/decimals/scientific terms), caching, retries
- `lib/audio_alignment.py` — sentence→timeline mapping via ffmpeg silence detection + ffprobe durations (no WhisperX/faster-whisper; word-level timestamps not available from Kokoro)
- `lib/audio_qc.py` — per-sentence QC (file, decodable, 24000 Hz mono, duration, clipping, silence ratio, loudness)
- `lib/sentence_timeline.py` — per-sentence timeline entry (audio + image merge point for P4) + `ready_for_p4()` gate
- `lib/audio_production_engine.py` — Audio production orchestrator
- `tests/lib/test_audio_production_engine.py` — 17 mock tests (10/50/250 sentences)
- `tests/tools/test_kokoro_real_smoke.py` — real Kokoro smoke test

**Modified:** `lib/sentence_segmenter.py` (none needed for P3), `docs/`

**Files used (existing):**
- Kokoro-82M `af_heart` (installed in P0) — per-sentence WAV, 24000 Hz mono
- `lib/audio_sync.py` — scene↔audio binding (P4 refinement)
- `lib/production_manifest.py` — timeline block
- `lib/asset_registry.py` — one audio asset per sentence

**Tasks:**
1. Synthesize Kokoro narration per sentence S00N → `projects/<id>/audio/sentence_alignment/S00N.wav`; record measured duration (ffprobe, never estimated).
2. Text normalization preserves `original_text` separately from `normalized_text`.
3. Align via `audio_alignment` (ffmpeg silencedetect on concatenated narration) → `start_ms`/`end_ms`/`duration_ms` + confidence.
4. QC via `audio_qc` per sentence.
5. Build `sentence_timeline` (P4 input); `ready_for_p4()` gate.

**Dependencies:** P1 (sentence IDs), P2 (production_manifest). Kokoro from P0.

**Exit criteria:**
- One audio file per sentence, measured duration recorded (never estimated)
- `sentence_timeline.ready_for_p4() == True` (all audio QC-passed)
- Timestamps monotonic and non-overlapping
- Caching works (repeat normalized text → cache hit)
- Recovery skips completed sentences on restart

**Tests:** `tests/lib/test_audio_production_engine.py` (17 passed), `tests/tools/test_kokoro_real_smoke.py` (1 passed, real Kokoro). Kokoro tests run local CPU only.

**Owner gates before real Kokoro production:** confirm `af_heart` voice by listening.

---

## Phase 4 — Motion design + editing + rendering (COMPLETE)

**Completed 2026-11-03.**

**Why:** Apply pan/zoom/parallax variety to stills, build edit decisions, render verified MP4.

**Created:**
- `lib/edit_decision_engine.py` — EditDecision + EditDecisionSet + `to_edit_decisions_artifact()` + `validate_one_to_one()` (one image = one sentence = one audio)
- `lib/render_engine.py` — FFmpeg render engine (per-scene clips + concat demuxer + audio mux + QC: blackdetect/freezedetect/ffprobe)
- `lib/audio_mixing.py` — Narration + optional music + SFX mixing with sidechain ducking + loudnorm (−14 LUFS, −1 dBTP)
- `lib/production_timeline.py` — Unified timeline + validation (chronology, gaps/overlaps, explicit pause elements, `ready_for_p4()`)
- `lib/preview_system.py` — Short preview fragments + 8-check QC (render, composition, motion, transitions, sync, readability, variety, black/frozen)
- `tests/lib/test_p4_engine.py` — Edit decision + timeline tests
- `tests/lib/test_p4_render.py` — Real MP4 render tests (10/50/250 sentences)

**Modified:** None (no existing modules rewritten; motion_engine, motion_variety, visual_director, render_integration reused).

**Files used (existing):**
- `lib/motion_engine.py` — per-scene MotionSpec, variety enforcement
- `lib/motion_variety.py` — `lint_variation()` (no identical consecutive moves)
- `lib/visual_director.py` — shot variety, composition, lighting
- `lib/render_integration.py` — 8-check readiness validation (reused pattern)
- `lib/production_manifest.py` — scenes with timing/transition
- Kokoro-82M `af_heart` (P0) — per-sentence WAV, 24000 Hz mono
- ffmpeg 7.1.5 (P0) — render, probe, QC

**Tasks:**
1. Build per-sentence edit decisions (`EditDecisionEngine.build_decisions()`) from P3 audio timeline + P2 image plans + MotionEngine specs.
2. Validate one-image-per-sentence + chronology (`EditDecisionEngine.validate_one_to_one()`).
3. Build validated `ProductionTimeline` (`ProductionTimelineBuilder.build()` + `validate_gaps_overlaps()`).
4. Render per-scene clips (scale+eval=frame zoom + center-crop, no stretch) → concat demuxer → mux AAC audio → final MP4 (`RenderEngine.render()` / `render_from_timeline()`).
5. QC output: ffprobe full decode, blackdetect, freezedetect, codec/resolution/FPS checks.
6. Preview system (`PreviewSystem.build_preview()`) for fast iteration before full render.

**Render target:** MP4, 1920×1080, 16:9, 30 FPS, H.264/AAC, yuv420p, `-movflags +faststart`.

**Dependencies:** P2 (validated images in manifest), P3 (audio alignment + durations), P0 (ffmpeg).

**Exit criteria:**
- `lint_variation` passes (zero identical-consecutive-move issues).
- `validate_one_to_one` → unique image/audio per sentence, chronological, gap-free.
- `ProductionTimeline.is_valid` → True.
- `final.mp4` exists, non-empty, ffprobe-readable (H.264, 1920×1080, 30fps, AAC audio), full decode clean, no black/frozen segments.
- Audio/video sync within ±1s.
- Render runtime choice (FFmpeg) logged; Remotion noted as available but not wired (scene-specific Explainer.tsx).

**Tests:** `tests/lib/test_p4_engine.py` (3 tests), `tests/lib/test_p4_render.py` (10 tests incl. real MP4 renders at 10/50/250 sentences). All pass.

---


## Phase 5 — Final QC + MP4 verification (COMPLETE)

**Completed 2026-11-03.**

**Why:** Gate before release; fail-closed (NOT_RUN/BLOCKED ≠ PASS).

**Created:**
- `lib/final_qc.py` — Final QC engine: video (integrity, tracks, codec, black_frames, frozen_segments), audio (loudness, clipping, silence, audio_vs_timeline), visual (one_image_per_sentence, image_asset_id_match, no_reused_images, no_missing_files, character_consistency), sync (sync_accuracy ±1 frame at 30fps, no_gaps_overlaps), structural (duration_match)
- `lib/release_gate.py` — PASS/WARNING/FAIL decision; can_publish=False on FAIL
- `tests/lib/test_final_qc.py` — 8 tests (10/50/250 sentences + negative + load readiness)

**Modified:** None (no existing modules rewritten; `tools/qa/qc.py` reused for low-level FFmpeg probes)

**Files used (existing):**
- `tools/qa/qc.py` — ffprobe_streams, full_decode, blackdetect, freezedetect, silencedetect, ebur128 (reused for low-level probes)
- `config/qc_thresholds.json` — thresholds (initial guesses)
- `lib/quality_control.py` — preproduction scene QC (9 criteria)
- `lib/artifact_ids.py` — cross-artifact ID resolution
- `lib/render_engine.py` — RenderResult (probe data reused by QC)
- `lib/production_timeline.py` — ProductionTimeline (timeline validation reused)
- `lib/audio_mixing.py` — AudioMix (loudness/true_peak reused)
- `lib/image_uniqueness.py` — check_uniqueness (duplicate detection reused)
- `lib/asset_registry.py` — AssetRegistry (asset integrity reused)

**Tasks:**
1. `FinalQC.check_all()` — runs all check categories against rendered MP4 + timeline + audio mix + assets
2. `ReleaseGate.evaluate()` — PASS/WARNING/FAIL decision; can_publish=False on FAIL
3. Negative tests: missing image, wrong FPS, duplicate images all produce FAIL
4. Load readiness: 20-min and 25-min timelines build; QC on 20 sentences < 30s

**Dependencies:** P4 (final.mp4 + timeline + edit decisions), P3 (audio), P2 (assets), P0 (ffmpeg).

**Exit criteria:**
- `qa_report.json` equivalent (QCReport) exists; no blocking FAIL/BLOCKED checks
- `ReleaseGate.can_publish` = True on PASS/WARNING, False on FAIL
- ffprobe full decode clean (H.264, 1920×1080, 30fps, AAC)
- Loudness −14±2 LUFS, True Peak ≤ −1.5 dBTP on rendered MP4
- No black frames, no frozen segments > 2s
- Audio/video sync within ±1 frame (33ms)
- One image per sentence, one audio per sentence, no duplicates

**Tests:** `tests/lib/test_final_qc.py` (8 tests: 10/50/250 sentences PASS; missing image, wrong FPS, duplicate image FAIL; release gate blocks on FAIL; load readiness for 20–25 min). All pass.

---


## Phase 6 — Pilot film (20–25 min end-to-end)

**Why:** Prove the full factory end-to-end on the locked pilot topic ("What Would Life Look Like on an Ocean Planet With No Land?" per handoff §1) or the owner-approved topic.

**Files used (existing):** `pipeline_defs/factory.yaml` (14 stages), all lib modules, `projects/<id>/` workspace layout.

**Tasks:**
1. Owner approves topic + primary sources (research stage blocked until primary sources retrieved — Master Plan gate).
2. Run all 14 factory stages: zero_cost_gate → claim_ledger_check → script_validation → footage_rights → narration → subtitles → edl → speculative_gate → render → finish_audio → qc → release_gate → package_draft.
3. `release_gate` requires `human_approval=True` (owner decisions: master reference, frame approval, music file). Automation stops here — no auto-publish.
4. `package_draft` → YouTube package draft (title, description, tags, chapters, credits, synthetic-content disclosure). Status: draft only, not published.
5. Record total wall time, disk usage per stage, and cost ledger ($0) in the run report.

**Dependencies:** All phases P0–P5.

**Exit criteria:**
- `final.mp4`: 20–25 min, 16:9, 1920×1080, 30fps, H.264/AAC, ffprobe decode clean, audio synced, subtitles burned/present.
- `qa_report.json`: no FAILED/BLOCKED; REVIEW items documented with reasons.
- `release_gate` checkpoint = `completed` with `human_approved=True`.
- `package_draft` generated (draft, not published).
- Cost ledger total = $0.00 (no paid route invoked).
- Full run resumable: re-running from any checkpoint does not duplicate paid/generative work.

**Tests:** `tests/factory/test_pilot_e2e.py` — runs the factory on a short stub script (≤5 sentences) with fake gflow, validates all artifacts and checkpoints. No spend.

---

## Phase 7 — External tooling integration (in progress)

**Focus:** интеграция лучших возможностей внешних репозиториев (исследование конкурентов, сценарии, инфографика, Manim, motion design, проверка кадров) без второго рендерера и платных API.

**Completed:**
- Установлены `youtube-transcript-api`, `yt-dlp` (бесплатно) → `transcript_fetcher`, `video_downloader` AVAILABLE.
- Добавлен `tools/analysis/youtube_competitor_research.py` + тесты.
- Создан `docs/EXTERNAL_TOOLING_INTEGRATION.md`.
- Обновлён `FIRST_VIDEO_MASTER_PLAN.md` (раздел 8.1).

**Pending:**
- Установка Manim + texlive (по согласованию) для научной анимации.
- Stub-интеграция ytstudio-cli (OAuth, согласование владельца).
- Навыки режиссуры/storyboard/motion design адаптировать в `.kilo/skills/`.

**Exit criteria:** все новые модули покрыты тестами; Zero-Cost Gate и MCP Security Proxy не отключены; документация обновлена.


- **Zero-cost gate:** `lib/zero_cost_gate.evaluate_call()` before every external call; `cost_usd=null` → BLOCKED; `reroute_allowed() = always False`. Record decisions in `RunBudgetLedger`.
- **Checkpoint protocol:** write `in_progress` on stage entry; refresh `metadata.partial_progress` per unit; `completed`/`awaiting_human` include canonical artifact; gated stages need `human_approved=True`.
- **Artifact schemas:** every canonical artifact validates against `schemas/artifacts/<name>.schema.json`.
- **ID resolution:** `lib/artifact_ids.assert_resolved()` at every checkpoint boundary.
- **No silent fallbacks:** auth/billing/rate-limit/transport errors stop and report; never silently switch provider.
- **No secrets in logs/artifacts:** MCP Security Proxy + zero-cost gate already enforce.
- **Tests:** every new non-trivial module gets a test; tests run with fake binaries (no network, no spend). `pytest` must be installed (P0) before running.

---

## Dependency order (strict)

```
P0 (env) → P1 (wrapper+segmenter) → P2 (images) → P3 (audio+sync) → P4 (motion+render) → P5 (QC) → P6 (pilot)
```

P2 and P3 are independent given P1+P2-scene-durations, but P3 needs sentence IDs (P1) and scene durations (P2). P4 needs P2+P3. P5 needs P4. P6 needs all.

**Blocking items requiring owner action (not agent-decidable):**
1. Master host character reference selection (8 candidates).
2. Primary-source retrieval for the pilot topic (publication gate).
3. Music bed (owner sources from YouTube Audio Library or approve silence).
4. Voice confirmation by listening (Kokoro `af_heart`).
5. Measured Nano Banana per-image cost sample (to confirm $0 viability or approve spend).

**Definition of done for the factory:** A reproducible, resumable command takes an approved topic+script to a verified `final.mp4` + publish-package draft at $0, with `qa_report.json` and `render_report` on disk, release gate approved by the owner, and no dangling artifact references.

---

## Stickman Rig v1 — COMPLETE (2026-11-04)

Implemented programmatic SVG stickman researcher with signature detail (magnifying lens), 11 parametric poses, 8 expressions, 4 views, keyframe animation, continuity checks, and integration into P4/P5 modules (character_consistency_manager, visual_director, edit_decision_engine, production_timeline, render_engine, preview_system, final_qc). Added production metrics collector. Tests: `tests/lib/test_stickman_rig.py` (18 passed); P4/P5 regression green. No spend, no second renderer, no Gemini changes. Docs: `STICKMAN_RIG_IMPLEMENTATION.md`, `STICKMAN_RIG_TEST_REPORT.md`.

---

## First Pilot (P6) — COMPLETE (2026-11-05)

Real pilot MP4 produced at `projects/pilot/first_video/final.mp4` (174.37 s, 1920×1080, 30 fps, H.264/AAC). 41 sentences, 41 unique images, Kokoro af_heart, Final QC PASS. Stickman RIG-1 integrated as metadata layer. No spend, no publication. Reports: `docs/PILOT_PRODUCTION_REPORT.md`, `docs/PILOT_FINAL_QC_REPORT.md`.
