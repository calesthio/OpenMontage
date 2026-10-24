# Improvement changelog

Record accepted changes, benchmark evidence, reviewer and rollback method.

## 2026-10-21 — Milestone F1-fix (Kilo), pipeline correctness (config/tools/scripts/tests/docs)

Approved inputs: SCR-05 (QC thresholds from config), SCR-06 (every claim_id on a
line), SCR-07 (episode-generic EDL); plus the two red chapter tests and the
pytest-collection failure from F0. `FACTORY_100_SPEC.md` was not edited.

- `tools/qa/qc.py`: new `load_thresholds()`; `DEFAULT_CONFIG_PATH` = repo
  `config/qc_thresholds.json`; missing/unreadable/non-object/non-numeric config
  returns `ToolResult(success=False)` with a one-entry `thresholds_config` BLOCKED
  report (verdict BLOCKED). `thresholds_source` is reported in success data.
  `claim_ids_resolve` now treats a line as SINGLE_SOURCE if ANY cited id is
  SINGLE_SOURCE (was: last id only).
- `config/qc_thresholds.json`: converted to strict JSON (comments removed; values
  unchanged). `finish_audio` reads the same keys and is unaffected.
- `scripts/run_episode.py`: added `_parse_script_rows/_group_beats/_beat_claim_ids/
  _episode_narration_duration`; `cmd_edl` derives title/beat/credits cards,
  durations, claim_ids and rationale from the episode script + measured narration
  duration (no ARTEMIS literals, no 185.43 constant); `cmd_script_validation` and
  `split_script_into_chapters` share the parser; `cmd_qc` passes `config_path`.
- `tests/tools/test_qc_tool.py`: +9 tests (default/override thresholds, verdict
  flip by config, missing/malformed fail-closed, mixed-ID SINGLE flags, unknown id
  in the middle, all-resolved PASS).
- `tests/test_edl_generic.py`: +5 tests (two fake episodes differ; claim_ids from
  script; manifest duration; BLOCKED without script/duration).
- `pytest.ini`: `norecursedirs` excludes the nested `youtube-niche-finder/`
  checkout (its backend needs psycopg2); full-root collection now succeeds.
- Evidence: 22/22 qc tests (exit 0), 5/5 chapter, 5/5 EDL, 24/24 impacted
  (exit 0); before the fix 2 chapter tests failed and 9 new tests were red.
- Rollback: `git revert` of the F1-fix commit; the config file's old comment
  lines are the only non-code loss.


## 2026-10-21 — Milestone S4 (Kilo), model bakeoff (docs/tools/scripts/tests)

### S4-1 PROMPTING FACTS (DONE)
- docs/openmontage/image_gen/PROMPTING_FACTS.md — verified prompting claims against official sources (vendor-official / blog / UNVERIFIED labels). Key confirmations: Z-Image-Turbo guidance_scale=0.0 for Turbo, negative_prompt accepted at pipeline level but ignored when guidance_scale<1 (diffusers z_image docs); SDXL negative_prompt + guidance_scale default 5.0 (HF diffusers docs); FLUX.2-klein-4B local FluxPipeline honours guidance_scale (default 3.5, enabled >1) and negative_prompt (only when true_cfg_scale>1) (diffusers FluxPipeline docs). BFL docs.bfl.ai prompting applies to the cloud API service, not the local pipeline.

### S4-2 RUN ORDER / MATRIX (IN_PROGRESS)
- docs/openmontage/image_gen/prompt_test_matrix.json schema 1.1: 12 scenes x 2 seeds x 3 models x 3 variants = 216 renders; 24 images per cell (meets scorer >=24/cell minimum); neutral render IDs for blind naming; prompt_test_mapping.json regenerated to unblind.
- tools/kaggle_bridge/s4_bakeoff_run.py: generalized one-model-per-kernel runner, fp16 only, NO bitsandbytes, NO CPU fallback (requires CUDA), non-zero exit if images < prompts, full tracebacks saved to output, exact versions (diffusers commit hash, transformers, huggingface_hub, torch) recorded in manifest via --force-reinstall pinned stack (hub 1.x + transformers 5.x + torchao 0.11-0.14 + diffusers git main).
- scripts/s4_push_bakeoff.py: pre-renders prompts via OpenCode-owned tools/prompting.builder (read only), embeds job config as JOB_EMBEDDED (Kaggle copies only script.py), pushes to forts845/openmontage-runner (GPU + internet).
- Model order (owner): 1) Z-Image-Turbo — BLOCKED after 5 attempts (final error: diffusers.loaders.single_file import failure, transformers 5.x vs git-main diffusers; max fix attempts reached, moved on per stop rule); 2) SDXL Base + madebyollin/sdxl-vae-fp16-fix — SUBMITTED s4-sdxl-1, RUNNING with torchao pin (1 fix attempt used, 1 remaining); 3) FLUX.2-klein-4B — PENDING.

