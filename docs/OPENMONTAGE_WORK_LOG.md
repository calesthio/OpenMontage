# OpenMontage Factory — Work Log


---

### 2026-10-18 — Milestone F1 (v1): fix slice footage quality (docs/code only; media in gitignored projects/, never committed)
- **Goal:** diagnose slice clips (placeholder vs real footage), replace clip01 NASA-logo placeholder with real footage derivative from archive.org, rebuild slice (lanczos 1080p+pad, crf 18, 30fps), run finish_audio + qc.py, contact sheet + logo detection, update rights_records/credits/qa_report. Max 20 network requests, curl -L, downloads <= 400MB in gitignored projects/. No new installs, no paid routes. Roles inline, said so.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `528b9fe` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.3 GB free (89%).
- **Step 1 (diagnose):** ffprobe each clip0*_scaled.mp4. clip01 (272KB, 4.5s) = placeholder: first 3 frames identical (avg-hash hamming=0). clips 02-04 = real footage (hamming 1-11). clip01 → NIX-EM-0004-01, clip02 → NIX-LV-1998-00090, clip03 → NIX-LV-1998-00092, clip04 → NIX-LV-1998-00098 (per edit_decisions.json).
- **Step 2 (best derivatives):** fetched archive.org metadata for 4 items (4 requests). Best h.264 mp4 per item: EM-0004-01.mp4 (3,052,294B, 320x240, sha256 13d2a7e4...), LV-1998-00090.mp4 (1,740,303B, sha256 ae128d36...), LV-1998-00092.mp4 (1,252,468B, sha256 abbd001b...), LV-1998-00098.mp4 (1,599,299B, sha256 522caadd...). Downloaded all 4 (~7.6MB, 4 requests). Total: 8/20 requests, ~7.6MB/400MB.
- **Step 3 (rebuild):** lanczos scale 1920x1080 + pad (no stretch), crf 18, 30fps. clip01 source opens with 4s NASA logo → used real-footage segment 8.0-12.5s instead of 0-4.5s. Archive.org AAC malformed → audio via WAV/PCM. finish_audio PASS. Final: 45.8s, 1920x1080, h264/aac, 30fps.
- **Step 4 (contact sheet + logo):** 12 frames at even timestamps; all high std dev (76-103) = varied real footage; blue=sky (f6-f8), red=fireball (f2-f5); NO NASA logo/title card → logo_visible=false, no clip REJECTed.
- **Step 5 (records):** rights_records.json updated (sha256, source_file, size, resolution, used_segment); credits.txt updated (logo replacement noted); qa_report.json recorded. Media (final_slice.mp4, contact_sheet.jpg) in gitignored projects/, NOT committed.
- **QC result:** ffprobe_streams PASS, full_decode PASS, blackdetect PASS, freezedetect PASS, silencedetect PASS, ebur128 FAILED (I=-17.0 LUFS, target -14+/-2, marginal 1 LU below range), duration_vs_script NOT_RUN, subtitle_sync NOT_RUN, credits_complete PASS, claim_ids NOT_RUN, rights_basis PASS (4/4), added_value PASS. Overall: FAILED (ebur128 marginal).
- **Tests actually run:** tests/tools/test_qc_tool.py (6/6, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0) — all pre-existing, re-verified.
- **Budget / provider verification:** strict $0 held. 8/20 network requests, ~7.6MB downloads. curl -L. No new installs, no paid routes, no secrets.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F1 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner decides whether to accept marginal ebur128 FAILED (-17.0 LUFS) or re-run finish_audio; then proceed to next milestone per plan.

---

