# AUDIT_1_REPO_MAP — OpenMontage repository map

Read-only audit. No commits, pushes, or file modifications were made except this new audit file.
Date: 2026-11-06. Active branch: `kilo/mega-100`.

## 1. Branches and recent commits

### `git branch -a`
```
* kilo/mega-100
  remotes/origin/HEAD -> origin/main
  remotes/origin/factory/business-documentary-pilot
  remotes/origin/kilo/mega-100
  remotes/origin/main
```

### `kilo/mega-100` — `git log --oneline -20`
```
22c8844 Add files via upload
2e9ddfc feat: полная фабрика OpenMontage — оркестратор, 13 стадий, чекпоинты, категории A/B/C
81e36c3 K3 v3 DONE: 6 вариаций одной персонажа через якорь-референс
cee8043 Fix v3 kernel: sequential_cpu_offload + float16-first for T4 VRAM
284b74c Fix CUDA OOM in v3 kernel: expandable_segments + empty_cache between variations
734f670 feat: категория A готова к запуску, курс для владельца (B2)
cd13f0d Fix indentation error in v3 kernel (merged comment+for loop)
e98f7d0 K3 v3: anchor reference + identity variation kernel
4cd470b feat: инфраструктура автономной фабрики (категория A)
4a7704c RUN_STATE: K1+K2 v2 помечен DONE, владелец выбирает из v2 листа
a754865 Fix kernel title slug for Kaggle push
1d27412 K1+K2 v2: перегенерация кандидатов ведущего с обновлённым стилем
d59bb56 Обновить стиль ведущего под целевой ориентир (чиби, глаза с бликом, текстура на одежде)
9d91197 Установлен плагин Ponytail (DietrichGebert/ponytail, MIT, v5.3.2)
e796ef0 Add files via upload
3324f41 K5: competitor analysis stage added (BLOCKED pending owner links)
4bbe2fb K3+K4+S12: 78 кадров Klein, контактные листы, финальная сборка v4
4a51923 K3: shot_list.json + 3 Kaggle ядра для кадров FLUX.2-klein-4B
95d573a S12: финальная сборка пилота через ffmpeg (без Remotion)
c9100ba K1+K2 DONE: 8 кандидатов ведущего сгенерированы FLUX.2-klein-4B
```

### `origin/factory/business-documentary-pilot` — `git log --oneline -20`
```
9ab0e6d Add files via upload
850139f Add files via upload
5dd325b F1-fix: config thresholds, every claim_id, generic EDL, chapter parser, pytest scope
d53e87b S7: blind pack and tally support a 2-model pack when a model is blocked
a49924d S7: runner option to cast the VAE to fp32 before offload hooks (Z-Image black frames)
cfc0e65 Merge remote-tracking branch 'origin/factory/business-documentary-pilot' into factory/business-documentary-pilot
c126830 F0: read-only factory gap audit + spec change requests
c8d7237 S7: zimage attempt 2 black frames (fp16 VAE NaN); attempt 3 forces fp32 VAE decode
a6a76a2 S7: zimage attempt 1 blocked by CUDA OOM; attempt 2 adds CPU offload via new --load-config/--ladder flags
0f2336a S7: scope the torchao pin test to the live ladder rungs
3aa3bef S7: update ladder test for the renamed torchao-pinned stacks
2b299e1 S7: report section 2 - attempts log for SDXL and klein
8841f78 S7: pack-root staging helper with sha256 verification (survives /tmp wipes)
f2baa35 S7: klein run DONE (10/10 verify PASS), rubric review sheet + writer, state update
c7bb49c S5: private kernel slug (shared slug overwritten by parallel S7), klein vendor class + CPU offload, zimage install ladder
3871444 S7: fix bridge verify staging, rework install ladder after SDXL rung findings, update state
93d8791 S7: agent assessment aggregator, kernel watcher, report skeleton
dcb5765 S7: 3-model bakeoff harness (30-render test set, Kaggle runner, QC, blind pack, tally)
696eb6f Add files via upload
ac13463 S5: probe classes per model; lesson on 3 harness failures (global/JSON-null/blanket import)
```