### S4-3 PROMPT-RULE EXPERIMENTS (DONE)
- scripts/s4_verify_prompt_experiments.py: 12/12 assertions pass using tools/prompting.builder (read only). Confirms: zimage negative_prompt=None (ignored), negation!=positive phrasing, style-first; klein anatomy-first(C)!=anatomy-last(B), guidance=None (uses diffusers default 3.5); sdxl negative_prompt present, guidance 7.5, steps 50; determinism. Objective image measurement (text artifacts via QC detector, pHash duplicates, blur) requires generated images from S4-2 Kaggle jobs.

### S4-4 BLIND PACK (IN_PROGRESS)
- scripts/score_rubric.py (OpenCode-owned, read only) proven on dummy CSV: loads, validates columns + 0-2 score range, computes per-cell severe-artifact rate / repair burden / usable share / eligible (>=24 images), reports INSUFFICIENT when no cell qualifies, lists reviewer disagreements.
- Contact sheets (R001... neutral IDs) + mapping file in projects/ (not committed) blocked pending generated images from S4-2.

## 2026-10-19 — Milestone K (Kilo), factory scope only (docs/tools/config)

### K1 NICHE PROFILE (DONE)
- Created docs/openmontage/NICHE_PROFILE_SPACE_ASTRONOMY_HD.md — niche profile spec for "Space & Astronomy on HD Public-Domain Footage" (NASA SVS, images.nasa.gov, ESA/Hubble where rights allow, archive.org, Wikimedia), following NICHE_PROFILE_SPEC.md schema; storage_policy enum, excluded_content, required_primary_doc_types, viability/added-value gates, episode templates, rights notes per RIGHTS_MODEL.md.
- Updated docs/openmontage/NICHE_DECISION.md: CID stays as pilot/test video only (demand measured: DEMAND_SIGNAL_PRESENT, top videos ~100k–138k views/365d), but all licensable CID clips are 320x240 (below the HD>=720p bar) → CID remains test fixture for claim-ledger/QC/rebuild tooling, not primary niche rollout.

### K2 FOOTAGE PROBE (DONE)
- docs/openmontage/footage/K2_FOOTAGE_PROBE_SPACE_ASTRONOMY.md — probed 10 candidate topics keyless via NASA images-api; all NASA-produced, rights=None → source_policy_us_gov candidates, no third-party credit; HD>=720p verified via ffprobe for 3 downloaded clips (Artemis 3840x2160, Hubble 1920x1080, Perseverance 3840x2160). Beat counts per candidate 6-beat structure. Top 3 topics: (1) Artemis/SLS launch — 672 hits, 4K, all 6 beats; (2) Perseverance — 117 hits, 4K; (3) Hubble — 152 hits, 1080p, best astronomy fit. Best topic for K3: Artemis/SLS launch. Downloads: 3 (at cap). Requests: 16 (<40 cap).

### K3 SCRIPT + LEDGER + SHORTS (DONE)
- docs/openmontage/evidence/ARTEMIS_CLAIM_LEDGER.md — 12 claims (ARTEMIS-01..12); load-bearing claims TWO_SOURCES (multiple distinct NASA records agree); hardware-detail claims SINGLE_SOURCE honestly flagged; all paraphrased from NASA image-library descriptions, page/record cited; nasa.gov HTML rate-limited (429) and not used.
- docs/openmontage/slice/ARTEMIS_FULL_SCRIPT_v0.md — 6 beats, 19 sentences, ≈3.5–4 min, claim_ids on every sentence, 4 single-source sentences flagged.
- docs/openmontage/slice/ARTEMIS_CLAIM_IDS.json — 21 entries.
- docs/openmontage/package/ARTEMIS_SHORTS_PLAN.md — 45s Shorts cut plan, EDL, source cards, static_by_design cards.
- QC: claim_ids PASS (21/21), claim_ids_resolve PASS (21/21).

### K4 tooling (DONE)
- Generalized qc.py `_parse_claim_ledger` regex from CID-only (`CID-\d+`) to any `<ID>-<digits>` (e.g. ARTEMIS-01); CID regression re-verified PASS (52/52 claim_ids + claim_ids_resolve).
- py_compile exit 0 on changed files; ruff not available.

### K4 CLOSE (DONE — this session)
- MASTER_RUN_STATE.md, OWNER_ACTIONS.md, CHANGELOG.md updated.

## 2026-10-19 — Milestone Z (Kilo), factory scope only (docs/tools/config)

### Z1 VOICE ENV (DONE)
- Isolated python3.12 venv at /tmp/kilo/z1_venv (NOT system 3.14.2); pinned kokoro==0.2.2, misaki==0.7.17, soundfile==0.14.0, torch==2.6.0+cpu; Kokoro-82M weights into gitignored /tmp/kilo/hf_cache; 10s sample synthesized (14.625s, RTF 1.38 CPU); finish_audio PASS (loudnorm to -14 LUFS); qc.py PASS (decode/loudness/silence/freeze; ffprobe_streams FAILED expected — audio-only).
- docs/openmontage/Z1_VOICE_ENV.md written; docs/openmontage/z1_voice_venv.requirements.txt pinned.
- Blocker: venv + weights wiped mid-session; HF xet CAS + CDN unreachable from this network.

