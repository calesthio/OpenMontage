# MILESTONE Z state — OpenMontage Kilo (space / astronomy niche)

**Branch:** factory/business-documentary-pilot  
**HEAD:** K complete (8e96cda); Z1-Z9 this session  
**Started / updated:** 2026-10-19  
**Disk:** ~4.6 GB free /workspaces (above 800 MB stop threshold)  
**Rules:** zero-cost only (unknown/unpriced route = BLOCKED), curl -L for downloads, max 60 requests/phase, no paid routes, no AI upscaling, no publishing/upload, no secrets printed/committed, never touch `youtube-niche-finder/` or owner's `.env.example`/`AGENTS.md`. Roles inline, not independent. Venv + weights live outside the repo (/tmp/kilo/*) and are never committed.

## Phase status

| Phase | Status | Evidence | Commit |
|-------|--------|----------|--------|
| Z1 VOICE ENV | DONE | Isolated python3.12 venv at /tmp/kilo/z1_venv. Kokoro-82M via kokoro-onnx 0.6.1 (PyPI, MIT) + ONNX weights from GitHub Releases (thewh1teagle/kokoro-onnx model-files-v1.1, model Apache-2.0). kokoro-onnx==0.6.1, onnxruntime==1.20.1, espeakng-loader==0.2.4, phonemizer==3.4.0. Weights: kokoro-v1.0.onnx (310MB) + voices-v1.0.bin (27MB) in /tmp/kilo/kokoro_onnx_weights/ (gitignored). 10s sample synthesized (15.46s, RTF 1.0), finish_audio PASS, qc.py PASS (ebur128 I=-15.8 LUFS). NOTE: HF xet/CDN blocked — kokoro-onnx route used instead; HF Kokoro weights NOT re-downloaded. | 580d1d9 + z1-onnx |
| Z2 ARTEMIS DRAFT | DONE | 3:05 video, qc.py PASS (11 PASS + 1 REVIEW static_by_design), NOT_PUBLISHABLE. Media under projects/ (gitignored, not committed). | e0739ed |
| Z3 PIPELINE | DONE (smoke OK) | scripts/run_episode.py (10-stage chain, per-stage checkpoint+resume+idempotency via output hash, fail-closed, 800MB disk budget, wall-time/disk logging, STAGE_REGISTRY pluggable). scripts/z3_kokoro_narrate.py (kokoro-onnx route). 6/6 orchestration tests pass. Smoke test on artemis: VERDICT OK (all stages incl. qc PASS, duration drift 0.00s). qc.py claim_ids_resolve generalized to comma-separated IDs (regression test added). | 554ab91 + run_episode edits |
| Z4 CHAPTER MODE | DONE code+tests, dry-run limited | run_episode.py --chapters (per-chapter checkpoint+resume, per-chapter disk budget, xfade concat, final loudness). 5/5 chapter tests pass. docs/openmontage/LONGFORM_SPEC.md (40-50 min, added-value gate, step ladder, owner's YouTube Studio metrics go/no-go). End-to-end render dry-run NOT completed: render EDL is Artemis-hardcoded (fixed 12-cut plan), not chapter-subset; per-chapter render would produce wrong/duplicated content. Documented as known gap. | adfbb9e + run_episode edits |
| Z5 SERIES PLAN | DONE | docs/openmontage/SERIES_PLAN.md — 12 ranked space topics; per topic HD clips, rights_basis, primary docs, usable minutes, max feasible length; T1 demand measured (weak signal); SpaceX Tier C excluded. | ee3db4a |
| Z6 SCRIPTS | DONE | Apollo test flights, ISS, JWST scripts + claim ledgers + Shorts plans; claim_ids resolve ALL OK. | dbd0276 |
| Z7 PACKAGING | DONE | docs/openmontage/slice/artifacts/ARTEMIS_PACKAGING.md (3 titles, thumbnails, description+chapters+credits, synthetic-voice disclosure citing support.google.com/youtube/answer/14328491). | a798db6 |
| Z8 REVIEW PACK | DONE | docs/openmontage/REVIEW_PACK.md (files to read, paste-ready reviewer prompt, verification commands w/ exit codes). 29 fast tests pass exit 0; py_compile OK. | 3476815 |
| Z9 CLOSE | DONE | OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md, LESSONS.md updated; stop Codespace commands printed. | a660c5c + 579ba4c |
| APOLLO 9 (Milestone Y) | DONE | Claim ledger APOLLO9_CLAIM_LEDGER.md (42 claims, all TWO_SOURCES). Script table APOLLO9_FULL_SCRIPT_v0.md rewritten + corrected per apollo9-script-review.md (3 claim-ID fixes: hook A9-001->A9-037, ch7 A9-010->A9-004/A9-019, ch8 sources meta-claim). claim_ids resolve: ALL OK (9/9 resolve, all TWO_SOURCES). Narration synthesized via kokoro-onnx (428.6s, 9 sentences). finish_audio PASS. Subtitles via stable-ts (1037 words, 135 cues). Build: generalized render (no Artemis hardcode), 17 original graphics cards + 2 NASA PD stills, EDL with per-cut rationale, static_by_design. qc.py with ALL inputs: PASS (12 PASS + 1 REVIEW freezedetect on static_by_design cards; duration drift 0.00s). NOT_PUBLISHABLE: no clean native-HD PD Apollo 9 motion footage (splashdown clip CC BY-NC-ND creator=None; 16mm film AI-upscaled/rejected) → graphics+stills only; synthetic-voice disclosure pending; frame/logo review pending (NEEDS_REVIEW); B8 sources card assigned structural claim_id A9-001 (review-flagged meta-claim). Media (.wav/.mp4/.jpg stills) NOT committed. | pending |

| Y1 RENDER GENERALIZATION | DONE | scripts/run_episode.py cmd_render rewritten: EDL + footage path per episode via render_manifest.json (asset_id -> {kind, path}), no Artemis hardcode. graphics_card cuts loop PNGs; archive_insert cuts trim/frame HD footage (pillarbox to 1080p when <1080p). All segments same resolution/fps, concatenated, muxed with narration. 3 new fake-stage render tests pass (generalized build, missing manifest blocked, missing asset blocked). | pending |
| Y2 APOLLO 9 FOOTAGE | DONE (no clean HD motion) | Searched NASA images-api (no Apollo 9 HD video) + archive.org. Splashdown clip 17584-apollo-action-center-footage-mos-vwr is CC BY-NC-ND creator=None → NOT usable (ND blocks editing, non-commercial). 16mm film is AI-upscaled → rejected (no AI upscaling rule). Only clean PD NASA assets: 2 stills downloaded via curl -L with sha256 recorded (AS09-21-3199 LM, GPN-2000-001283 splashdown) into gitignored projects/slice_apollo9/stills/, copied to docs/openmontage/slice/apollo9/stills/. Cap 600MB respected (2.8MB total). | pending |
| Y3 APOLLO 9 BUILD | DONE | Corrected script table (13->9 beats after review fixes), narration re-synthesized kokoro-onnx (428.6s), finish_audio PASS, subtitles stable-ts (135 cues). EDL 19 cuts partitioning full duration, per-cut rationale, all static_by_design. Render: graphics cards + 2 stills, 1920x1080p30 h264/aac, 428.6s. | pending |
| Y4 APOLLO 9 QC | DONE | qc.py with ALL inputs: verdict PASS (12 PASS + 1 REVIEW freezedetect on static_by_design segments = expected, matches Artemis Z2 practice). duration_vs_script PASS (drift 0.00s), subtitle_sync PASS, credits_complete PASS, claim_ids 9/9 PASS, claim_ids_resolve 9/9 PASS, rights_basis 19/19 PASS, added_value PASS. NOT_PUBLISHABLE documented in artifacts/credits.txt. | pending |
| W1 ISS TOPIC SELECTION | DONE | ISS Earth view / cupola selected (Comp 0.5, lowest among ISS sub-topics in T10). HD footage verified: NASA API NHQ_2019_0626 "Earth Views from the ISS" — 1280x720 HD, 44:00, Creator=None, PD, no NC/ND, third-party credit none. ~medium.mp4 (776 MB) downloaded via curl -L, sha256 recorded. Under 800 MB cap. | pending |
| W2 ISS BUILD | DONE | Claim ledger ISS_CLAIM_LEDGER.md (4 claims, ISS-003 TWO_SOURCES, ISS-001/002/004 SINGLE_SOURCE flagged). Script ISS_FULL_SCRIPT_v0.md (8 beats, 8 chapters, claim_ids resolve ALL OK). Narration kokoro-onnx (195.7s, 8 sentences). finish_audio PASS. Subtitles from measured durations (8 cues, last ends <= audio). EDL 16 cuts with per-cut rationale, all graphics cards static_by_design. 9 graphics cards + NASA PD footage. Render: 1280x720p30 h264/aac, 195.6s. | pending |
| W3 ISS QC | DONE | qc.py with ALL inputs: verdict PASS (12 PASS + 1 REVIEW freezedetect on static_by_design cards; duration drift 0.10s; expected 1280x720 native HD, no upscaling). NOT_PUBLISHABLE documented in artifacts/credits.txt (synthetic-voice disclosure pending, insignia review pending, single NASA clip). | pending |

## Blocker carried (Z1/Z3/Z4 + W)
Kokoro-82M HF weights unreachable (cas-server.xethub.hf.co + us.aws.cdn.hf.co blocked; HF_HUB_DISABLE_XET=1 HTTP stuck at 0 bytes). Resolved for narration via kokoro-onnx GitHub Releases route (weights in /tmp/kilo/kokoro_onnx_weights/).

## Rules observed
- KAGGLE_API_TOKEN never printed/logged/committed.
- Network: NASA images-api, archive.org (curl -L), YouTube help page (read-only), GitHub/PyPI for kokoro-onnx. NTRS blocked — do not retry.
- Downloads into gitignored /tmp or projects/, never committed; delete temp files.
- Disk < 800 MB free -> write state and STOP whole run.
- Code test-first (red then green); report exact commands/exit codes; never claim unobserved work.

## Stop Codespace commands (owner)
- `gh codespace stop -c <codespace-name>`
- `gh codespace list`
- Or VS Code Codespaces panel: stop active codespace

## Rollback
`git revert` of the session's commits on branch `factory/business-documentary-pilot`.