## 2. File trees (committed)

### `kilo/mega-100` — 3252 files
Top-level counts (top 15):
```
  996 .agents
  504 tools
  482 docs
  432 .claude
  226 tests
  170 skills
   90 scripts
   50 remotion-composer
   50 .kilo
   43 schemas
   30 ink-theater
   24 lib
   15 pipeline_defs
   13 .github
   11 backlot
```
Full list: `git ls-tree -r --name-only kilo/mega-100`

### `origin/factory/business-documentary-pilot` — 2594 files
Top-level counts (top 15):
```
  996 .agents
  432 .claude
  258 docs
  225 tools
  193 tests
  170 skills
   48 remotion-composer
   42 schemas
   41 .kilo
   38 scripts
   30 ink-theater
   24 lib
   14 pipeline_defs
   13 .github
   11 backlot
```
Full list: `git ls-tree -r --name-only origin/factory/business-documentary-pilot`

## 3. Branch comparison

- Merge base: `5dd325b` (F1-fix commit on factory).
- `git rev-list --left-right --count kilo/mega-100...origin/factory/business-documentary-pilot` → `87 2` (kilo 87 commits ahead, factory 2 ahead).
- Neither branch is an ancestor of the other.
- Common files: 2592.
- Only in kilo: 660 (grouped by top-level: tools 279, docs 224, tests 73, scripts 34, lib 24, root artifacts/logs ~26).
- Only in factory: 2 — `HOST_CHARACTER.md`, `OpenMontage_ALL_IN_ONE_v2.md`.
- Common files differing in content (43):
```
.gitignore
AGENTS.md
config/qc_thresholds.json
docs/agent-improvement/EVALS.md
docs/agent-improvement/LESSONS.md
docs/openmontage/FACTORY_GAP_AUDIT.md
docs/openmontage/S5_STATE.md
docs/openmontage/S7_STATE.md
docs/openmontage/SPEC_CHANGE_REQUESTS.md
docs/openmontage/VOICE_DECISION.md
docs/openmontage/image_gen/BAKEOFF_S7.md
docs/openmontage/image_gen/LICENSE_EVIDENCE.md
docs/openmontage/image_gen/S7_AGENT_REVIEW.csv
docs/openmontage/niches/speculative_evolution/STYLE_BIBLE.md
remotion-composer/src/Root.tsx
scripts/ci_fast_suite.py
scripts/rebuild_slice_assets.sh
scripts/run_episode.py
scripts/s5_blind_pack.py
scripts/s5_checks.py
scripts/s5_tally.py
scripts/s7_agent_assessment.py
scripts/s7_blind_pack.py
scripts/s7_fetch.py
scripts/s7_review_write.py
scripts/s7_stage_pack_root.py
scripts/s7_tally.py
tests/test_run_episode.py
tests/test_s5_blind_pack.py
tests/test_s5_checks.py
tests/test_s5_runner.py
tests/test_s5_tally.py
tests/test_s7_blind_pack.py
tests/test_s7_stage_pack_root.py
tests/test_s7_tally.py
tests/tools/test_illustration_qc.py
tests/tools/test_qc_tool.py
tools/illustration/illustration_batch.py
tools/illustration/illustration_qc.py
tools/kaggle_bridge/s4_bakeoff_run.py
tools/kaggle_bridge/s5_bakeoff_run.py
tools/kaggle_bridge/s7_bakeoff_run.py
tools/qa/qc.py
```
- 3-dot diff `kilo/mega-100...origin/factory/business-documentary-pilot` (factory side since merge base) added only the 2 unique files above (8092 insertions).

## 4. OPENMONTAGE_MASTER_CONTEXT1.md / Remotion-Stickman pipeline