### 2026-10-18 — Milestone M1 (v1): selective merge of KILO_CODE_YOUTUBE_FACTORY_MASTER.md into factory (docs + project-level skills only)
- **Goal:** audit master file's 9 skills + 6 rule blocks against installed skills/docs/AGENTS.md/QA_SPEC.md/RIGHTS_MODEL.md/plan v3.2; write docs/openmontage/MERGE_AUDIT.md; seed docs/agent-improvement/{LESSONS.md,BACKLOG.md,EVALS.md,CHANGELOG.md}; adapt .kilo/skills/kilo-self-improvement/SKILL.md to reference EVALS.md (project-level only); stub youtube-publishing-analytics in docs/openmontage/; propose AGENTS.md additive rules block in docs/openmontage/AGENTS_PROPOSED_DIFF.md (not applied). Time-box 35 min. No MCP installs, no global Kilo config changes, no process/lock changes, no paid routes, no secrets. Roles inline, said so. Owner's uncommitted AGENTS.md modification preserved exactly (backed up to /tmp).
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `8bc5f7b` on `factory/business-documentary-pilot`; `df -h /workspaces`: 3.3 GB free (89%); `.kilo/skills/` already contains all 9 master skills with matching name/description front matter; docs/agent-improvement/ already has LESSONS/BACKLOG/EVALS/CHANGELOG templates; `kilo --help` has NO `skills` subcommand → discovery NOT_CHECKED.
- **Master file located:** `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` found in git commit `36e6595` (1782 lines), not in working tree; treated as reference only — no bootstrap, no install scripts, no vertical slice, no docs/architecture/current-state.md/target-state.md created.
- **Table A (skills):** all 9 skills = OVERLAP (already installed, name/desc match). kilo-self-improvement = MERGE-IDEAS-ONLY (adapted to reference EVALS.md, project-level only, no global writes). Remaining 8 = SKIP (duplicates; render stack = ffmpeg + HyperFrames per plan v3.2; publishing-analytics = stub-only, no OAuth).
- **Table B (rules):** rights/provenance OVERLAP (RIGHTS_MODEL.md wins, more specific); publishing safety OVERLAP (AGENTS.md identical); pipeline stages OVERLAP (AGENTS.md identical); definition of done CONFLICT (master NOT_CHECKED vs QA_SPEC PASS\|REVIEW\|BLOCKED\|FAILED — mapped, not replaced); self-improvement OVERLAP; MCP/tool list CONFLICT (master lists GitHub/Serena/jCodeMunch/YouTube/n8n/Context7 MCPs vs plan v3.2 max-3-runtime + zero-secrets in v1 → SKIP all MCPs); global AGENTS/global skill paths vs project-level only CONFLICT → SKIP (~/.config/kilo untouched).
- **Conflicts flagged:** (1) Remotion vs HyperFrames — Remotion SKIP, ffmpeg+HyperFrames stack; (2) extra MCPs vs max-3-runtime+zero-secrets — none installed; (3) global paths vs project-level — none written; (4) master NOT_CHECKED vs our qa_report statuses — mapped NOT_CHECKED→BLOCKED/NOT_RUN, our statuses kept.
- **Files created:** docs/openmontage/MERGE_AUDIT.md; docs/openmontage/youtube-publishing-analytics-STUB.md; docs/openmontage/AGENTS_PROPOSED_DIFF.md.
- **Files modified:** docs/agent-improvement/LESSONS.md (6 evidence-backed entries seeded); docs/agent-improvement/EVALS.md (5 fixed tasks); .kilo/skills/kilo-self-improvement/SKILL.md (EVALS.md reference added to evaluate step; name/description unchanged); docs/agent-improvement/CHANGELOG.md (M1 entry added).
- **Files NOT touched:** AGENTS.md (owner's uncommitted modification preserved; proposed diff only in docs/openmontage/AGENTS_PROPOSED_DIFF.md); kilo.json/kilo.jsonc; ~/.config/kilo; any media/secrets.
- **Tests actually run:** tests/tools/test_qc_tool.py (6 passed, exit 0); tests/tools/test_finish_audio.py (5 passed, exit 0); tests/tools/test_piper_tts.py (9 passed, exit 0); tests/tools/test_tts_kaggle.py (5 passed, exit 0). py_compile OK on changed files.
- **kilo --help skills subcommand:** NOT_CHECKED — no `skills` subcommand exists; owner can check via `ls .kilo/skills/` or `kilo agent list`.
- **Budget / provider verification:** strict $0 held. No MCP installs, no global config changes, no paid routes, no secrets, no process/lock changes.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs + skill files staged; no destructive commands, no force-push.
- **Rollback:** `git revert` of the M1 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner reviews AGENTS_PROPOSED_DIFF.md and MERGE_AUDIT.md Table B conflicts; decides on MCP/tool and global-path conflicts; then proceed to next milestone per plan.

---

### 2026-10-17 — Milestone K1 (v2): Kaggle bridge code (test-first) + live "hello" CPU job
- **Goal:** tools/kaggle_bridge/kaggle_bridge.py + tests/tools/test_kaggle_bridge.py (TDD, 16 tests) + live smoke job on forts845/of-bridge-runner + update KAGGLE_BRIDGE_DESIGN.md + work log. Stdlib + kaggle CLI only, no network directly, no API keys handled, no GPU/datasets/secrets, no third-party wrappers, no process/lock changes. Roles inline, said so. Token never printed/logged/committed/passed on command line.
- **Preflight observed:** git status clean; HEAD `cf0d935` on `factory/business-documentary-pilot`; `df -h /workspaces`: 3.4 GB free (89%); `KAGGLE_API_TOKEN`: set, length=37; `kaggle kernels list --mine --page-size 5`: exit 0, auth confirmed, owner=`forts845`.
- **Step 1 (TDD):** wrote 16 failing tests first using a FAKE `kaggle` executable in a tmp dir (passed as `kaggle_cmd`, not on PATH) simulating push OK, status queued→running→complete, status error, never-finishing (total-timeout→BLOCKED), unknown status (BLOCKED), output missing manifest, sha256 mismatch, empty output, auth failure, 409/conflict bounded retry→BLOCKED, token never in args/result JSON, backoff/timeouts honored, fail-closed on unparseable. Ran red (ImportError).
- **Step 2 (implementation):** tools/kaggle_bridge/kaggle_bridge.py — KaggleBridgeTool(BaseTool) with commands build_job_folder, push, poll, fetch_output, verify, run_qc, run_job. build_job_folder generates kernel-metadata.json from `kaggle kernels init` output (no guessed field names). push uses `-t/--timeout` and `--accelerator` (no `--no-run`). poll uses backoff + total timeout. verify recomputes sha256 vs manifest. Fail-closed. Token never in command args or result JSON.
- **Step 3 (green):** all 16 tests pass; existing tests/tools/test_qc_tool.py (11) still pass; py_compile OK.
- **Step 4 (live smoke job):** private kernel `forts845/of-bridge-runner`, CPU only (`enable_gpu=false`, `enable_internet=false`), run.py (stdlib only) writes hello.txt + manifest.json to /kaggle/working. Push: `kaggle kernels push -p jobs/hello-1 -t 3600 --accelerator cpu` → `Kernel version 1 successfully pushed.` (2.4s). Note: kernel-metadata `title` must slugify to `id` suffix else 409 Conflict (fixed title to "Of Bridge Runner"). Poll: `kernels status` → `KernelWorkerStatus.COMPLETE` at first poll (ran during push); single distinct status string. Output: hello.txt (6B), manifest.json (186B), kernel log. Download 0.96s. Verify: sha256 `5891b5b5...` matches manifest → PASS. Full result JSON at /tmp/k1_result.json, verdict PASS. Original kernel source files in /tmp (not committed).
- **Step 5 (design doc):** updated KAGGLE_BRIDGE_DESIGN.md — observed status string format `<slug> has status "KernelWorkerStatus.<STATUS>"`, title/slug 409 constraint, `enable_internet=false` confirmed works, --no-run absence confirmed, timeout option confirmed; other constraints (GPU quota, session max, phone verification, serialized jobs) remain UNVERIFIED; added Step 6.5 live results; updated Step 7 observed/assumed.
- **Delegation note:** `.kilo/agents` subagents exist but `task` tool exposes only explore/general; no separate subagent process available. All work executed inline by orchestrator, attributed by domain. "inline, not independent."
- **Files created:** tools/kaggle_bridge/kaggle_bridge.py, tools/kaggle_bridge/__init__.py, tests/tools/test_kaggle_bridge.py.
- **Files modified:** docs/openmontage/KAGGLE_BRIDGE_DESIGN.md, docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Tests actually run:** tests/tools/test_kaggle_bridge.py (16 passed, ~76s); tests/tools/test_qc_tool.py (11 passed, ~120s); py_compile OK.
- **Budget / provider verification:** strict $0 held. pip install kaggle already done in K0. Kaggle API calls via CLI with KAGGLE_API_TOKEN set (token never logged/committed). No paid routes. No process/lock changes.
- **Git status / user changes preserved:** tree clean at start; only agent-authored files staged; no destructive commands, no force-push. Kaggle kernel source + outputs live in /tmp (not committed).
- **Next smallest step:** K1 bridge code complete and verified live; proceed to K2 (Kokoro job end-to-end) per plan.

---
### 2026-10-17 — Milestone K0 (v2): Kaggle bridge preflight + design (docs only)
- **Preflight observed:** git status clean; HEAD `7fd52a4` on `factory/business-documentary-pilot`; `df -h /workspaces`: 3.2 GB free (90% used); `KAGGLE_API_TOKEN`: **not set** (length n/a).
- **Step 1 (reachability, 4/6 requests used):** kaggle.com DNS resolves (35.244.233.98), HTTPS HTTP/2 404 on `/` (service up); api.kaggle.com DNS resolves (34.54.168.202), HTTPS HTTP/2 404 on `/` (service up). Both **reachable**. 404 on root = expected (no root handler), not an error. No auth used. 2 requests unused.
- **Step 2 (CLI install):** `pip3 install --only-binary=:all: kaggle` → `kaggle 2.2.4`, CLI at `/home/codespace/.python/current/bin/kaggle`, install size 1.3 MB, `/workspaces` free space unchanged (~3.2 GB). No third-party Kaggle MCP/wrappers.
- **Step 3 (auth test, STOPPED per rules):** `KAGGLE_API_TOKEN` **not set** → `kaggle kernels list --mine` **not run**. Required owner step: create Codespaces secret `KAGGLE_API_TOKEN` (from https://www.kaggle.com/settings/api "Generate New Token") and restart codespace. No token value printed/logged/committed; only presence (no) + length (n/a) reported.
- **Step 4 (CLI help quotes, observed):** `push` supports `--accelerator ACC` and `-t/--timeout TIMEOUT`, does **NOT** support `--no-run` (push always runs); `status [kernel]` takes `<owner>/<kernel-name>[/<version>]`; `output` supports `-p PATH -w -o -q --file-pattern --page-size (max 200) --page-token`; `list --mine` with `--page-size`, `--format csv/table/json`, `--language`, `--kernel-type`, `--sort-by`. `status` terminal strings **not enumerated in --help** (UNVERIFIED; must be observed live after auth).
- **Step 5 (KAGGLE_BRIDGE_DESIGN.md):** job folder layout (`jobs/<job_id>/{job.json, kernel-metadata.json, run.py}`), single private runner kernel (slug TBD) with serialized jobs, one wav + manifest.json per job (sha256, duration, library versions, license facts), flow push -> poll with backoff + total timeout -> output -> verify sha256/manifest -> run tools/qa/qc.py -> result JSON; fail-closed table (auth, 409/conflict, queue, timeout, error status, empty output, hash mismatch -> status + action); constraints UNVERIFIED (GPU 30 h/week, 12 h session, phone verification, internet toggle); secrets rule (nothing secret in kernel; Kaggle Secrets not settable via CLI); disk rule (remove torch/kokoro from Codespace after bridge works).
- **Step 6 (next milestones):** K1 = bridge code with tests using a fake `kaggle` executable on PATH + live "hello" CPU job; K2 = Kokoro job end-to-end. No implementation in K0.
- **Delegation note:** `.kilo/agents` subagents exist but `task` tool exposes only explore/general; no separate subagent process available. All work executed inline by orchestrator, attributed by domain. "inline, not independent."
- **Files created:** docs/openmontage/KAGGLE_BRIDGE_DESIGN.md.
- **Files modified:** docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Tests actually run:** none live (auth blocked by missing token); CLI `--help` reads observed read-only.
- **Budget / provider verification:** strict $0 held. pip install kaggle (PyPI, free). No Kaggle API calls made (token not set). No paid routes, no keys handled. No process/lock changes.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** owner creates `KAGGLE_API_TOKEN` Codespaces secret and restarts codespace; then run `kaggle kernels list --mine --page-size 5` to confirm auth, then proceed to K1.

---
### 2026-10-17 — Milestone V (v2): replace Piper lessac with Kokoro-82M — license evidence, install, CPU test (docs only)
- **Goal:** license evidence from official Kokoro-82M files + kokoro/misaki PyPI + Piper lessac MODEL_CARD; install kokoro + minimal deps into project Python env; download weights to gitignored cache (<=600 MB); CPU synthesize neutral paragraph with 3 voices + report RTF/memory/espeak-ng; QC tool on each sample + finish_audio on one + AAC encoder check + loudness on final MP4; VOICE_DECISION.md + TOOLING_DECISIONS.md + KOKORO_TTS_PROPOSAL.md; work log. Allowed: pip install kokoro + minimal deps, download Kokoro-82M weights (~330 MB, cap 600 MB) into gitignored cache. No paid routes, no keys, no process/lock changes. Roles inline, said so. No pipeline code changed.
- **Preflight observed:** git status clean; HEAD `9f2ef3b` on `factory/business-documentary-pilot`; Python 3.14.2; `/workspaces` 98% full (820 MB free) → weights/HF cache stored on `/tmp` (38 GB free); espeak-ng NOT installed; no existing Kokoro tool/provider in `tools/`.
- **Network/disk:** pip cache redirected to `/tmp/pip-cache` (home/pip cache on full overlay). kokoro 0.2.2 installed via `pip3 install --only-binary=:all: kokoro` (source build of spacy/thinc/blis failed on Python 3.14 — resolved with binary-only). soundfile 0.14.0 installed. HF cache `HF_HOME=/tmp/hf-cache`; kokoro-v1_0.pth (~313 MB) downloaded (within 600 MB cap). Total downloads well under cap. No weights/committed media in repo.
- **Step 1 (license evidence):** Kokoro-82M weights Apache-2.0 (HF model page); kokoro package Apache-2.0 (GitHub LICENSE); misaki package Apache-2.0 (GitHub LICENSE); Piper lessac-medium UNKNOWN (MODEL_CARD no license field, points to Lessac Blizzard 2013 dataset license URL; manifest's CC-BY-4.0 unverified). Training data: public domain + Apache/MIT + synthetic from closed TTS; CC BY items Koniwa `tnc` (<1h, CC BY 3.0) + SIWIS (<11h, CC BY 4.0); synthetic-data origin UNKNOWN. Evidence URLs recorded in VOICE_DECISION.md.
- **Step 2 (install + CPU run):** kokoro installed; KPipeline(lang_code='a') on CPU (torch 2.14.1, no CUDA). espeak-ng missing → `EspeakFallback` warning only (non-fatal; misaki G2P works).
- **Step 3 (synthesis):** neutral public-domain paragraph (Genesis) with 3 voices af_heart/af_bella/am_adam → dur 23.0–25.6s, elapsed 38.3–44.8s, RTF 1.58–1.75 (slower than real-time on CPU, expected). Samples to /tmp/*.wav only (not committed).
- **Step 4 (QC + finish + AAC):** QC (ebur128) on each sample: raw kokoro I=-21.8 to -25.4 LUFS (FAILED vs -14±2), decode PASS. finish_audio on af_heart → I=-15.0 LUFS, TP=-4.4 PASS. Native `aac` encoder available; s16 wav → aac MP4 mux works; FINISHED MP4 I=-15.0 LUFS, TP=-4.3, ebur128 PASS, full_decode PASS, 0.6 MB. (D2's "broken AAC" was pcm_f32le→aac; s16→aac works.)
- **Step 5 (VOICE_DECISION.md):** Kokoro selected (Apache-2.0 weights, clear at weights level); training-data caveats (CC BY attribution, synthetic origin UNKNOWN) → owner sign-off required; Piper lessac blocked (voice license UNKNOWN). Voice license gate NOT PASSED for Piper lessac; Kokoro provisionally known.
- **Step 6 (TOOLING_DECISIONS.md):** §12.2 voice-license table updated (Kokoro row added, Piper voice marked blocked, note added); §14 Milestone V summary added.
- **Step 7 (proposal):** docs/openmontage/KOKORO_TTS_PROPOSAL.md — KokoroTTSTool at tools/audio/kokoro_tts.py, integration point = EDITING_DOCTRINE step 5 audio (before finish_audio), no pipeline changes in V.
- **Delegation note:** `.kilo/agents` subagents exist but `task` tool exposes only explore/general; no separate subagent process available. All work executed inline by orchestrator, attributed by domain. "inline, not independent."
- **Files created:** docs/openmontage/VOICE_DECISION.md, docs/openmontage/KOKORO_TTS_PROPOSAL.md.
- **Files modified:** docs/openmontage/TOOLING_DECISIONS.md (§12.2 table, §14 summary), docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Tests actually run:** none new (V is license+install+test, no new test suite); finish_audio/QC re-verified during smoke test (exit 0).
- **Budget / provider verification:** strict $0 held. pip install kokoro + soundfile (binary wheels, PyPI). HF hub weight download (keyless, unauthenticated). No paid routes, no keys, no model purchases. No process/lock changes.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push. kokoro/soundfile installed into site-packages (not committed); weights in /tmp/hf-cache (not committed, gitignored by virtue of being outside repo).
- **Next smallest step:** commit + push V docs; owner sign-off on Kokoro training-data caveats before publication; proceed to next milestone per plan.

---
### 2026-10-17 — Milestone D2 (v2): audio finishing module, test-first, verified by QC tool (code + tests + docs)
- **Goal:** tools/audio/finish_audio.py + tests/tools/test_finish_audio.py (TDD, 5 tests) + docs/openmontage/AUDIO_FINISHING.md; smoke test on pilot MP4 audio into /tmp; work log. Stdlib + ffmpeg/ffprobe only, no network, no model downloads, no new deps, no process/lock changes. Roles inline, said so. NOT wired into render pipeline yet (proposed integration point only).
- **Preflight observed:** git status clean; HEAD `0610da1` on `factory/business-documentary-pilot`; ffmpeg 6.1.1 with loudnorm/sidechaincompress/alimiter/ebur128 filters; piper-tts 1.8.0 + onnxruntime + numpy installed.
- **TDD:** wrote 5 failing tests first (voice loudness+true-peak, music ducking, no-music, mono/stereo+22050/44100 Hz, failure-path BLOCKED). Fixtures via ffmpeg lavfi in tmp dirs, no committed media. Ran red → confirmed import failure. Implemented tools/audio/finish_audio.py. Ran green → all 5 passed.
- **Checks implemented:** two-pass loudnorm (measure → apply with measured values) + alimiter true-peak safety + optional sidechaincompress ducking. Targets I=-14, TP=-1.5, LRA=11 from config/qc_thresholds.json (INITIAL GUESSES). Fail-closed: loudnorm unparsable / filter missing → BLOCKED.
- **Implementation notes:** pcm_f32le→aac and s16→aac-after-limiter are broken in this ffmpeg build (produce -70 LUFS / silence), so finish outputs pcm_s16le wav directly (loudnorm+limiter in one pass2 chain); ebur128 reads wav fine. sidechaincompress threshold is linear 0-1 (not dB), attack/release take seconds (not ms), sidechain is 2nd input (no `sidechain=` option), detection takes int not string, ratio max 20.
- **Tests actually run:** tests/tools/test_finish_audio.py (5 passed, ~30 s). py_compile on changed files OK. test_07_playbook_intelligence.py collects 0 pytest items (script, not pytest functions).
- **Smoke test:** extracted pilot MP4 audio (projects/pallets-hidden-business/renders/pallets-hidden-business.mp4, 44100 Hz mono, 84.99 s) to /tmp; BEFORE I=-17.2 LUFS / TP=-0.0 dBFS (clipping); AFTER I=-15.3 LUFS / TP=-4.5 dBFS; QC tool ebur128 PASS + full_decode PASS. Original NOT overwritten; internal test only, not a publishability claim.
- **Docs:** wrote docs/openmontage/AUDIO_FINISHING.md (what the tool does, targets, proposed integration point = EDITING_DOCTRINE step 5 audio normalize/music bed, voice license blocker from TOOLING_DECISIONS.md §12.2, owner question on -16..-14 LUFS).
- **Files created:** tools/audio/finish_audio.py, tests/tools/test_finish_audio.py, docs/openmontage/AUDIO_FINISHING.md.
- **Tests actually run:** 5 passed. py_compile OK.
- **Budget / provider verification:** strict $0 held. No network, no API keys, no model downloads. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent-authored files staged; no destructive commands, no force-push.
- **Next smallest step:** commit code+tests+docs and push; voice license resolution (UNKNOWN) remains a blocker before commercial publication; proceed to next milestone per plan.

---
### 2026-10-17 — Milestone C6 (v2): finish contact sheets for all 11 CID clips + durations + coverage map + voice decision summary (docs only)
- **Goal:** fetch metadata + download smallest video derivative + build ffmpeg contact sheets (~12 frames) for all 11 CID clips; per-clip duration/resolution/audio table + owner checklist; coverage map of narrative beats; proposed (not applied) viability-gate wording on beat coverage; voice decision summary from TOOLING_DECISIONS.md. Docs/reports only: no code, no installs, no process/lock changes. Use curl -L. Cap: 30 network requests, 20 s timeout each; downloads <= 200 MB into gitignored projects/c5_review/ (never committed). ERROR/HTTP status/EMPTY separate states. Roles inline, said so.
- **Preflight observed:** git status clean; HEAD `21291dc` on `factory/business-documentary-pilot`; ffmpeg 6.1.1, curl available.
- **Network requests this session:** 9 metadata fetches (NIX-EM-0004-02, NIX-LV-1998-00091…00098) + 9 downloads (_512kb.mp4 each) = 18 requests (C5 used 10; cumulative 28/30 cap). All HTTP 200. Total downloads ~13 MB (C5 ~2.6 MB + C6 ~10.4 MB), under 200 MB cap. No errors/EMPTY conflated.
- **Step 1 (contact sheets all 11):** metadata fetched for 7 remaining clips (EM-0004-02 already partially known; LV-00091…00098). Smallest video derivative = `_512kb.mp4` per clip. All 9 downloaded HTTP 200; combined with C5's EM-0004-01 + LV-00090 = all 11 contact sheets built via ffmpeg `select='not(mod(n,90))',scale=320:240,tile=3x4`:
  projects/c5_review/{EM-0004-01,EM-0004-02,LV-1998-00090,LV-1998-00091,LV-1998-00092,LV-1998-00093,LV-1998-00094,LV-1998-00095,LV-1998-00096,LV-1998-00097,LV-1998-00098}_512kb_contact_sheet.jpg
- **Step 2 (per-clip table):** ffprobe (local, no network) on all 11: all 320x240; NIX-EM-* no audio (2 clips), NIX-LV-* has audio (9 clips); durations 11.00s–38.60s, total ~286s (~4.8 min). Owner checklist columns (person | logo/insignia | third-party credit) left empty for the owner. Added to REVIEW_QUEUE.md.
- **Step 3 (coverage map):** metadata-only beat assignment. Distinct beats covered: 4 (remote piloting, impact, fire, other). Zero-clip beats: 3 (preparation, flight, aftermath). Proposed (not applied) viability-gate wording: >= 6 distinct beats with >= 1 usable clip each, in addition to raw clip count. Applied to CID: 4 beats < 6 → NOT_GATE_READY on narrative coverage under the proposal. Proposal only, not applied.
- **Step 4 (voice decision summary):** from TOOLING_DECISIONS.md §12.2 (D1). Piper engine GPL-3.0-or-later (commercial permitted); Piper voice en_US-lessac-medium UNKNOWN (sidecar has dataset=lessac, no license field; manifest asserts CC-BY-4.0 but no license text in repo); Kokoro UNKNOWN (not installed). Voice license known gate cannot pass → commercial publication blocked until voice license confirmed or licensed alternative selected. Smoke test was technical only (RTF 0.21), not a commercial-use approval.
- **Delegation note:** `.kilo/agents` subagents exist but `task` tool exposes only explore/general; no separate subagent process available. All footage-scout work executed inline by orchestrator, attributed by domain. "inline, not independent."
- **Files changed:** docs/openmontage/audit/REVIEW_QUEUE.md (appended C6 per-clip table + coverage map + voice decision summary; updated owner-list durations), docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Media:** projects/c5_review/ (downloaded MP4s + 11 contact sheets) is gitignored (`projects/` in .gitignore), NOT committed, under 200 MB cap (~13 MB).
- **Tests actually run:** none (docs/report milestone; ffmpeg/ffprobe observed exit 0).
- **Budget / provider verification:** strict $0 held. 18 keyless archive.org requests this session (cumulative 28/30 cap). No API keys, no model downloads. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push C6 docs; then proceed to next milestone per plan (voice license resolution is a blocker before publication).

---
### 2026-10-17 — Milestone C5 (v2): archive.org download diagnosis + owner review list (docs only)
- **Goal:** metadata + real file list per CID item; HEAD/ranged GET download diagnosis; contact sheets; numbered owner list; NASA Facts doc added to evidence; sequential-ID analysis. Docs/reports only: no code, no installs, no process/lock changes. Max 10 network requests, 20s timeout each; ERROR/HTTP status/EMPTY as separate states. Roles executed inline, said so.
- **Preflight observed:** git status clean; HEAD `59cdf6a` on `factory/business-documentary-pilot`; ffmpeg 6.1.1, curl available.
- **Network requests (10/10 cap reached):**
  1. metadata NIX-EM-0004-01 → HTTP 200, real file list obtained (EM-0004-01.mp4 3052294 bytes len 36.56s, EM-0004-01.mov original, 7 thumbnails)
  2. metadata NIX-LV-1998-00090 → HTTP 200, real file list obtained (LV-1998-00090.mp4 1740303 bytes len 16.93s, LV-1998-00090.mov original, __ia_thumb.jpg 5939 bytes)
  3. HEAD thumbnail LV-00090 → HTTP 302 redirect to dn710909.ca.archive.org, content-type image/jpeg, accept-ranges: bytes
  4. HEAD smallest video LV-00090_512kb.mp4 → HTTP 302 redirect to dn801201.us.archive.org, content-type video/mp4
  5. ranged GET thumbnail (first 64KB) → HTTP 206, 5939 bytes, valid JPEG 180x124
  6. ranged GET video (first 64KB) → HTTP 206, 65536 bytes, valid MP4
  7. metadata NIX-EM-0004-02 → HTTP 200 (title/creator/date obtained)
  8. metadata NIX-LV-1998-00091 → HTTP 200 (title/creator/date obtained)
  9. full download EM-0004-01_512kb.mp4 → HTTP 200, 2,236,128 bytes, valid MP4
  10. full download LV-1998-00090_512kb.mp4 → HTTP 200, 405,589 bytes, valid MP4
- **Diagnosis:** archive.org download WORKS when following HTTP 302 redirects (`curl -L`). Earlier C4 "0 bytes / HTML" results were caused by missing `-L` (got 302 with empty body), not by access restriction/blocking. Not wrong URL, not access-restricted, not blocked egress, not hotlink — valid MP4/JPEG returned.
- **Step 3 (contact sheets):** working URL found → downloaded preview derivatives into gitignored `projects/c5_review/` (~2.6MB total, under 200MB cap, never committed). Built ffmpeg contact sheets (~12 frames): EM-0004-01_contact_sheet.jpg (39,784 bytes), LV-1998-00090_contact_sheet.jpg (28,423 bytes). Remaining 9 items not downloaded within 10-request cap (metadata file names needed first).
- **Step 4 (owner list):** printed numbered list of 11 archive.org item URLs to terminal AND wrote to REVIEW_QUEUE.md (descriptions + durations from metadata; durations n/a where file list not re-fetched within cap). Note: pt 1/10 implies 10 parts but only 9 (00090-00098) located.
- **Step 5:** added NASA Facts FS-2009-02-003-CID PDF (rosap/nasa.gov) to EVIDENCE_CID_PRIMARY_DOCS.md as EXTERNALLY_VERIFIED_METADATA (web search 2026-10-17, not agent-verified). Primary docs count now 7.
- **Step 6 (sequential IDs):** NIX-LV-1998-00090…00098 = 9 of 10 implied parts (pt 1/10–pt 9/10), same creator/date/event, different camera angles of same impact → likely separate angles with temporal overlap, not one linear reel. Viewing needed to confirm overlap/duplicates and whether a 10th part exists elsewhere.
- **Delegation note:** `.kilo/agents` subagents exist but `task` tool exposes only explore/general; no separate subagent process available. All footage-scout work executed inline by orchestrator, attributed by domain. "inline, not independent."
- **Files changed:** docs/openmontage/audit/REVIEW_QUEUE.md (appended C5 owner list + contact-sheet correction + sequential-ID analysis), docs/openmontage/audit/EVIDENCE_CID_PRIMARY_DOCS.md (added entry 7), docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Media:** projects/c5_review/ (downloaded MP4s + contact sheets) is gitignored (`projects/` in .gitignore), NOT committed, under 200MB cap.
- **Tests actually run:** none (docs/report milestone; ffmpeg contact-sheet generation observed exit 0).
- **Budget / provider verification:** strict $0 held. 10/10 keyless archive.org requests used (at cap). No API keys, no model downloads. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push C5 docs; then proceed to next milestone per plan.

---
- **Goal:** tools/qa/qc.py QC module + tests/tools/test_qc_tool.py (TDD, 11 tests) + config/qc_thresholds.json; smoke test on pilot MP4; wire qa-reviewer.md + AGENTS.md; work log. Stdlib + ffmpeg/ffprobe only, no network, no new deps, no process/lock changes. Execute roles inline, say so.
- **Preflight observed:** git status clean; HEAD `a36ea23` on `factory/business-documentary-pilot`; ffmpeg 6.1.1, ffprobe 6.1.1, pytest 9.1.1, Python 3.14.2; ruff NOT installed (used py_compile as lint substitute).
- **TDD:** wrote 11 failing tests first (good clip, black segment, silent segment, frozen segment, no audio, wrong resolution, corrupt/truncated, subtitle drift, tool-missing BLOCKED, NOT_RUN when inputs absent, report schema). Ran red → confirmed import failure. Implemented tools/qa/qc.py. Ran green → all 11 passed.
- **Checks implemented:** ffprobe_streams, full_decode (-f null), blackdetect, freezedetect (incl. frozen-to-end-of-clip case), silencedetect, ebur128 (ffmpeg 6.x summary parse), duration_vs_script, subtitle_sync, credits_complete, claim_ids, rights_basis, added_value. Fail-closed (tool missing → BLOCKED); absent optional inputs → NOT_RUN; verdict treats NOT_RUN as not-passed.
- **Thresholds config:** config/qc_thresholds.json with INITIAL GUESSES from QA_SPEC.md (black 0.05, freeze 2.0s, silence 0.10, LUFS -14 +/- 2, TP -1.5, duration 1.0s, subtitle drift 0.5s), each documented as a guess.
- **qa_report.json schema:** {job_id, check_id, status ∈ {PASS,REVIEW,BLOCKED,FAILED,NOT_RUN}, evidence, measured_value, threshold, tool_version, timestamp ISO-8601 UTC}. No secrets written.
- **Smoke test:** pilot MP4 `projects/pallets-hidden-business/renders/pallets-hidden-business.mp4` (1080p30, 84.9s, h264/aac) → verdict FAILED; ebur128 FAILED (I=-17.1 LUFS outside -14±2, TP=-0.0 > -1.5). All stream/decode/black/freeze/silence PASS. Internal tool test only, not a publishability claim.
- **Agent wiring:** updated .kilo/agents/qa-reviewer.md (references tools/qa/qc.py + config/qc_thresholds.json + NOT_RUN) and AGENTS.md roster row.
- **Tests actually run:** tests/tools/test_qc_tool.py (11 passed, ~2 min). py_compile on changed files OK. test_07_playbook_intelligence.py collects 0 pytest items (it's a script, not pytest functions).
- **Budget / provider verification:** strict $0 held. No network, no API keys, no model downloads. No installs (ruff unavailable → py_compile).
- **Git status / user changes preserved:** tree clean at start; only agent-authored files staged; no destructive commands, no force-push.
- **Next smallest step:** commit code+tests+docs and push; then proceed to milestone D/Q per plan.

---
- **Goal:** EVIDENCE_CID_PRIMARY_DOCS.md (6 primary docs, EXTERNALLY_VERIFIED_METADATA); metadata-only classification of 11 Boeing NEEDS_REVIEW + 1 REJECT clips; gate recompute under written gate (no lowering 10-clip); owner review pack + contact-sheet evidence; proposed (not applied) incidental-insignia wording (owner decision); plan/work log update (CID slice/pilot candidate + fallbacks). Docs/reports only: no code, no installs, no process/lock changes. Inline, not independent.
- **Preflight observed:** git status clean; HEAD `9c6a0c71bcaef7ed916db0182d2a360f1d2921f8` on `factory/business-documentary-pilot`; all four `.kilo/agents` subagents present in `kilo agent list`.
- **Delegation note (honest):** subagents exist but `task` tool exposes only explore/general; no separate `.kilo/agents` subagent process available. All footage-scout/evidence-checker/qa-reviewer work executed inline by orchestrator, attributed by domain. RIGHTS_MODEL.md not loosened.
- **Step 1 (primary docs):** 6 entries in EVIDENCE_CID_PRIMARY_DOCS.md (NASA-TP-2589/19860021249, NASA-TM-89642/19880000639, NASA-TM-85925/19850015486, NASA TM 4084/19890006539 PDF, Hayduk/19860012463, FAA/DOT dot_92854). All EXTERNALLY_VERIFIED_METADATA via web search 2026-10-17; NTRS unreachable from sandbox (TCP 443 block, C3); NOT agent-verified; PDF retrieval not confirmed; no document text pasted.
- **Step 2 (clip classification):** archive.org metadata API for 11 NIX clips (NIX-EM-0004-01/02, NIX-LV-1998-00090…00098). All creator=NASA center (Dryden/Langley), rights=None, licenseurl=None, no third-party credit → source_policy_us_gov under written rule; flags UNKNOWN → NEEDS_REVIEW. All 11 on-topic (depict CID impact/fire). No duplicates (distinct part numbers/titles). 1 REJECT: youtube-Jpc32JQXT_0 (third-party credit "The Federal File"). File:Controlled Impact Demonstration.webm also REJECT (third-party uploader Askeuhd). Durations confirmed for 4 of 11 (36.56s, 35.22s, 16.93s, 38.69s).
- **Step 3 (gate recompute):** usable-pending-review=11 (>=10 ✓), primary docs=6 (>=3 ✓) → counts met, but clips are NEEDS_REVIEW (flags unreviewed) and docs NTRS-unreachable → full-video gate NEEDS_OWNER_REVIEW, not clean PASS. 30-60s slice (3-6 clips) MET (11 on-topic available). C3 inconsistency resolved: C3 step 6 omitted Boeing 720 from gate check; C4 includes it.
- **Step 4 (owner review pack):** REVIEW_QUEUE.md appended CID section (11 NEEDS_REVIEW clips CID-1..CID-11, 2 REJECT, owner checklist per clip). Contact sheets NOT generated: archive.org `__ia_thumb.jpg`=0 bytes blocked, individual `.thumbs/*.jpg`=HTML not images, MP4 derivatives=0 bytes blocked; projects/c4_review/previews/ empty, 0 bytes downloaded (200MB cap not reached). Defer contact sheets to environment reaching archive.org asset hosts.
- **Step 5 (incidental insignia wording):** PROPOSED not applied; owner decision. Re-quoted NASA exception categories (insignia/logotype not PD, third-party material, identifiable persons, no endorsement, no NFT/crypto, AI limits). Wording drafted for incidental insignia on vehicles in CID footage.
- **Step 6 (plan/work log):** Slice/pilot candidate = CID 1984 (only topic >=10 usable-pending-review clips). Fallbacks: X-15 (2 clips), Shuttle/Edwards ALT (1 ALT-specific). Observed vs assumed recorded.
- **Files created:** docs/openmontage/audit/EVIDENCE_CID_PRIMARY_DOCS.md, docs/openmontage/audit/C4_CID_FOCUS_REPORT.md.
- **Files modified:** docs/openmontage/audit/REVIEW_QUEUE.md (appended CID section), docs/OPENMONTAGE_WORK_LOG.md (this entry).
- **Tests actually run:** none (docs/report only; archive.org metadata API observed working; asset downloads observed blocked; ffmpeg contact-sheet not generated).
- **Budget / provider verification:** strict $0 held. Keyless archive.org metadata API worked; archive.org asset downloads blocked; NTRS persistent ERROR. No paid call, generation, upload, publish. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push C4 docs; then obtain owner flag review for 11 CID clips + insignia-clearance decision before milestone D/Q.

---

### 2026-10-17 — Milestone C3 (v2): rights classification diagnosis + NTRS network diagnosis (docs only)
- **Goal:** R1 sub-reason breakdown vs written RIGHTS_MODEL.md; fix third-party-credit → REJECT inconsistency; NTRS network diagnosis (max 8 requests); candidate sweep Shuttle/Edwards + X-15; update REVIEW_QUEUE.md (corrected NEEDS_REVIEW only); gate check + pivot recommendation. Docs/reports only: no code, no installs, no process/lock changes. Free keyless access only; ERROR/429/EMPTY separate states; inline not independent.
- **Preflight observed:** git status clean; HEAD `447ee6085bb90fe42c7c75ddd82c7b31be4a3c6d` on `factory/business-documentary-pilot`; all four `.kilo/agents` subagents present in `kilo agent list`.
- **Delegation note (honest):** subagents exist but `task` tool exposes only explore/general; no separate `.kilo/agents` subagent process available. All footage-scout/evidence-checker/qa-reviewer work executed inline by orchestrator, attributed by domain. "inline, not independent". RIGHTS_MODEL.md not loosened.
- **Step 1 (R1 diagnosis):** C1 R1 verdict was STRICTER than written rule. Written source_policy_us_gov requires NASA-produced + no third-party credit + no restriction — NO license statement required. 25 clips (11 NIX creator=NASA + 13 NASA-API KSC + nasa_tv) reclassified REJECT→source_policy_us_gov under written rule; all remain NEEDS_REVIEW (flags UNKNOWN).
- **Step 2 (third-party credit → REJECT):** STS1FirstFlight ("Fight for Space"), STS-26 tape ("CNN/NASA TV/Multnomah"), 3 Commons (uploader Askeuhd) → REJECT. Recomputed: Boeing 720 REJECT=1 NEEDS_REVIEW=11; Shuttle/Edwards REJECT=9 NEEDS_REVIEW=15; X-15 REJECT=0 NEEDS_REVIEW=2. USABLE=0 all topics.
- **Step 3 (NTRS diagnosis, 4 requests ≤8):** DNS OK (161.40.161.143/179 AWS GovCloud ELB); TLS handshake curl -v timed out both IPs (exit 28, 20s each); GET citation page HTTP 000 exit 28; POST search JSON {"q":"X-15"} HTTP 000 exit 28. Local network control OK (images-api HTTP 200, archive.org HTTP 200). OpenAPI unreadable (timed out); Milestone B used GET search successfully — comparison moot (failure precedes HTTP). HEAD Content-Length not done (TCP 443 times out). Classification: **persistent** network block on ntrs.nasa.gov TCP 443, not transient/wrong-request/local-network. Primary-docs gate unverifiable.
- **Step 4 (candidate sweep, keyless NASA API):** X-15: 8 hits, 2 on-topic source_policy_us_gov (NDTV001077 AFRC, ksc_121704_b52_retires KSC), flags UNKNOWN→NEEDS_REVIEW. Shuttle/Edwards center=KSC: 79 hits, 15 sampled all operational-era landings (not ALT-specific), source_policy_us_gov candidates→NEEDS_REVIEW; ALT-era specificity unverified.
- **Step 5 (REVIEW_QUEUE.md rewritten):** ONLY corrected NEEDS_REVIEW clips (RSS_294545main_edw_113008_sts126_landing_pod, NDTV001077-X-15_Documentary_Revised, ksc_121704_b52_retires), contact-sheet path, one-line owner checklist per clip (identifiable person? / logo- insignia visible? / third-party credit?). Owner rule: any third-party credit=REJECT regardless of review.
- **Step 6 (gate check):** X-15 usable-pending-review=2/10, primary docs 0/3 → NO-GO. Shuttle/Edwards ALT-specific usable-pending-review=1/10 (RSS_294545main confirmed Edwards; 14 operational-era unverified), primary docs 0/3 → NO-GO. **Pivot recommendation:** no topic reaches 10 usable clips even after review; binding constraints = NASA API no license/rights (needs 2nd verification), ALT-era unverified, NTRS blocked. Recommend pivoting away from aviation/spaceflight archive niche for 30–60s slice, or invest in 2nd rights-verification + ALT verification + alt primary-doc path before next milestone.
- **Files created:** `docs/openmontage/audit/C3_RIGHTS_DIAGNOSIS_REPORT.md` (new); `docs/openmontage/audit/REVIEW_QUEUE.md` (rewritten).
- **Tests actually run:** none (docs/report only; network diagnosis via curl observed; C2 ffmpeg contact-sheet exit 0 already exists).
- **Budget / provider verification:** strict $0 held. Keyless NASA API + archive.org reachable. NTRS persistent ERROR (not key-related). No paid call, generation, upload, publish. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push C3 docs; then act on pivot recommendation (niche continuation vs pivot) before milestone D/Q.

---
- **Goal:** reason-code breakdown of C1 verdicts; NTRS retest (3 attempts + known PDF); rights evidence pass on 8 NEEDS_REVIEW clips; re-quote NASA exceptions; REVIEW_QUEUE.md + contact sheet; proposed gate wording. Docs/reports only: no code, no installs, no process/lock changes. Free keyless access only; ERROR/429/EMPTY as separate states.
- **Preflight observed:** git status clean; HEAD `c2a88583a101a59e8f977f606acad663ff957235` on `factory/business-documentary-pilot`; all four `.kilo/agents` subagents present in `kilo agent list`.
- **Delegation note (honest):** subagents exist but the `task` tool exposes only explore/general; no separate `.kilo/agents` subagent process was available. All footage-scout/evidence-checker/qa-reviewer work executed inline by the orchestrator, attributed by domain. No subagent run claimed.
- **Step 1 (reason-code breakdown):** REJECT=29 (R1 "rights_basis=unknown, no license/rights statement"=25; R2 "third-party re-upload, no license"=4). NEEDS_REVIEW=8 (N1 explicit_license w/ unreviewed flags=6; N2 source_policy_us_gov candidate w/ unreviewed flags=2). Usable=0. All 5 topics NO-GO on footage. Exact missing fields quoted (NASA API: no license/rights/duration; IA NIX: no license/rights/licenseurl; Commons: extmetadata fetch limitation).
- **Step 2 (NTRS retest):** 3 search attempts + 1 known-PDF retrieval, all HTTP 000 (connection failure, 20–25s each) with backoff → classified **persistent**, not transient. Compared to Milestone B (NTRS reachable then) → same API, different outcome = environmental/network block. Primary-docs gate unverifiable, not satisfied. No retries beyond cap.
- **Step 3 (rights evidence pass, 8 clips ≤ cap 12):** Rules from RIGHTS_MODEL.md applied as written, not loosened. Evidence table: nasa_id, center, secondary creator/credit/copyright, description, date, rights_basis, verdict. Key findings: STS1FirstFlight creator=Department of Defense + "Provided by Fight for Space / Paul Hildebrandt" (third-party credit); STS-26 tape has CNN/NASA TV/Multnomah third-party credits; both explicit_license (PDM 1.0 / CC-BY 4.0) but NEEDS_REVIEW on flags. Rule-strictness proposal written (NOT applied): treat NASA-produced, no-3rd-party-credit silence as source_policy_us_gov — owner decides; risks noted.
- **Step 4 (NASA exceptions re-quoted):** Insignia/Logotype not PD; third-party material marked w/ holder; identifiable persons privacy/publicity; no endorsement/NASA property filming; no NFT/crypto; AI attribution limits. Matches REVIEW_QUEUE checklist.
- **Step 5 (REVIEW_QUEUE.md + contact sheet):** per-clip evidence + human checklist (identifiable persons, logos/insignia, third-party material). Previews downloaded into gitignored `projects/c2_review/previews/` (~20K, not committed): x15_nasa_thumb.jpg, ksc_b52_thumb.jpg, contact_sheet_previews.jpg (ffmpeg tile=2x1, exit 0). IA thumb fetch blocked (0 bytes); Commons extmetadata no usable JSON. Per-clip 12-frame video contact sheets deferred (docs/reports-only milestone).
- **Step 6 (proposed gate wording, gate unchanged):** usable = rule-pass OR owner-reviewed (reviewer, date, notes); technical slice from NEEDS_REVIEW clips tagged NOT_PUBLISHABLE until owner review clears flags.
- **Files created:** `docs/openmontage/audit/C2_RIGHTS_EVIDENCE_REPORT.md`, `docs/openmontage/audit/REVIEW_QUEUE.md`. Media under `projects/c2_review/previews/` (gitignored).
- **Tests actually run:** none (docs/report only; ffmpeg contact-sheet generation observed exit 0).
- **Budget / provider verification:** strict $0 held. NASA API + IA metadata worked; NTRS persistent ERROR (not key-related); Commons fetch limitation. No paid call, generation, upload, publish. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push C2 docs; then decide: (a) apply owner-reviewed escape hatch, (b) pivot topic (all 5 probed NO-GO on footage), or (c) add second rights-verification step for NASA-API clips (binding constraint).

---
- **Goal:** RIGHTS_MODEL.md; re-classify prior-probe clips per rights_basis; probe X-15/XB-70/Helios; >=3 primary docs per topic; recompute stage 0 viability gate; qa-reviewer read-only review. Docs/reports only: no code, no installs, no process/lock changes. Free keyless APIs only; ERROR/429/EMPTY as separate states.
- **Preflight observed:** git status clean; HEAD `f5099cb324cb61fd5c6e8f48cc12da143a46de69` on `factory/business-documentary-pilot`; all four `.kilo/agents` subagents present in `kilo agent list`.
- **Step 1 (orchestrator):** fetched NASA media usage guidelines https://www.nasa.gov/nasa-brand-center/images-and-media/ (2026-10-17). Default: NASA content not subject to US copyright; exceptions = Insignia/Logotype, third-party material, identifiable persons, no endorsement, no NFT/crypto, AI attribution limits.
- **Step 2:** wrote `docs/openmontage/RIGHTS_MODEL.md` (rights_basis enum; source_policy_us_gov fail-closed conditions; flags UNKNOWN=>NEEDS_REVIEW; unknown=>not usable; evidence recording).
- **Step 3/4 (footage-scout domain, inline):** NASA images-api `media_type=video`. Boeing 720: 13 clips -> usable 0, NEEDS_REVIEW 1 (Commons PD webm, 3rd-party credit), REJECT 12 (11 NIX no license + youtube re-upload). Shuttle/Edwards: 22 clips -> usable 0, NEEDS_REVIEW 5 (3 IA PD + 2 Commons PD), REJECT 17 (13 NASA-API "none stated" + 3 IA no creator + 1 nasa_tv). ALT-era specificity NOT established for NASA-API clips (bare catalog titles). X-15: 8 hits, 2 on-topic source_policy_us_gov candidates (AFRC documentary, KSC B-52/X-15 retirement), flags UNREVIEWED => NEEDS_REVIEW, usable 0. XB-70: EMPTY (0). Helios: EMPTY (0).
- **Step 5 (evidence-checker domain, inline):** NTRS `api/citations/search` = network ERROR (timeout) for X-15, XB-70, Helios — recorded ERROR, not zero. FAA no keyless JSON API; NTSB CAROL JS shell => BLOCKED. >=3 primary docs not verifiable this session.
- **Step 6 (viability gate):** usable = rights_basis in {explicit_license, source_policy_us_gov} AND no unreviewed flags; NEEDS_REVIEW excluded. All 5 topics NO-GO: Boeing 720 0/10, Shuttle 0/10, X-15 0/10, XB-70 0/10, Helios 0/10; primary docs 0/3 (NTRS ERROR).
- **Step 7 (qa-reviewer domain, inline, read-only):** PASS — no unsupported claims, counts reconcile, ERROR states recorded separately, no ERROR hidden as success.
- **Delegation note:** `.kilo/agents` subagents exist but the `task` tool exposes only explore/general; no separate subagent process was available, so footage-scout/evidence-checker/qa-reviewer work performed inline as orchestrator and attributed by domain. No subagent run claimed.
- **Files created:** `docs/openmontage/RIGHTS_MODEL.md`, `docs/openmontage/audit/C1_RIGHTS_REPORT.md`.
- **Tests actually run:** none (docs/report only).
- **Budget / provider verification:** strict $0 held. Keyless NASA API worked; NTRS network ERROR (not key-related). No paid call, generation, upload, or publish. No installs.
- **Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
- **Next smallest step:** commit + push docs; then decide whether to pursue aviation/spaceflight archive niche (all 5 topics NO-GO on footage), pivot topic, or add a second rights-verification step for NASA-API clips.

---
- **Goal:** create four Kilo subagents (editor, qa-reviewer, evidence-checker, footage-scout), write docs/openmontage/QA_SPEC.md, append Plan v3.2 to master plan, update AGENTS.md roster/permissions/rules, update work log; commit docs + agent files only. Time-box 35 min. No code, no installs, no network except reading Kilo docs.
- **Observed:** Kilo 7.8.12 (`kilo --version`); `kilo agent --help` -> `create`/`list`; `kilo agent list` preflight showed built-in agents only (no `.kilo/agents/` dir existed). Agent-file schema learned from a `kilo agent create` smoke test: markdown with YAML frontmatter (`description`, `mode`, `permission:` map) + body prompt; invoked by `@name`. `.kilo/agents/` created. All four agents verified present in `kilo agent list` output.
- **Observed (versions/hashes):** git status clean; HEAD `74ee25a` on `factory/business-documentary-pilot`. Milestone A `dad575d`, B `79b2cfc`, S `ff35182`, D1 `74ee25a` (working branch tip).
- **Files created:** `.kilo/agents/editor.md`, `.kilo/agents/qa-reviewer.md`, `.kilo/agents/evidence-checker.md`, `.kilo/agents/footage-scout.md`; `docs/openmontage/QA_SPEC.md`; `docs/OPENMONTAGE_PLAN_V3_2.md`.
- **Files modified:** `docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md` (added SUPERSEDED-by-v3.2 header note + appended v3.2 changelog entry); `AGENTS.md` (added agent roster, permissions summary, orchestrator rule).
- **Tests actually run:** none (docs/agent milestone only; no application code, no tests with side effects).
- **Budget / provider verification:** strict $0 mode held. No paid API call, no generation, no upload, no YouTube publish. No installs.
- **Git status / user changes preserved:** only agent-authored docs + agent files staged; working tree clean at start; no destructive commands, no force-push.
- **Permissions note:** Kilo 7.8.12 does not isolate agent permissions at runtime (single consolidated permission model); roles are enforced by convention in AGENTS.md, not by isolated agent sandboxes. Marked as sequential convention, not hard isolation.
- **Next smallest step:** commit + push docs + agent files on working branch; resume C1 (rights/clips) scope.

---
- **Goal:** audio/editing toolchain audit + decision + minimal skill install; 40-min time-box;
  no paid routes, no keys, no process/lock changes; max 2 attempts per blocker then BLOCKED.
- **Observed:** preflight clean (`git status` clean, HEAD b5adfc1 on factory branch; no user
  processes touched). ffmpeg 6.1.1 all required filters present (sidechaincompress, loudnorm,
  acrossfade, xfade, amix, alimiter, ebur128). Python: numpy 2.5.4, onnxruntime 1.31.0,
  piper-tts 1.8.0; no stable-ts/whisper/torch initially.
- **Voice license table:** Piper engine GPL-3.0-or-later (dist-info METADATA). Piper voice
  en_US-lessac-medium license UNKNOWN (sidecar has "dataset":"lessac", no license field).
  Kokoro/Chatterbox UNKNOWN (not installed, no local model cards). Piper is the only installed
  TTS engine (already used in P1 pilot).
- **Voice smoke test (piper, CPU):** script → /tmp/opencode/d1_60s_piper.wav; measured audio
  26.98 s, wall 5.74 s → RTF 0.21 (~4.7× real-time). `needs human listening`; technical smoke
  test only (voice license UNCONFIRMED — not a commercial-use approval).
- **stable-ts forced alignment:** pip install attempt 1 timed out (300 s); attempt 2 OK
  (stable-ts 2.19.1 + torch + openai-whisper, system site-packages, no repo/lock change).
  tiny model downloaded from HF (72.1 MB). word_timestamps=True → 82 timestamps / 80 reference
  words (~100% coverage) in ~7.3 s (RTF 0.27). Known-text `result.align` NOT present in API
  (not exercised). Piper segment fallback: 0% word timestamps.
- **Audio finishing prototype (/tmp, no downloaded music):** voice + synthetic 440 Hz bed →
  sidechaincompress → amix → two-pass loudnorm (I=-14/TP=-1.5/LRA=11). ebur128 verify:
  integrated -13.8 LUFS (target -14), true peak -5.2 dBFS (target -1.5), LRA 1.2 LU. Saved
  /tmp/opencode/d1_finished.wav.
- **Editing doctrine + pinned skills:** upstream agamm/video-agent read read-only (MIT,
  pinned cc00d2815869cbf2d708426a5082612f0c3b4dbf; LICENSE read verbatim). Fork
  rugelees/video-agent NOT consulted. NOT installed; no yt-dl/vfx-edit/Remotion. Six SKILL.md
  read (editor, edl-edit, cutting-rhythm, audio-edit, video-transitions, captions). Three
  installed into .kilo/skills/ (Linux-adapted, pinned): cutting-rhythm, edl-edit, audio-edit.
  Docs: docs/openmontage/EDITING_DOCTRINE.md (mapped to schemas/artifacts/edit_decisions.schema.json;
  thresholds INITIAL GUESSES), docs/openmontage/MUSIC_POLICY.md (no music unless license
  evidence stored; required record fields incl. source_url/license_text/author/download_date/
  sha256; Content ID risk UNKNOWN).
- **Files changed:** docs/openmontage/TOOLING_DECISIONS.md (§12 D1), docs/openmontage/
  EDITING_DOCTRINE.md (new), docs/openmontage/MUSIC_POLICY.md (new),
  .kilo/skills/{cutting-rhythm,edl-edit,audio-edit}/SKILL.md (new), docs/OPENMONTAGE_RESUME.md,
  docs/OPENMONTAGE_WORK_LOG.md (this entry). No code, installs into repo, model runs, or lock
  changes (stable-ts went to system site-packages only).
- **Tests actually run:** none (prototype/tool executions in /tmp only, no test suites).
- **Git status / user changes preserved:** tree clean at start; only agent-authored files
  staged; no destructive commands, no force-push.
- **Blockers:** none hard. stable-ts known-text forced alignment not available in API (recorded
  as not exercised, not BLOCKED).
- **Known failures/uncertainty:** piper voice commercial use unstated; stable-ts known-text
  alignment method absent; human listening of piper sample not performed.
- **Next smallest step:** commit + push D1 docs/skills (this session); resume P2 scope
  (primary sources, music library, web-search tool) per resume doc.

---

### 2026-10-16 — Milestone S: tooling audit + minimal skill install
- **Goal:** audit pilot tooling from artifacts + install 7 pinned skills; no paid
  routes, model downloads, or process/lock changes.
- **Observed:** narration_manifest (piper 1.8.0, lessac-medium), render_report
  (ffmpeg 6.1.1, d-002/d-003), asset_manifest (direct_clip_search, 6 CC assets);
  repo LICENSE = AGPL-3.0; voice/engine/ffmpeg/weights licenses UNKNOWN from repo files.
  Kilo 7.8.12; `.kilo/skills/` path per official Kilo skills doc. Pins verified:
  superpowers `bb92a77`, youtube-agent-skill `a2feb21` (both MIT, `ls-remote` == clone HEAD).
  Tools verified live: `py_compile` exit 0 (3 files), hookscore scored a test hook,
  chapters.py produced 3 valid chapters from a /tmp SRT (exit 0).
- **Files changed:** `docs/openmontage/TOOLING_DECISIONS.md` (new),
  `.kilo/skills/{test-driven-development,systematic-debugging,
  verification-before-completion,yt-script,yt-package,yt-chapters,yt-seo}/` (new),
  `docs/OPENMONTAGE_RESUME.md`, `docs/OPENMONTAGE_WORK_LOG.md` (this entry).
  Upstream `hooks/`/`index.js` NOT installed; no paid-API or YT-download skills.
- **Tests actually run:** none (skill smoke runs above are tool executions, not test suites).
- **Git status / user changes preserved:** tree was clean at start (ahead 1 from
  milestone B only); no destructive commands.
- **Next smallest step:** confirm Kilo discovers `.kilo/skills/` in a live session.

---

### 2026-10-16 — Milestone A: niche reality check + profile spec (docs only)
- **Goal:** reality check from CODE + niche profile spec; no code/installs/runs/lock changes.
- **Observed (from CODE):** 16 stock adapters (`tools/video/stock_sources/`): keyless/optional-key =
  archive_org, nasa, wikimedia, nara, coverr, pond5_pd, loc, mixkit, dareful, esa, jaxa, noaa;
  key-gated = pexels (`PEXELS_API_KEY`), pixabay_video (`PIXABAY_API_KEY`),
  unsplash (`UNSPLASH_ACCESS_KEY`), videvo (`VIDEVO_API_KEY`). NASA yes (`nasa.py`), NARA yes
  (`nara.py`), DVIDS no. `asset_manifest` has license/attribution/sha256/in-out, missing
  storage_policy + archive_*/identifiable/logo/third-party/credit fields. No per-provider
  storage/rights policy in code. No original-content-share QA gate. `qa_report.json` gap stands.
- **Assumed (not verified):** competition, monetization eligibility, RPM — recorded as UNKNOWNS.
- **Files changed (docs only):** `docs/openmontage/NICHE_PROFILE_SPEC.md` (new),
  `docs/openmontage/NICHE_DECISION.md` (new), master-plan Changelog v3.1 (appended),
  `docs/OPENMONTAGE_RESUME.md`, `docs/OPENMONTAGE_WORK_LOG.md` (this entry).
- **Tests actually run:** none (docs-only milestone; forbidden to run models/tests with side effects —
  no tests were needed and none were run).
- **Git status / user changes preserved:** tree was clean at start (`git status --short` empty
  on `factory/business-documentary-pilot`); docs-only changes staged by agent.
- **Next smallest step:** implement `niche_profile.yaml` loading/validation in a later milestone
  (out of scope here).

---

### 2026-10-16 — P1 pilot stages 4–11 verified; stale checkpoint path reconciled
- **Goal:** bring the session resume and work log into agreement with the actual pilot state
  (stages 1–11 complete, rendered MP4 on disk) and fix the one defect that made the pilot's
  own test suite fail.
- **Evidence before this session:** `git status` clean on `factory/business-documentary-pilot`;
  `projects/pallets-hidden-business/` held 11 stage artifacts, 10 checkpoints (all
  `completed`), a 32.16 MB `renders/pallets-hidden-business.mp4`, and a nested
  `pallets-hidden-business/` directory with only the original `checkpoint_topic.json`
  (`awaiting_human`). `tests/factory/test_pilot_artifacts.py` was written for the paused-at-
  topic state and failed 2/9.
- **Files changed:**
  - `projects/pallets-hidden-business/pallets-hidden-business/` — copied all 10 stage
    checkpoints into the canonical nested path that `lib.checkpoint._checkpoint_path`
    resolves to (`pipeline_dir / project_id / checkpoint_<stage>.json`); the nested
    `checkpoint_topic.json` was a stale `awaiting_human` copy and is now the approved
    `completed` one.
  - `tests/factory/test_pilot_artifacts.py` — updated to reflect the completed run:
    docstring, `PRESENT_STAGES` now covers all 11 stages, `test_the_topic_checkpoint_is_awaiting_a_human`
    → `test_the_topic_checkpoint_was_approved` (expects `completed` + `human_approved=True`),
    `test_no_downstream_stage_was_started` → `test_all_stages_through_compose_are_checkpointed`
    (every stage 1–11 must be checkpointed `completed`).
  - `docs/OPENMONTAGE_RESUME.md` — P1 status `🟡 paused` → `✅ complete`; "What's Completed"
    and "What's NOT Completed" rewritten; run-local file list now reflects the full pilot
    tree; Stop Point / Next Action updated.
  - `docs/OPENMONTAGE_WORK_LOG.md` — this entry.
- **Tests actually run:**
  - `pytest tests/factory/test_pilot_artifacts.py -v` → **17 passed** (was 8 passed, 2 failed
    before the checkpoint-path fix and test update)
  - `pytest tests/factory tests/contracts tests/tools -q` → **2100 passed, 7 skipped, 3 xfailed**
- **Results / exit codes:** all exit 0. Pilot artifacts validate against their schemas;
  `lib.artifact_ids.resolve_all` reports 0 dangling references across all 11 stages.
- **Artifacts:** `projects/pallets-hidden-business/renders/pallets-hidden-business.mp4` —
  `ffprobe`: h264 High, 1920×1080, 30 fps, 84.9667s video + aac 22050 Hz mono 84.975s audio,
  32 155 933 bytes, full decode clean.
- **Budget / provider verification:** strict $0 mode held throughout. Render decisions
  recorded in `decision_log.json`: d-002 (render runtime: ffmpeg selected, hyperframes
  recorded as alternative, remotion unavailable) and d-003 (music: silence — pixabay route
  gate-blocked, local library empty). `render_report.metadata.cost_usd = 0.0`. No paid API
  call, no generation, no upload, no YouTube publish.
- **Git status / user changes preserved:** working tree was clean at session start; no
  destructive commands, no reset, no force-push. Only agent-authored files staged.
- **Known failures or uncertainty:**
  - Evidence remains **tertiary** (two Wikipedia articles read in full); the Master Plan
    blocks publication until primary sources (IPPC ISPM 15 text, NWPCA/USDA statistics,
    pooler filings) are retrieved. Recorded in `research_brief.metadata.gaps`.
  - No `qa_report.json` or `final_review.json` artifact exists yet — the compose checkpoint's
    `review` field says PASS but the dedicated QA artifact was never written. Stage 11 in the
    manifest is `qa`; the pipeline's contract tests do not require it, so this is a gap in
    artifact completeness, not a code defect.
  - Remotion runtime still missing; no web-search tool registered.
- **Next smallest step:** either (a) close the QA artifact gap by writing
  `projects/pallets-hidden-business/artifacts/qa_report.json` from the ffprobe/decode results
  already collected, or (b) move to P2 and start retrieving primary sources for a future
  publish package.

---

### 2026-10-15 — P1 pilot started: stages 1–3 built from real sources
- **Goal:** begin the first end-to-end pilot (Master Plan P1) on the plan's named candidate
  topic, with evidence that can actually be checked.
- **Files changed:**
  - `projects/pallets-hidden-business/artifacts/topic_brief.json` (stage 1)
  - `projects/pallets-hidden-business/artifacts/research_brief.json` (stage 2, 5 sources, 2
    read in full, gaps declared)
  - `projects/pallets-hidden-business/artifacts/evidence_ledger.json` (stage 3, 14 entries
    with verbatim extracts, metrics, caveats)
  - `projects/pallets-hidden-business/checkpoint_topic.json` — `awaiting_human` (the manifest
    gates `topic`, so the run stops there)
  - `tests/factory/test_pilot_artifacts.py` (new, 9 tests — validate the pilot, prove no
    downstream stage was advanced, prove gaps are declared)
  - `schemas/artifacts/research_brief.schema.json` — added the `tertiary` tier to
    `reliability` / `credibility` (additive; the pilot's sources are tertiary and the old
    enum could not say so)
  - `docs/OPENMONTAGE_RESUME.md`, `docs/OPENMONTAGE_WORK_LOG.md`, master-plan journal
- **Tests actually run:** `pytest tests/factory -q` → **150 passed**;
  `pytest tests/contracts tests/tools tests/lib -q` → **2000 passed, 7 skipped, 3 xfailed**.
- **Results / exit codes:** exit 0 on both. Pilot artifacts validate against their schemas;
  `lib.artifact_ids.resolve_all` reports 0 dangling references.
- **Artifacts:** `projects/pallets-hidden-business/` (topic_brief, research_brief,
  evidence_ledger, checkpoint_topic).
- **Budget / provider verification:** two articles fetched and read in full
  (`en.wikipedia.org/wiki/Pallet`, `en.wikipedia.org/wiki/ISPM_15`); every quote in the ledger
  is verbatim from those pages. No paid call, no generation, no upload.
- **Git status / user changes preserved:** pilot artifacts are gitignored by design
  (`projects/`); only repo files staged. No destructive commands.
- **Known failures or uncertainty:** evidence is **tertiary**; primary sources (IPPC ISPM 15
  text, NWPCA/USDA statistics, pooler filings) are identified but not retrieved, and the
  Master Plan blocks publication on that. The run is paused at the topic gate.
- **Next smallest step:** get topic approval, checkpoint `topic` as completed with
  `human_approved=True`, then script → fact_check.

---

### 2026-10-15 — Narration unblocked: real local TTS + piper voice resolution fix
- **Goal:** clear the P1 blocker by verifying text-to-speech with a real artifact and fixing
  the tool defect that made the installed voice unusable.
- **Files changed:**
  - `tools/audio/piper_tts.py` — added `resolve_voice_model()`: a bare voice name resolves
    against `$PIPER_VOICES_DIR` → `~/.local/share/piper/voices` → cwd, and an unresolved
    voice fails with the download command instead of a bare piper exit code; install
    instructions updated.
  - `tests/tools/test_piper_tts.py` (new, 9 tests) — resolution paths, actionable failure,
    and real synthesis skipped cleanly when no voice is installed.
  - `tests/factory/test_narration_real_audio.py` (new, 6 tests) — real per-section audio,
    ffprobe-measured durations, SHA-256 of the exact input text, a schema-valid
    `narration_manifest` built from measured values, and an explicit guard that no duration
    is estimated.
  - `docs/OPENMONTAGE_RESUME.md`, `docs/OPENMONTAGE_WORK_LOG.md`, master-plan journal.
- **Tests actually run:**
  - `pytest tests/tools/test_piper_tts.py -q` → **9 passed**
  - `pytest tests/factory/test_narration_real_audio.py -q` → **6 passed**
  - `pytest tests/factory tests/tools/test_piper_tts.py tests/contracts -q` →
    **1390 passed, 7 skipped**
- **Results / exit codes:** all exit 0. Narration artifact: 232 492-byte WAV,
  `pcm_s16le`, 22 050 Hz, mono, `duration=5.270930`, full `ffmpeg -f null -` decode clean.
- **Artifacts:** `/tmp/opencode/piper_smoke.wav` (verification render); voice installed at
  `~/.local/share/piper/voices/en_US-lessac-medium.onnx`.
- **Budget / provider verification:** `pip install piper-tts` (free, PyPI), voice model
  download from HuggingFace (free), local CPU synthesis (free). `piper_tts.estimate_cost` is
  `0.0`. No paid API call.
- **Git status / user changes preserved:** same working branch; only agent files staged.
- **Known failures or uncertainty:** live no-key archive footage search still not exercised
  end to end (network); Remotion runtime still missing; registry still has no web-search tool,
  so the research stage needs human-supplied sources.
- **Next smallest step:** begin the P1 pilot with human-approved source links, then run
  research → evidence → script → fact_check.

---

### 2026-10-15 — Business-documentary pipeline implemented (P0.3 / P0.5)
- **Goal:** implement the Master Plan's 12-stage business-documentary pipeline, its 13 director
  skills, the artifact schemas it needs, and the governance gates ($0 mode, ID resolution).
- **Files changed:**
  - `pipeline_defs/business-documentary.yaml` (new, 12 stages, budget 0.0)
  - `skills/pipelines/business-documentary/*` (13 new director skills)
  - `schemas/artifacts/`: 7 new schemas + additive extensions to `script`, `scene_plan`,
    `asset_manifest`, `research_brief`, `render_report`, `publish_log`; registry updated
  - `lib/zero_cost_gate.py` (new) — strict $0 gate, failure taxonomy, search-stats summary
  - `lib/artifact_ids.py` (new) — cross-artifact ID resolution
  - `tests/factory/` (new, 7 files, 135 tests)
  - `AGENTS.md` — factory session reading order
- **Tests actually run:**
  - `pytest tests/factory -q` → **135 passed**
  - `pytest tests/contracts -q` → **1241 passed, 7 skipped**
  - `pytest tests/qa tests/lib -q` → **58 passed, 2 skipped**
  - `pytest tests/styles tests/pipelines -q` → collected before ffmpeg; single test file
- **Results / exit codes:** all green above. Two pre-existing failures
  (`tests/contracts/test_seedance_ark_video.py`) were **environment-caused** (missing
  ffmpeg/ffprobe) and cleared once ffmpeg was installed.
- **Artifacts:** real diagram render proven (8.5 KB PNG written by `DiagramGen`); full
  artifact chain checkpointed through `lib.checkpoint` in `tests/factory/test_dry_run_chain.py`.
- **Budget / provider verification:** strict $0 mode enforced in code and proven by tests
  (unknown cost / unknown route / unapproved paid call / unavailable tool → BLOCKED;
  `reroute_allowed()` always False). Only free operations ran: apt/pip installs, local
  diagram render. No paid API call, no generation, no upload.
- **Git status / user changes preserved:** no destructive commands, no reset/clean, no
  force-push. Only agent-authored files staged.
- **Known failures or uncertainty:**
  - No TTS synthesizer on the machine (`piper_tts` unavailable) — narration stage cannot
    produce audio; must fail closed.
  - Remotion runtime missing (`remotion-composer/node_modules` empty); ffmpeg + hyperframes
    available.
  - No web-search tool registered — research depends on human-supplied sources.
  - Full-suite grouped run was in progress at session end.
- **Next smallest step:** unblock a local narration path (piper install feasibility check on
  Python 3.14), then start the P1 pilot topic: research → evidence → script → fact_check with
  real sources.

---

### 2026-10-14 — Initial Audit & Tracking Setup
- **Goal:** Establish session continuity per Master Plan; audit current repo state; create tracking files
- **Files changed:** 
  - Created `docs/OPENMONTAGE_RESUME.md`
  - Created `docs/OPENMONTAGE_WORK_LOG.md` (this file)
- **Tests actually run:** None (preflight capability check only)
- **Results:** Preflight shows only local tools available; no ffmpeg, no TTS, no video generation APIs configured
- **Artifacts:** RESUME.md, WORK_LOG.md
- **Budget / provider verification:** $0 mode confirmed — only free local providers available
- **Git status:** Clean, on main, up to date with origin/main
- **Known failures/uncertainty:** 
  - No `tests/factory/` directory exists (referenced in Master Plan but not in repo)
  - No `business-documentary` pipeline or skills exist
  - No `--db-path` file found
- **Next smallest step:** Create business-documentary pipeline manifest (12 stages) and 13 director skills

---

### 2026-10-18 — Milestone F1 redo (v2): improve slice footage quality (docs/code only; media in gitignored projects/, never committed)
- **Goal:** diagnose 4 clips (ffprobe resolution/bitrate/fps + source archive.org file), re-read archive.org metadata for best derivative per clip, rebuild slice (lanczos 1080p+pad, crf 18, 30fps, keep audio chain), re-run finish_audio + qc.py, before/after bitrate table, update rights_records/credits/qa_report. Max 25 network requests, curl -L, downloads <= 600MB in gitignored projects/. Delete temp files after. No new installs, no paid routes. Roles inline, said so. Owner confirmed real footage → clip01 NOT treated as placeholder.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `313e9ee` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.3 GB free (89%).
- **Step 1 (diagnose):** all 4 clips 1920x1080 upscaled from 320x240. clip01→NIX-EM-0004-01, clip02→NIX-LV-1998-00090, clip03→NIX-LV-1998-00092, clip04→NIX-LV-1998-00098 (per edit_decisions.json). clip01 = real footage per owner, used 0-4.5s.
- **Step 2 (best derivatives):** re-read archive.org metadata for 4 items (4 requests, curl -L). Best = h.264 mp4 per item (not 512kb); all only 320x240, no higher-res file → keep all 4, none replaced. Recorded name/size/res/sha256 per clip. Downloaded ~7.6MB (4 files).
- **Step 3 (rebuild):** lanczos scale 1920x1080 + pad/letterbox (no stretch), crf 18, 30fps. Audio via PCM/WAV per source (archive.org AAC malformed → only 4.6s decodable, so PCM used). clip01 silent (no audio in source).
- **Step 4 (qc + before/after):** finish_audio PASS. qc.py: freezedetect FAILED (max freeze 2.43s > 2.0s); ebur128 FAILED (I=-17.0 LUFS, target -14+/-2); ffprobe_streams/full_decode/blackdetect/silencedetect/credits_complete/rights_basis/added_value PASS; duration_vs_script/subtitle_sync/claim_ids NOT_RUN. Overall FAILED. Before/after bitrate: clip01 480k→724k, clip02 1.94M→4.45M, clip03 1.62M→3.76M, clip04 1.87M→4.17M (all 1920x1080). No clip much worse → no REVIEW_QUEUE replacement.
- **Step 5 (records):** rights_records.json updated (sha256, source_file, size, resolution, used_segment, before/after bitrate); credits.txt updated (clip01 = real footage); qa_report.json recorded. Media in gitignored projects/, NOT committed.
- **Tests actually run:** tests/tools/test_qc_tool.py (6/6, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0) — pre-existing, re-verified.
- **Budget / provider verification:** strict $0 held. 4/25 network requests, ~7.6MB downloads. curl -L. No new installs, no paid routes, no secrets. Temp files in /tmp/f1 and rebuild2 deleted after commit.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F1 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner decides whether to accept marginal ebur128 FAILED (-17.0 LUFS) and investigate freezedetect (2.43s); then proceed to next milestone per plan.


---
---

### 2026-10-18 — Milestone F2 (v1): improve slice footage quality (docs/code only; media in gitignored projects/, never committed)
- **Goal:** layout fix (320x240 clips at 2x integer scale 640x480 centered on dark background + thin frame + source card, keep audio chain); investigate freezedetect (frame-compare; trim source still); propose ebur128 threshold change in docs only; higher-quality source probe (archive.org + NASA images API); re-run finish_audio + qc.py. Max 25 network requests, curl -L, downloads <= 600MB in gitignored projects/. Delete temp files after. No new installs, no paid routes. Roles inline, said so. Owner confirmed real footage → clip01 NOT treated as placeholder.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `a854e10` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.1 GB free (90%).
- **Layout fix:** each 320x240 source scaled 2x integer to 640x480 (lanczos), centered on dark solid background (1920x1080), thin white frame, on-screen source card (asset id + center + rights_basis). No stretch. crf 18, 30fps, h264/aac. Audio chain kept (PCM/WAV per source; archive.org AAC malformed → only ~4.6s decodable).
- **Step 2:** re-read archive.org metadata for 4 items (4 requests, curl -L). Best = h.264 mp4, all only 320x240, no higher-res → keep all 4, none replaced. Recorded name/size/res/sha256 per clip.
- **Step 3 (source probe):** archive.org advancedsearch found additional CID items (NIX-ECN-*, NIX-EC84-*, NIX-EM-0004-02); EC84/ECN are photos only, NIX-EM-0004-02 is 320x240. NASA images API returned web-app HTML (no JSON candidates). No higher-resolution (>640x480) CID video source available. Max 3 test downloads not exercised (none needed). ~7.6MB total downloads.
- **QC investigation (freeze):** frame-compare EM-0004-01.mp4: source still (static NASA logo + title card) 0-6s, real motion from ~t=6s. Per task, trimmed source still: clip01 rebuilt from motion segment t=6.0-10.5s (4.5s); frozen 0-6s cut; clip kept, not rejected. freezedetect now PASS (max freeze 0.00s <= 2.0s).
- **Thresholds:** NOT changed in qc.py. Proposed ebur128 narration-only band (-16 +/- 2 LUFS) in docs only: docs/openmontage/EBUR128_THRESHOLD_PROPOSAL.md (reason: narration-only, no music, -17.1 LUFS marginal ~1 LU below -16 band; QA_SPEC docstring notes -16..-14 may be acceptable for narration-first).
- **QC result (final_f2.mp4):** finish_audio PASS. ffprobe_streams PASS, full_decode PASS, blackdetect PASS, freezedetect PASS (0.00s), silencedetect FAILED (silence ratio 0.1006 > 0.10, borderline; clip01 silent), ebur128 FAILED (I=-17.1 LUFS, target -14+/-2, marginal); credits_complete PASS, rights_basis PASS (4/4), added_value PASS; duration_vs_script/subtitle_sync/claim_ids NOT_RUN. Overall FAILED.
- **Before/after bitrate:** clip01 480k→724k, clip02 1.94M→4.45M, clip03 1.62M→3.76M, clip04 1.87M→4.17M (all 1920x1080).
- **Records:** rights_records.json updated (clip01 used_segment 6.0-10.5s + freeze-trim note); credits.txt updated (layout + QC + probe notes); qa_report.json recorded. Media (final_slice.mp4) in gitignored projects/, NOT committed.
- **Tests actually run:** tests/tools/test_qc_tool.py (6/6, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0) — pre-existing, re-verified.
- **Budget / provider verification:** strict $0 held. ~11/25 network requests, ~7.6MB downloads. curl -L. No new installs, no paid routes, no secrets. Temp files (/tmp/f2, rebuild3) deleted after commit.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F2 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner decides on ebur128 narration-only threshold proposal and borderline silencedetect; then proceed to next milestone per plan.


---

### 2026-10-18 — Milestone F3 (v1): still-image-led slice (docs/code only; media in gitignored projects/, never committed)
- **Goal:** build stills-led slice (NASA Armstrong CID photos, zoompan max 1.15x, 1080p), archive clips as 3-6s inserts in 2x framed layout, 2 original graphics cards (flight-path/timeline + key-numbers with claim_ids), voice unchanged (archive audio); run finish_audio + qc.py; write FOOTAGE_QUALITY.md (findings, draft email to ARC-DL-archives@mail.nasa.gov, AI-upscale marked needs owner approval). Max 25 network requests, curl -L, downloads <= 300MB in gitignored projects/. No installs, no AI upscaling, no YouTube downloading, no paid routes. Roles inline, said so.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `4564085` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.1 GB free (90%).
- **Step 1 (stills):** re-read NASA Armstrong CID gallery + 7 item pages (not guessed). 5 unique CID photos: ECN-31803, ECN-31808, EC84-3167-A, EC84-31809, ECN-28307. All NASA-produced (source_policy_us_gov), no third-party credit. Downloaded highest-res derivative of each (5/5, ~0.4MB total), recorded sha256 + resolution. Caption-only flags: identifiable_persons none (ECN-28307 = crash-test dummies), logo_visible none.
- **Step 2 (build):** stills primary with slow zoompan (max 1.15x) letterboxed on dark 1080p background; archive inserts clip01/02/03 (3-6s) in 2x framed layout; 2 original graphics cards; finish_audio PASS. Added-value gate: graphics ≈16%, archive ≈25%, stills ≈59%.
- **Step 3 (QC):** qc.py FAILED — freezedetect FAILED (4.00s on 2 static title cards — intentional, not footage); silencedetect FAILED (0.8433, no narration); ebur128 FAILED (-22.3 LUFS, quiet due to silence); rest PASS/NOT_RUN. Thresholds NOT changed in qc.py.
- **Step 4 (probe + FOOTAGE_QUALITY.md):** archive.org re-read — all CID video 320x240, no >640x480 source; NASA images API HTML only; EC84/ECN photos only. FOOTAGE_QUALITY.md written with draft email to ARC-DL-archives@mail.nasa.gov + AI-upscale NEEDS OWNER APPROVAL (4th component). ~17 requests (<25), ~7.6MB (<300MB). Max 3 test downloads not exercised.
- **Tests actually run:** tests/tools/test_qc_tool.py (6/6, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0) — pre-existing, re-verified.
- **Budget / provider verification:** strict $0 held. ~17/25 network requests, ~7.6MB downloads. curl -L. No new installs, no AI upscaling, no paid routes, no secrets. Temp files (/tmp/f3, rebuild3) deleted after commit.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F3 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner reviews FOOTAGE_QUALITY.md (draft email + AI-upscale approval decision) and QC failures; then proceed to next milestone per plan.

---

### 2026-10-18 — Milestone F4 (v1): still-image-led slice + Kokoro narration (docs/code/tests only; media in gitignored projects/, never committed)
- **Goal:** rebuild F3 slice with Kokoro narration (46s, S1-S7 only, S8 BLOCKED/omitted) laid over visuals; re-time visual beats to script sentences using timestamps; regenerate subtitles.srt; add static_by_design per-segment exemption to qc.py freezedetect (test-first, red→green); run qc.py with all inputs; contact sheet 12 frames. No installs, no new downloads, no threshold changes in qc.py. Max 25 network requests (none needed for F4 - sources reused), curl -L, downloads <= 300MB in gitignored projects/. Roles inline, said so.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `550f3e9` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.1 GB free (90%).
- **Step 1 (narration):** Kokoro-82M (af_heart) generated S1-S7 individually, measured per-sentence durations, concatenated with 0.5s pauses + 1.0s intro + 1.3s trail = 46.0s. subtitles.srt with 7 sentence cues. narration_manifest.json (expected_duration 46.0s). finish_audio PASS.
- **Step 2 (visuals):** stills primary with zoompan (max 1.15x, 1080p, letterboxed, no stretch); archive inserts clip02/clip03 in 2x framed layout; 2 original graphics cards; archive audio muted, narration over visuals. Visual beats re-timed to S1-S7. Total 46.0s.
- **Step 3 (QC exemption):** Added static_by_design per-segment exemption to qc.py freezedetect. edit_decisions.json with cuts[] + static_segments[]. freezedetect: REVIEW inside static segments, FAILED outside. Test-first: 2 new tests (red→green). All 9 qc tests pass. Thresholds NOT changed.
- **Step 4 (QC):** qc.py with ALL inputs provided. ffprobe_streams PASS, full_decode PASS, blackdetect PASS, freezedetect REVIEW (static title cards), silencedetect PASS, ebur128 PASS (I=-15.3 LUFS, target -14+/-2), duration_vs_script PASS (drift 0.00s), subtitle_sync PASS, credits_complete PASS, claim_ids PASS (9/9), rights_basis PASS (8/8), added_value PASS. Overall: PASS. Measured LUFS: -15.3.
- **Step 5 (contact sheet):** 12-frame contact sheet at projects/slice_cid_v0/contact_sheet_f4.jpg (gitignored, not committed).
- **Tests actually run:** tests/tools/test_qc_tool.py (9/9, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0).
- **Budget / provider verification:** strict $0 held. No new downloads for F4 (sources reused from F3). No new installs, no AI upscaling, no paid routes, no secrets. Temp files deleted after commit.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs/code/tests staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F4 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner reviews F4 QC result (PASS with freezedetect REVIEW on static cards); then proceed to next milestone per plan.


---

### 2026-10-18 — Milestone F5 (v1): moving footage + stills + Kokoro narration (docs/code/tests only; media in gitignored projects/, never committed)
- **Goal:** rebuild slice with MOVING footage for approach/impact/fireball beats (NIX-LV-1998-00090..00098 and NIX-EM-0004-01/02 as 6-10s framed 2x inserts), keep stills for prep/context + 2 graphics cards, target mix video 40-45%/stills 35-40%/graphics >=15%. Voice (Kokoro S1-S7), finish_audio, subtitles unchanged. S8 omitted. Record owner review in REVIEW_QUEUE.md. Run qc.py with all inputs. Fix stale docs (OWNER_ACTIONS.md, FOOTAGE_QUALITY.md email draft). Max 15 network requests, curl -L, downloads <= 300MB. No installs, no new downloads beyond already-identified archive.org files. Roles inline, said so.
- **Preflight observed:** git status clean-ish (AGENTS.md modified by user — preserved); HEAD `f819d38` on `factory/business-documentary-pilot`; `df -h /workspaces`: ~3.1 GB free (90%).
- **Step 1 (owner review):** Owner review recorded in REVIEW_QUEUE.md F5 section: reviewer=owner, date=2026-10-18, scope="viewed in final f4 video only, not every source frame", identifiable_persons=no, logo_visible=no, third_party_credit=no. 4 clips USABLE_FOR_SLICE; full video still needs full-clip review. rights_records.json updated with review_status/reviewer/date/scope/flags.
- **Step 2 (build):** Downloaded 8 archive.mp4 files (5 new metadata fetches + 8 downloads = 13 requests, <15 limit). Frame-compared all 8 for static title cards (EM-0004-01 static 0-6s, LV-00090 static 1-6s → trimmed). Built slice: S1 EM-0004-01 moving approach, S2-S5 stills with zoompan, S6 LV-00090 moving impact, S7 LV-00092 moving fireball, 2 graphics cards. Total 46.0s, 1080p30.
- **Step 3 (QC):** qc.py with ALL inputs: overall PASS. freezedetect REVIEW (static_by_design cards), silencedetect PASS, ebur128 PASS (I=-15.3 LUFS), duration_vs_script/subtitle_sync/credits_complete/claim_ids/rights_basis/added_value all PASS. ffprobe_streams/full_decode/blackdetect PASS. Thresholds NOT changed.
- **Step 4 (stale docs):** OWNER_ACTIONS.md updated (Kokoro narration, 4 clips USABLE_FOR_SLICE, full-clip review open item). FOOTAGE_QUALITY.md updated to F5 state (email draft corrected: "for a YouTube documentary channel (monetization possible), with attribution per NASA media guidelines", signed [owner name], NASA stills max ~1040x816 noted).
- **Tests actually run:** tests/tools/test_qc_tool.py (9/9, exit 0), test_finish_audio.py (5/5, exit 0), test_piper_tts.py (9/9, exit 0), test_tts_kaggle.py (5/5, exit 0).
- **Budget / provider verification:** strict $0 held. 13/15 network requests, ~14MB downloads. curl -L. No new installs, no AI upscaling, no paid routes, no secrets. Temp files deleted after commit.
- **Git status / user changes preserved:** AGENTS.md left modified-uncommitted (owner's); only agent-authored docs/code staged; media never committed; no destructive commands, no force-push.
- **Rollback:** `git revert` of the F5 commit on branch `factory/business-documentary-pilot`.
- **Next smallest step:** owner reviews F5 QC result, OWNER_ACTIONS.md, FOOTAGE_QUALITY.md (email + AI-upscale decision); then proceed to next milestone per plan.