### Z2 ARTEMIS DRAFT (DONE, 3:05)
- 20-sentence Kokoro narration (af_heart), stable-ts/whisper-tiny word alignment (387 words), 20-cue subtitles, 8 original graphics cards with claim_ids, EDL with per-cut rationale + static_by_design cards, 4x16s HD inserts from NASA GX010506 (1920x1080, used unscaled).
- qc.py with ALL inputs: PASS (11 PASS + 1 REVIEW freezedetect on static_by_design cards).
- NOT_PUBLISHABLE: voice-license residual risk, no frame-level review, NASA insignia clearance pending, synthetic-voice disclosure pending, 4 single-source claims flagged (ARTEMIS-02, ARTEMIS-04, ARTEMIS-12).
- docs/openmontage/slice/artifacts/* (qa_report.json, subtitles.srt, edit_decisions.json, narration_manifest.json, credits.txt, rights_records.json, claim_ids.json, word-timestamps.json).
- tools/qa/qc.py claim_ids_resolve now splits comma-separated claim_ids (regression test added).
- Video in gitignored projects/slice_artemis_v0/renders/ — not committed.

### Z3 PIPELINE (DONE code+tests, BLOCKED smoke)
- scripts/run_episode.py: claim_ledger_check → script_validation → footage_manifest_rights → narration → subtitles → edl → render → finish_audio → qc → package_draft. Per-stage checkpoint with wall-time + disk logging, resume of OK stages, idempotency via output hash, fail-closed (any unverified stage = BLOCKED, non-zero exit), 800MB disk budget fail-closed, STAGE_REGISTRY pluggable for fake-stage tests.
- scripts/z3_kokoro_narrate.py, scripts/z3_subtitles.py: Kokoro-82M CPU narration + stable-ts alignment helpers.
- tests/test_run_episode.py: 6 orchestration tests pass (resume skips done stages, mid-chain failure blocks, unknown claim_id blocked, rights unknown blocked, hash mismatch triggers rerun, disk threshold blocks).
- Real smoke test BLOCKED — Kokoro-82M weights unreachable (same HF network block as Z1).

### Z4 CHAPTER MODE (DONE code+tests+spec, BLOCKED dry-run)
- scripts/run_episode.py --chapters: split script into <=6 min chapters, per-chapter checkpoint+resume, disk budget check before each chapter, xfade concatenation, final loudness pass on final file.
- tests/test_run_chapters.py: 5 chapter mode tests pass (split respects max duration, single chapter when short, per-chapter checkpoint+resume, chapter failure blocks remaining, disk budget before each chapter).
- docs/openmontage/LONGFORM_SPEC.md: 40-50 min targets (7-9 chapters, 80-120 claims, 35-45 min usable visuals), added-value gate per chapter (narration share >=60%, original graphics >=1 per 90s, archive clip <=20s unannotated, still-only <=15s), step ladder 3-4 -> 8-10 -> 15-20 -> 40-50 min with go/no-go driven by owner's YouTube Studio metrics (no invented thresholds).
- Dry-run on Artemis BLOCKED — Kokoro weights unreachable.

### Z5 SERIES PLAN (DONE)
- docs/openmontage/SERIES_PLAN.md: 12 ranked space topics; per topic: HD clip count, rights_basis, primary docs reachable, est. usable minutes, max feasible length.
- Demand from T1 (MEASURED: 5/300 breakouts, weak signal — only 1 English on-topic breakout = JWST first images); footage from T5/T12 (ESTIMATE/MEASURED); primary docs from T15 (MEASURED Apollo 9/10/11 NASA public domain).
- SpaceX Tier C excluded (no PD footage, copyrighted). No demand claims beyond measured data.

### Z6 SCRIPTS (DONE)
- Apollo test flights / Saturn V (13 claims), ISS (12 claims), JWST (12 claims) — full scripts (3-5 min each) + claim ledgers + 45s Shorts plans.
- Apollo: 4 TWO_SOURCE + 9 SINGLE/UNVERIFIED flagged. ISS/JWST: all UNVERIFIED pending NASA primary page verification.
- claim_ids resolve check: ALL OK — every script sentence's claim_id resolves to its ledger, all SINGLE/UNVERIFIED claims flagged in scripts.

### Z7 PACKAGING (DONE)
- docs/openmontage/slice/artifacts/ARTEMIS_PACKAGING.md: 3 truthful titles, 3 thumbnail text options, 1280x720 PNG thumbnails (gitignored projects/slice_artemis_v0/thumbnails/, from own graphics cards + NASA Causeway frame, no emblem/people), description with chapters + credits block, synthetic-voice disclosure checklist citing https://support.google.com/youtube/answer/14328491 with paraphrased wording and owner action items.

### Z8 REVIEW PACK (DONE)
- docs/openmontage/REVIEW_PACK.md: files a fresh session must read (Z_STATE.md, Z1_VOICE_ENV.md, SERIES_PLAN.md, LONGFORM_SPEC.md, ARTEMIS_PACKAGING.md, run_episode.py, test files, claim ledger, example script), verification commands with observed exit codes (29 fast tests pass exit 0, py_compile OK), EVALS.md task status, paste-ready read-only reviewer prompt.

### Z9 CLOSE (this session)
- OWNER_ACTIONS.md, MASTER_RUN_STATE.md, this CHANGELOG, LESSONS.md updated; stop Codespace commands printed.

## 2026-10-19 — Milestone I (Kilo), factory scope only

### I1 SECOND SOURCES (DONE)
- Fetched + fully extracted FAA/CT-87/10 (DOT/FAA/CT-87/10, rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf, 92 pages, curl -L + pypdf). Confirmed CID-06 (150 ft commitment, p.45/75), CID-10 (cutter/right inboard engine/ignition, p.16-19), CID-15 (overall success, p.7/38), FAA p.32 fire findings (CID-23..28). Upgraded CID-06, CID-10, CID-15 to TWO_SOURCES. Recorded contradiction CID-20 (FS: ineffective) vs CID-25 (FAA p.32: reduced intensity attributed to AMK). Ledger now 50 claims. Paraphrase only, page recorded per claim.

### I2 CLAIM_ID RESOLUTION (DONE, test-first)
- Added qc.py `claim_ids_resolve` check (every claim_id resolves to CID_CLAIM_LEDGER.md; fails on unknown ids and SINGLE_SOURCE claims without a flag) + `claim_ledger_path` input. Demonstrated red then green (PASS 52/52). Regenerated CID_FULL_CLAIM_IDS.json with source_flags. Added lib/footage_classifier.py + tests/lib/test_footage_classifier.py (E5 PASS). Full fast suite exit 0; py_compile exit 0; ruff not available. EVALS.md updated (E5 PASS; E4 claim_ids_resolve).

### I3 BEAT B6 (DONE)
- 0 aftermath footage. Evaluated (a) keyless images.nasa.gov search — not viable (HTML only); (b) original graphics only (Key Numbers + Lessons Learned cards with claim_ids) — implemented; (c) merge into B5 — declined. Documented in CID_BEAT_COVERAGE.md §5; B6 graphics-only, LIMITED. Viability gate satisfied.

### I4 DOC FIXES (DONE)
- Kokoro-82M license corrected: weights/code Apache-2.0 clear; UNKNOWN only synthetic-data training provenance residual risk. Fixed in OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CID_PACKAGE_DRAFT.md, REVIEW_QUEUE.md. FOOTAGE_QUALITY.md NASA email says "for a YouTube documentary channel (monetization possible)".

### I5 FULL-VIDEO DRAFT (BLOCKED)
- Kokoro-82M not installed in this environment; no cleared alternative TTS without secrets; Piper lessac BLOCKED. No narration synthesized; finish_audio/qc.py all-media-inputs not run. Wrote docs/openmontage/slice/artifacts/FULL_DRAFT_STATUS.md (EDL plan, NOT_PUBLISHABLE reasons). Never media.

### I6 CLOSE (DONE — this session)
- MASTER_RUN_STATE.md, OWNER_ACTIONS.md, CHANGELOG.md, EVALS.md updated.

## 2026-10-18 — Milestone H (Kilo), factory scope only

### H1 FULL SCRIPT (DONE)
- Extended docs/openmontage/evidence/CID_CLAIM_LEDGER.md with 20 new claims (CID-31 to CID-50), all paraphrased from NASA Facts FS-2009-02-003-DFRC fetched + fully extracted this session (curl -L + pypdf); TM-4084 not re-fetched (NTRS blocked from sandbox) so all new claims honestly marked SINGLE / name SINGLE; CID-25 CONTRADICTION vs CID-20 restated; no intensity claim used. Ledger now 50 claims.
- Rewrote docs/openmontage/slice/CID_FULL_SCRIPT_v0.md: 6 beats (preparation, remote piloting, approach, impact, fire, aftermath), 40 sentences, every sentence carries claim_id(s), single-source sentences flagged, ~5.5-6.5 min narration estimate, gap to 6-8 min noted.
- Regenerated docs/openmontage/slice/CID_FULL_CLAIM_IDS.json (52 entries).
- QC claim_ids check: PASS (52/52 sentences have claim_id), ffprobe 6.1.1.

### H2 FOOTAGE COVERAGE (DONE)
- Rewrote docs/openmontage/footage/CID_BEAT_COVERAGE.md: corrected asset inventory — keyless archive.org advancedsearch re-confirmed mediatype this session: 8 NIX video clips (EM-0004-01/02, LV-1998-00090/91/92/93/96/98, all 320x240 h.264, NASA/Dryden or NASA/Langley, source_policy_us_gov) + 5 NIX photos (EC84-31805/31806/31809, ECN-31808, ECN-28307 — mediatype=image, NOT video, correcting prior doc) + 5 NASA Armstrong stills (nasa.gov gallery, up to 1040x832); all source_policy_us_gov, no third-party credit.
- 4 third-party assets REJECTED per RIGHTS_MODEL.md.
- Keyless gap search: images.nasa.gov search returns web-app HTML only (not parseable); archive.org aftermath/investigation/wreckage video search = 0 results → B6 aftermath gap confirmed (stills + graphics card only).
- Beat coverage: B1-B5 GOOD/EXCELLENT, B6 LIMITED; all 6 beats covered → proposed viability gate (>=6 beats with >=1 usable asset) = GATE_READY with B6 LIMITED.
- Downloads: 0 successful test files (1 derivative download attempted for LV-00093 returned HTTP 404, recorded as ERROR not success); within the 3-file cap; earlier verified downloads (EM-0004-01, LV-00090, LV-00092, LV-00098) remain decodable.

### H3 HARDENING (DONE)
- Regression tests for unknown/missing source/claim ID rejection already present: tests/factory/test_artifact_id_resolution.py (19 passed, exit 0 — fabricated source_id/evidence_id/scene_id/asset_id caught) and tests/tools/test_rebuild_slice_assets.py (13 passed, exit 0 — missing/empty claim_id rejected, sha256 fail-closed).
- EVALS.md recorded: E1 PASS, E2 PASS, E3 PASS, E4 PASS, E5 NOT_CHECKED (no footage-classifier test).
- py_compile exit 0 on changed/test files; ruff not available.
- Full fast suite exit 0: test_qc_tool 13, test_finish_audio 5, test_piper_tts 6 (3 skipped), test_rebuild_slice_assets 13, test_artifact_id_resolution 19, test_artifact_schemas 41.

### H4 THUMBNAILS (DONE)
- Generated 3 candidates at 1280x720 PNG in gitignored projects/slice_cid_v0/thumbnails/ (thumb_01_impact ECN-31803, thumb_02_approach EC84-3167-A, thumb_03_fireball ECN-31808): PIL composite of NASA still + darkened overlay + large bold title/subtitle + attribution bar; no NASA emblem, no people, no third-party credit, large readable text; NOT committed.
- docs/openmontage/package/THUMBNAIL_NOTES.md already describes them (unchanged).

### H5 TOPIC BACKLOG (DONE)
- docs/openmontage/audit/TOPIC_BACKLOG.md: read-only keyless probe for X-15 and XB-70; video count per beat, rights_basis, reachable primary docs (NTRS blocked); both LOW viability (pilot-flown, no crash/fire demonstration); CID remains only production-ready topic; no demand claims.

### H6 CLOSE (DONE — this session)
- OWNER_ACTIONS.md, MASTER_RUN_STATE.md, this CHANGELOG updated; stop Codespace commands documented below; AGENTS.md untouched (owner's uncommitted modification preserved); .env.example untouched.
- Rollback: `git revert` of this session's commit on branch `factory/business-documentary-pilot`.
- Network/download budget this session: 8 requests total (pip pypdf, fs_cid.pdf, pytest, 2 archive.org advancedsearch, images.nasa.gov, 1 LV-00093 derivative 404) — well under the 40 cap; all keyless/$0; curl -L for downloads; no paid routes, no secrets printed; no AI upscaling; no publishing.

## 2026-10-18 — M1 selective merge of KILO_CODE_YOUTUBE_FACTORY_MASTER.md
- Accepted: docs/openmontage/MERGE_AUDIT.md (Table A skills + Table B rules vs RIGHTS_MODEL.md/QA_SPEC.md/AGENTS.md/plan v3.2); docs/agent-improvement/LESSONS.md (6 evidence-backed entries); docs/agent-improvement/EVALS.md (5 fixed tasks); .kilo/skills/kilo-self-improvement/SKILL.md (EVALS.md reference, project-level only); docs/openmontage/youtube-publishing-analytics-STUB.md (stub only, no OAuth); docs/openmontage/AGENTS_PROPOSED_DIFF.md (proposed, not applied).
- Not accepted: no MCP installs; no global ~/.config/kilo or kilo.json/kilo.jsonc changes; no Remotion activation (render stack = ffmpeg + HyperFrames); AGENTS.md left unmodified (owner's uncommitted change preserved; diff proposed only).
- Evidence: tests pass (test_qc_tool 6/6, test_finish_audio 5/5, test_piper_tts 9/9, test_tts_kaggle 5/5, all exit 0).
- Rollback: `git revert` of the M1 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — Output style rule (project rule)
- Final report max 12 lines, no tables; full detail kept in docs/... and MASTER_RUN_STATE.md.
- Report format: Status | Commit | Done (≤3 bullets) | Failed/NOT_CHECKED (≤3 bullets or "none") | Owner decision needed (≤3 bullets or "none") | Next action (one sentence).
- No restating of task, no per-file lists or per-skill tables; use "details: <path>".
- Never shorten honesty: keep "inline, not independent", real PASS/FAIL/NOT_CHECKED, blockers stated first.
- Apply to every milestone from now on; commit docs only, push non-force; do not touch AGENTS.md.

## 2026-10-18 — F1 fix slice footage quality
- Accepted: rebuilt slice with real archive.org derivatives (clip01 NASA-logo placeholder replaced with real-footage segment 8.0-12.5s); lanczos 1080p+pad crf 18 30fps; finish_audio PASS; qc.py run; rights_records.json + credits.txt + qa_report.json updated; contact sheet 12 frames, logo_visible=false.
- Not accepted: ebur128 FAILED (I=-17.0 LUFS, target -14+/-2, marginal 1 LU below range) → overall qc FAILED. Owner must decide whether to accept or re-run finish_audio.
- Evidence: qc report at projects/slice_cid_v0/qa_report.json (gitignored, not committed); 12/12 checks accounted (PASS/NOT_RUN/1 FAILED).
- Network/download budget: 8/20 requests, ~7.6MB/400MB, curl -L, no new installs, no paid routes, no secrets.
- Rollback: `git revert` of the F1 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — F1 redo (v2) improve slice footage quality
- Accepted: re-read archive.org metadata for 4 items (4/25 requests); all only 320x240, no higher-res derivative → keep all 4, none replaced. Rebuilt slice lanczos 1920x1080+pad crf 18 30fps, clip01 = real footage 0-4.5s per owner. finish_audio PASS. qc.py: freezedetect FAILED (max freeze 2.43s > 2.0s), ebur128 FAILED (I=-17.0 LUFS, marginal); remaining checks PASS/NOT_RUN. Before/after bitrate table recorded. rights_records.json + credits.txt + qa_report.json updated.
- Not accepted: overall qc FAILED (freezedetect + ebur128). Owner must decide whether to accept or investigate/re-run.
- Evidence: qc report at projects/slice_cid_v0/rebuild2/qa_report_f1.json (gitignored, not committed).
- Network/download budget: 4/25 requests, ~7.6MB/600MB, curl -L, no new installs, no paid routes, no secrets. Temp files deleted after commit.
- Rollback: `git revert` of the F1 redo commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — F2 improve slice footage quality
- Accepted: layout fix (320x240 → 2x integer 640x480 centered on dark background + thin frame + source card, lanczos crf 18 30fps, audio chain kept); re-read archive.org metadata for 4 items (all 320x240, no higher-res → keep all 4); source probe (archive.org + NASA images API; no higher-res CID video >640x480 available); freeze investigation (frame-compare EM-0004-01.mp4: source still 0-6s, motion from ~t=6s → clip01 rebuilt from motion segment 6.0-10.5s, frozen portion cut, clip kept); finish_audio PASS; qc.py: freezedetect PASS (0.00s); silencedetect FAILED (0.1006 > 0.10 borderline); ebur128 FAILED (-17.1 LUFS marginal); rights_records.json + credits.txt + qa_report.json updated; EBUR128_THRESHOLD_PROPOSAL.md created (docs only, no qc.py change).
- Not accepted: overall qc FAILED (silencedetect borderline + ebur128 marginal). Thresholds NOT changed in qc.py; ebur128 narration-only proposal in docs only.
- Evidence: qc report at projects/slice_cid_v0/rebuild3/qa_report_f2.json (gitignored, not committed).
- Network/download budget: ~11/25 requests, ~7.6MB/600MB, curl -L, no new installs, no paid routes, no secrets. Temp files deleted after commit.
- Rollback: `git revert` of the F2 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — F3 still-image-led slice
- Accepted: built stills-led slice (5 NASA Armstrong CID photos, zoompan max 1.15x, 1080p, letterboxed, no upscale beyond source); archive inserts clip01/02/03 (3-6s) in 2x framed layout; 2 original graphics cards (flight-path/timeline + key-numbers with claim_ids); finish_audio PASS; rights_records.json + credits.txt + qa_report.json updated; FOOTAGE_QUALITY.md written (findings, draft email to ARC-DL-archives@mail.nasa.gov, AI-upscale NEEDS OWNER APPROVAL as 4th component).
- Not accepted: qc.py overall FAILED (freezedetect on static title cards, silencedetect no-narration, ebur128 quiet). Thresholds NOT changed in qc.py. AI upscaling NOT applied (needs owner approval).
- Evidence: qc report at projects/slice_cid_v0/f3/qa_report_f3.json (gitignored, not committed).
- Network/download budget: ~17/25 requests, ~7.6MB/300MB, curl -L, no installs, no AI upscaling, no paid routes, no secrets.
- Rollback: `git revert` of the F3 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — F4 still-image-led slice + Kokoro narration
- Accepted: rebuilt slice with Kokoro-82M narration (S1-S7 only, S8 BLOCKED/omitted, 46.0s) laid over stills-led visuals with zoompan, archive inserts in 2x framed layout, 2 original graphics cards; subtitles.srt regenerated; finish_audio PASS. Added static_by_design per-segment exemption to qc.py freezedetect (edit_decisions.json with cuts[] + static_segments[]); test-first 2 new tests (red→green); all 9 qc tests pass. qc.py run with all inputs: overall PASS, freezedetect REVIEW (static title cards), ebur128 PASS (I=-15.3 LUFS). rights_records.json + credits.txt updated. Contact sheet 12 frames.
- Not accepted: qc.py thresholds NOT changed. S8 (CID-13) omitted (BLOCKED, load-bearing). AI upscaling NOT applied.
- Evidence: qc report at projects/slice_cid_v0/f4/qa_report_f4.json (gitignored, not committed); tests pass (test_qc_tool 9/9, test_finish_audio 5/5, test_piper_tts 9/9, test_tts_kaggle 5/5, all exit 0).
- Network/download budget: no new downloads for F4 (sources reused). curl -L. No new installs, no AI upscaling, no paid routes, no secrets.
- Rollback: `git revert` of the F4 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — F5 moving footage + stills + Kokoro narration
- Accepted: rebuilt slice with moving footage for approach/impact/fireball (EM-0004-01, LV-00090, LV-00092 as 2x framed inserts); stills for prep/context; 2 graphics cards retained; Kokoro-82M narration S1-S7 (46.0s); finish_audio PASS; qc.py overall PASS with all inputs (freezedetect REVIEW on static_by_design cards, ebur128 PASS at -15.3 LUFS). Owner review recorded in REVIEW_QUEUE.md (4 clips USABLE_FOR_SLICE). rights_records.json + credits.txt updated. FOOTAGE_QUALITY.md updated to F5 state (email draft corrected, NASA stills max ~1040x816 noted, AI-upscale NEEDS OWNER APPROVAL). OWNER_ACTIONS.md updated.
- Not accepted: qc.py thresholds NOT changed. S8 (CID-13) omitted. AI upscaling NOT applied. Full video full-clip review still pending.
- Evidence: qc report at projects/slice_cid_v0/f5/qa_report_f5.json (gitignored, not committed); tests pass (test_qc_tool 9/9, test_finish_audio 5/5, test_piper_tts 9/9, test_tts_kaggle 5/5, all exit 0).
- Network/download budget: 13/15 requests, ~14MB/300MB, curl -L, no installs, no AI upscaling, no paid routes, no secrets. Temp files deleted after commit.
- Rollback: `git revert` of the F5 commit on branch `factory/business-documentary-pilot`.

## 2026-10-18 — Milestone G (100-minute session close)

### G1 PORTABILITY (DONE)
- scripts/rebuild_slice_assets.sh: re-downloads 8 assets with curl -L + sha256 verify from committed manifest
- docs/openmontage/HANDOFF_NEW_ACCOUNT.md: branch/clone/deps/secrets/exact steps for new account
- docs/openmontage/assets/CID_SLICE_MANIFEST.json: COMMITTED manifest (URLs + sha256 + rights for all 8 assets)
- Dry-run PASS (EC84-3167-A still, sha256 verified)
- Non-git deps: curl, sha256sum, ffmpeg/ffprobe, python3, kokoro + misaki, espeak-ng, Kokoro weights ~313 MB (Hugging Face), kaggle CLI 2.2.4 (P3 only)
- Secret: KAGGLE_API_TOKEN (Codespaces secret, name only)

### G2 EVIDENCE (DONE)
- CID_CLAIM_LEDGER.md: CID-13 now TWO_SOURCES (FS + FAA/CT-87/10 both read); CONTRADICTION note (FS "no reduction in propagation/intensity" vs FAA p.32 "reduced intensity attributed to AMK"); no intensity claim in script
- CID_SLICE_SCRIPT_v0.md: S8 unblocked with new wording ("At full scale the modified fuel did not prevent a massive fuel-fed fire, and the FAA ended its attempts to require the additive.")
- QC claim_ids check: PASS (9/9 sentences have claim_id)

### G3 SLICE v2 (DONE)
- Rebuilt slice with Kokoro narration S1-S8 (56.0s), moving footage inserts (EM-0004-01, LV-00090, LV-00092), 2x framed layout, 2 graphics cards, S8 with FAA source card
- finish_audio PASS; qc.py overall PASS with all inputs (freezedetect REVIEW on static cards, ebur128 PASS at -15.2 LUFS)
- Thresholds NOT changed in qc.py

### G4 PACKAGING DRAFT (DONE)
- docs/openmontage/package/CID_PACKAGE_DRAFT.md: 3 title options, description with chapters, credits/attribution block, pre-publish checklist; all NOT_PUBLISHABLE

### G5 CLOSE (DONE)
- OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md updated
- Stop Codespace commands documented
- AGENTS.md untouched (owner's uncommitted modification preserved)
- Rollback: `git revert` of the G commit on branch `factory/business-documentary-pilot`

## 2026-10-18 — Milestone H (100-minute autonomous session close)

### H1 FULL-VIDEO PLAN (DONE)
- Extended CID_CLAIM_LEDGER.md with CID-17..CID-30 (14 new claims; TWO_SOURCES/SINGLE_SOURCE honestly marked; CID-25 CONTRADICTION noted vs CID-20; no intensity claim in script)
- Wrote docs/openmontage/slice/CID_FULL_SCRIPT_v0.md — 6 narrative beats, 34 sentences, every sentence with claim_ids, single-source sentences flagged
- Created docs/openmontage/slice/CID_FULL_CLAIM_IDS.json (35 entries)
- QC claim_ids check: PASS (35/35 sentences have claim_id)
- ~3-4 min of sourced material; noted gap to 6-8 min without additional evidence

### H2 FOOTAGE COVERAGE (DONE)
- Wrote docs/openmontage/footage/CID_BEAT_COVERAGE.md — 6 beats mapped to 12 NIX clips + 5 NASA stills + 2 graphics cards; all 6 beats covered (B6 aftermath LIMITED)
- Searched archive.org (17 CID docs) and NASA images API (HTML only); applied RIGHTS_MODEL.md (4 third-party assets REJECTED)
- Proposed viability-gate wording (6/6 beats = GATE_READY)
- Downloads: 0 new (metadata reads only)

### H3 HARDENING (DONE)
- Wrote tests/tools/test_rebuild_slice_assets.py — 6 tests (sha256 logic + claim_ids validation); all pass
- EVALS.md updated (E1-E3 PASS, E4 PASS, E5 NOT_CHECKED)
- py_compile PASS; ruff not available
- Full fast suite: 26 tests pass

### H4 THUMBNAIL (DONE)
- Generated 3 thumbnail candidates at 1280x720 PNG (gitignored, not committed)
- Wrote docs/openmontage/package/THUMBNAIL_NOTES.md

### H5 TOPIC BACKLOG (DONE)
- Wrote docs/openmontage/audit/TOPIC_BACKLOG.md — X-15/XB-70 LOW viability; CID remains only production-ready topic
- No demand claims; read-only keyless probe

### H6 CLOSE (DONE)
- OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md updated
- Stop Codespace commands documented
- AGENTS.md untouched (owner's uncommitted modification preserved)
- Rollback: `git revert` of the H commit on branch `factory/business-documentary-pilot`

## 2026-10-18 — R2 Kokoro narration + slice rebuild

- Accepted: Kokoro-82M (af_heart) synthesized S1-S8 from CID_SLICE_SCRIPT_v0.md (52.80s, RTF 1.2860) in output/kokoro_venv (gitignored venv). finish_audio PASS: I=-15.2 LUFS (target -14+/-2), TP=-4.3 dBTP. subtitles.srt regenerated. narration_manifest.json recorded.
- Accepted: rebuilt 52.80s slice from verified 8 assets in projects/slice_cid_v0/ (sha256-verified via rebuild_slice_assets.sh). 5 NASA stills zoompan (max 1.15x, continuous motion), 3 archive inserts as 640x480 2x-framed inserts with source cards, 1 original S8 graphics card (FAA source overlay + claim_ids). S8 static card at 48.0-52.80s declared static_by_design. edit_decisions.json recreated with per-cut rationale.
- Accepted: qc.py with ALL inputs → overall PASS. 11/12 PASS, freezedetect REVIEW (static_by_design card). ebur128 PASS I=-15.2 LUFS. Thresholds NOT changed. duration_vs_script PASS (drift 0.00s), subtitle_sync PASS (drift 0.00s), claim_ids PASS (8/8), rights_basis PASS (9/9).
- Accepted: Small project files committed to docs/openmontage/slice/artifacts/: edit_decisions.json, narration_manifest.json, subtitles.srt, credits.txt, rights_records.json, qa_report.json, claim_ids.json. Media (mp4/wav/png) NOT committed (gitignored projects/).
- Not accepted: freezedetect REVIEW (not FAILED) on static S8 card — acceptable per static_by_design exemption, owner may review.
- Evidence: qc report at projects/slice_cid_v0/qa_report.json (gitignored); tests pass (test_rebuild_slice_assets.py 13/13 exit 0).
- Network/download budget: Kokoro weights ~313 MB one-time from Hugging Face; no new asset downloads. No AI upscaling. No paid routes. No secrets printed.
- Rollback: `git revert` of the R2 commit on branch `factory/business-documentary-pilot`.