- `OPENMONTAGE_MASTER_CONTEXT1.md`: ОТСУТСТВУЕТ В РЕПО (checked in `kilo/mega-100`, `origin/factory/business-documentary-pilot`, `origin/main`).
- Remotion/Stickman pipeline file: no committed file describing a Remotion/Stickman pipeline exists in either branch. Working tree (uncommitted) contains `docs/STICKMAN_OPENMONTAGE_INTEGRATION_PLAN.md`, `docs/STICKMAN_RIG_ARCHITECTURE.md`, `docs/STICKMAN_RIG_IMPLEMENTATION.md`, `docs/STICKMAN_RIG_TEST_REPORT.md`, `docs/STICKMAN_VIDEO_DIRECTOR_AUDIT.md` and `lib/stickman_*.py`, but these are NOT committed (not in repository). Committed kilo tree has only `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md`.

## 5. Uncommitted changes on active branch `kilo/mega-100`

`git status`: branch up to date with origin/kilo/mega-100. Not staged: 11 modified, 130 untracked. Nothing committed.

### Modified (11)
```
.kilo/kilo.jsonc
FIRST_VIDEO_MASTER_PLAN.md
PROJECT_STATE_HANDOFF.md
docs/OPENMONTAGE_RESUME.md
docs/OPENMONTAGE_WORK_LOG.md
opencode.json
pytest.ini
requirements-pinned.txt
schemas/artifacts/__init__.py
tools/packaging/packaging.py
tools/packaging/rights_records.py
```

### Untracked (130)
```
.kilo/agents/architect.md
.kilo/agents/code-simplifier.md
.kilo/agents/code-skeptic.md
.kilo/agents/devops.md
.kilo/agents/docs-specialist.md
.kilo/agents/python-dev.md
.kilo/agents/security.md
.kilo/agents/test-engineer.md
.kilo/commands/session.md
.kilo/skills/beam-production-orchestrator/SKILL.md
.kilo/skills/youtube-competitor-research/SKILL.md
BROWSER_USE_INTEGRATION_REPORT.md
CDP_MOBILE_INPUT_FINAL_REPORT.md
FLOW_AUTONOMOUS_AUDIT.md
FLOW_FINAL_SECURITY_AUDIT.md
FLOW_FINAL_STABILITY_REPORT.md
FLOW_INTEGRATION_TEST.md
FLOW_MCP_SECURITY_REPORT.md
FLOW_PIPELINE_HARDENING_REPORT.md
FLOW_PRODUCTION_PIPELINE.md
GOOGLE_FLOW_AUTH_FINAL_REPORT.md
GOOGLE_FLOW_AUTONOMY_REPORT.md
GOOGLE_FLOW_CLEAN_REBUILD_REPORT.md
GOOGLE_FLOW_FINAL_ACCEPTANCE_REPORT.md
GOOGLE_FLOW_FINAL_REPORT.md
GOOGLE_FLOW_INPUT_FIX_REPORT.md
GOOGLE_FLOW_NEW_LOGIN_METHOD_REPORT.md
GOOGLE_FLOW_SESSION_MIGRATION_REPORT.md
GOOGLE_FLOW_SHARED_CHROME_REPORT.md
KILO_DEV_KIT_FINAL_AUDIT_REPORT.md
KILO_TOKEN_OPTIMIZATION_REPORT.md
PRODUCTION_RENDER_INTEGRATION_REPORT.md
REMOTE_DESKTOP_FINAL_REPORT.md
VIDEO_PREPRODUCTION_SYSTEM.md
VNC_DIAGNOSTICS.md
XPRA_LOCAL_SCALING_REPORT.md
XPRA_SCREEN_RESOLUTION_REPORT.md
docs/AUDIO_ALIGNMENT_REPORT.md
docs/AUDIO_PRODUCTION_ENGINE.md
docs/AUTONOMOUS_VIDEO_PRODUCTION_GUIDE.md
docs/EDITING_AND_RENDERING_ENGINE.md
docs/EXTERNAL_TOOLING_INTEGRATION.md
docs/FACTORY_IMPLEMENTATION_ROADMAP.md
docs/FACTORY_TECHNICAL_AUDIT.md
docs/FINAL_QC_SYSTEM.md
docs/GFLOW_CLI_COMPLETE_GUIDE.md
docs/IMAGE_GENERATION_ENGINE.md
docs/IMAGE_GENERATION_TEST_REPORT.md
docs/MOTION_ENGINE.md
docs/P4_TEST_REPORT.md
docs/P5_TEST_REPORT.md
docs/PILOT_APPROVAL_PACKAGE.md
docs/PILOT_CREATIVE_REVIEW.md
docs/PILOT_FINAL_QC_REPORT.md
docs/PILOT_OWNER_REVIEW.md
docs/PILOT_PRODUCTION_REPORT.md
docs/PILOT_V2_CREATIVE_REVIEW.md
docs/PILOT_V3_CREATIVE_REVIEW.md
docs/PROJECT_READINESS_AUDIT.md
docs/PROJECT_RELATIONSHIP_NOTE.md
docs/STICKMAN_OPENMONTAGE_INTEGRATION_PLAN.md
docs/STICKMAN_RIG_ARCHITECTURE.md
docs/STICKMAN_RIG_IMPLEMENTATION.md
docs/STICKMAN_RIG_TEST_REPORT.md
docs/STICKMAN_VIDEO_DIRECTOR_AUDIT.md
docs/TOOL_COMPARISON.md
docs/openmontage/pilot/character_contact_sheet.jpg
docs/openmontage/smoke/kokoro_test.mp3
flow_audit/flow_audit.log
lib/asset_registry.py
lib/audio_alignment.py
lib/audio_engine.py
lib/audio_mixing.py
lib/audio_production_engine.py
lib/audio_qc.py
lib/audio_sync.py
lib/batch_scheduler.py
lib/character_consistency_manager.py
lib/edit_decision_engine.py
lib/final_qc.py
lib/flow_integration.py
lib/flow_job_manager.py
lib/gflow_provider.py
lib/gflow_wrapper.py
lib/image_asset_pipeline.py
lib/image_generation_engine.py
lib/image_uniqueness.py
lib/mcp_security_proxy.py
lib/motion_engine.py
lib/preview_system.py
lib/production_manifest.py
lib/production_metrics.py
lib/production_timeline.py
lib/prompt_engineer.py
lib/quality_control.py
lib/recovery_manager.py
lib/release_gate.py
lib/render_engine.py
lib/render_integration.py
lib/scene_planner.py
lib/script_analyzer.py
lib/sentence_segmenter.py
lib/sentence_timeline.py
lib/stickman_continuity.py
lib/stickman_pose_library.py
lib/stickman_rig.py
lib/visual_director.py
schemas/artifacts/production_manifest.schema.json
tests/lib/test_audio_production_engine.py
tests/lib/test_final_qc.py
tests/lib/test_final_qc_v2.py
tests/lib/test_gflow_wrapper.py
tests/lib/test_image_generation_engine.py
tests/lib/test_image_uniqueness.py
tests/lib/test_p4_engine.py
tests/lib/test_p4_render.py
tests/lib/test_sentence_segmenter.py
tests/lib/test_stickman_rig.py
tests/lib/test_v3_improvements.py
tests/test_flow_job_manager.py
tests/test_flow_job_manager_mock.py
tests/test_flow_load.py
tests/test_mcp_security_proxy.py
tests/test_production_render_integration.py
tests/test_video_preproduction_system.py
tests/tools/test_ffmpeg_available.py
tests/tools/test_kokoro_real_smoke.py
tests/tools/test_kokoro_smoke.py
tests/tools/test_youtube_competitor_research.py
tools/analysis/youtube_competitor_research.py
```

## 6. State files and their status

Files found in working tree and committed branches (docs/openmontage/*_STATE.md, STATE/*, OWNER_ACTIONS.md, MASTER_RUN_STATE.md, RUN_STATE.md).

- `docs/RUN_STATE.md` — kilo/mega-100 pilot. S1-S4,S6-S7,S9-S12,S13-S17 DONE; S5 WAITING_OWNER (frame approval), S8 WAITING_OWNER (music), K5 BLOCKED (competitor links), S18 NOT_CHECKED. Pilot-final.mp4 1099.8s, 58.6 MB, h264 1280x720.
- `docs/openmontage/MASTER_RUN_STATE.md` — factory lane master run. Phases P1-P2,P4-P7 DONE; P3 BLOCKED (Kaggle GPU queued, never ran). M (M1-M9) DONE. F1-F5 mostly PARTIAL/DONE. G/H/I/K/Z milestones DONE. R2 DONE. Voice license OWNER_GATED, clip review PARTIAL, NASA insignia pending, synthetic-voice disclosure pending.
- `docs/openmontage/OWNER_ACTIONS.md` — numbered owner actions. Voice license, clip rights, single-source claims, NASA insignia, monetization, Kaggle quota, slice rebuild, publication blockers. Milestones H,I,K,Z,M all marked complete with remaining decisions.
- `docs/openmontage/MEGA_STATE.md` — factory build toward FACTORY_100_SPEC. G0-G6 DONE/PARTIAL, G7 BLOCKED (YouTube API quota), G8-G9,G11-G13 PENDING. Hard rules: $0 only, fail-closed QC, no secrets.
- `docs/openmontage/PIPE_STATE.md` — prompt queue. P0-P4 DONE, P5-P14 PENDING (prompt bodies not supplied). No work started on pending prompts.
- `docs/openmontage/S1_STATE.md` — (read in working tree) S1-S7 of image bake-off: SDXL DONE 13/13 (44.6 s/img), klein DONE 13/13 (25.1 s/img), Z-Image BLOCKED (black frames). Blind pack + tally done. Owner scoring pending.
- `docs/openmontage/S4_STATE.md` — 10-image 3-model bake-off plan: 10 scenes x 3 models, fp16, T4. SDXL DONE 13/13, klein DONE 13/13, Z-Image BLOCKED. Objective checks + blind pack done.
- `docs/openmontage/S5_STATE.md` — 10-image 3-model bake-off: SDXL DONE, klein DONE, Z-Image BLOCKED (fp16 NaN). Blind pack 10 sheets, tally helper verified. Owner scoring open.
- `docs/openmontage/S7_STATE.md` — 3-model bake-off (10 images each): SDXL DONE (10/10, 41.4 s/img), klein DONE (10/10, 24.69 s/img), Z-Image BLOCKED after 4 attempts (fp16 NaN -> black). Agent pick: klein (advisory). Owner blind scoring open.
- `docs/openmontage/S8_STATE.md` — 5-model bake-off: SDXL + klein reused; sdxl-lightning DONE (3.94 s/img), dreamshaper DONE (5.11 s/img), sana-sprint BLOCKED (fp16 NaN). Agent pick: klein. Owner scoring open.
- `docs/openmontage/S10_STATE.md` — 3 visual styles x 6 scenes x 3 seeds = 54 images, single kernel COMPLETE (54/54, 25.08 s/img). Objective checks done. Style winner OWNER_GATED.
- `docs/openmontage/F1FIX_STATE.md` — pipeline correctness fixes: QC thresholds from config (SCR-05), claim_ids_resolve all ids (SCR-06), generic EDL (SCR-07), chapter parser fix, pytest scope. CI fast suite 10/10 PASS.
- `docs/openmontage/Z_STATE.md` — space/astronomy milestone Z (Z1-Z9 DONE). Kokoro narration via kokoro-onnx (HF blocked). Artemis/Apollo9/ISS drafts built, qc PASS. Kokoro HF weights blocker carried; venv+weights wiped, needs restore.
- `docs/openmontage/M_STATE.md` — milestone M. G2 concluded FAILED. M2-M8 DONE (illustration module, niche profiles, museum adapters, motion variety, packaging, review harness, analytics). M9 IN_PROGRESS. M1 ISS v2 complete (25 scenes, qc PASS, NOT_PUBLISHABLE).
- `docs/openmontage/image_gen/G2_STATE.md` — G2 AI image bake-off concluded FAILED (0 images, 2 runs, T4 CPU float32 fallback broken). No further re-push. Owner decision: use GPU-enabled Kaggle or local GPU.

## Reproduce commands
```
git branch -a
git log --oneline -20 kilo/mega-100
git log --oneline -20 origin/factory/business-documentary-pilot
git ls-tree -r --name-only kilo/mega-100
git ls-tree -r --name-only origin/factory/business-documentary-pilot
git diff --stat kilo/mega-100...origin/factory/business-documentary-pilot
git status
```
