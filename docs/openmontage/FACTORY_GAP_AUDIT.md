# FACTORY GAP AUDIT — F0 (read-only reality audit)

**Date:** 2026-10-21
**Auditor:** OpenCode (research lane), inline — *not independent*
**Branch / HEAD:** `factory/business-documentary-pilot` / `3871444` (ahead 32, behind 1 of `origin/factory/business-documentary-pilot`)
**Source of truth:** the repository at the commit above plus the working tree as found. State files are treated as *claims*, not evidence.
**Code changes:** none. This milestone produced only this file and `SPEC_CHANGE_REQUESTS.md`.

> Scope note: `FACTORY_100_SPEC.md` exists **only on `origin`** (commit `696eb6f`, repo root), not in this working tree. It was read with `git show origin/factory/business-documentary-pilot:FACTORY_100_SPEC.md` (138 lines). Local `HEAD` does not contain it (`git cat-file -e HEAD:FACTORY_100_SPEC.md` → fatal). See SCR-01.

---

## 1. Verdict summary

| Layer | Verdict | One-line basis |
|---|---|---|
| L1 Niche and topic intelligence | **FAIL** | 4 niche profiles exist, but no demand-measurement code and no tested viability-gate function. |
| L2 Evidence and scripting | **FAIL** | 7 claim ledgers + `claim_ids_resolve` work, but no footage-aware storyboard and a multi-ID resolution defect. |
| L3 Visual sources and rights | **FAIL** | NASA/IA/LoC/NARA/Wikimedia + 4 museum adapters exist; DVIDS missing, fixtures-only, NC/ND test absent. |
| L4 AI illustration engine | **FAIL** | Bridge + prompt builder + illustration QC exist; S7 bake-off unfinished, no blind pack, no chosen model. |
| L5 Voice and audio | **FAIL** | Kokoro + license gate + finish_audio verified; owner voice sign-off missing, longest unattended narration 428.6 s (< 10 min). |
| L6 Editing and render | **FAIL** | 10-stage `run_episode.py` works, but the EDL is Artemis-hardcoded and 2 chapter-mode tests are red at HEAD. |
| L7 Quality gates | **FAIL** | 13 checks + fail-closed statuses; speculative gate and motion lint are not wired into `qc.py`; config thresholds unused by default. |
| L8 Packaging | **FAIL** | `tools/packaging` exists and is tested, but nothing imports it; the pipeline's package stage only copies files. |
| L9 Owner review and independent verification | **NOT_CHECKED** | Review pack and blind-sheet tooling exist; no independent reviewer run and no owner blind results in the repo. |
| L10 Operations and learning loop | **NOT_CHECKED** | State/CI/rebuild/lessons exist; analytics loop never ran, zero-cost gate is not wired into the pipeline. |

**Aggregate:** 0 PASS, 7 FAIL, 2 NOT_CHECKED (L9 requires a human/independent actor; L10's analytics half requires a published video).

---

## 2. Evidence base (what was actually executed)

All commands below were run in `/workspaces/OpenMontage` on 2026-10-21. No files were modified except the two docs named above.

| Command | Result |
|---|---|
| `git rev-parse --short HEAD`, `git status -sb` | HEAD `3871444`; ahead 32 / behind 1; dirty files are Kilo's (`scripts/s5_push_bakeoff.py`, `tests/test_s5_*`, `docs/openmontage/S5_STATE.md`), untouched by this audit |
| `df -m --output=avail /workspaces` | 2639 MB free (stop floor 800 MB → not triggered) |
| `python scripts/ci_fast_suite.py` | exit 0; 10/10 test files pass; 191.85 s; 2628 MB free after |
| `pytest tests/tools tests/lib tests/factory tests/prompting tests/illustration tests/qa -q` | **1030 passed, 29 skipped, 3 xfailed, 1 subtest** in 877.80 s |
| `pytest tests/test_run_episode.py tests/test_run_chapters.py tests/test_s7_*.py -q` | **40 passed, 2 failed** (both `tests/test_run_chapters.py`) |
| `pytest --collect-only -q` (repo root) | **fails**: nested untracked `youtube-niche-finder/backend/...` imports `psycopg2` (not installed). Full-repo collection = NOT_CHECKED; `pytest tests --collect-only -q` collects 2476 tests |
| `git diff --stat scripts/run_episode.py tests/test_run_chapters.py` | empty → the 2 failures exist at HEAD, not caused by local edits |

Test-scope limitation: `tests/` holds 2476 collected tests; only the 1072 factory-relevant tests above were executed. The rest (`tests/contracts`, `tests/pipelines`, provider suites) are **NOT_CHECKED** for this audit.

---

## 3. Per-layer findings

### L1 — Niche and topic intelligence — **FAIL**

**Met**
- Niche profiles as YAML with `allowed_sources`, `excluded_content`, `required_primary_doc_types`, `viability_gate`, `added_value_gate`, episode templates:
  `docs/openmontage/niches/space_iss.yaml`, `art_history.yaml`, `speculative_science.yaml`, `niches/speculative_evolution/speculative_evolution.yaml`. YAML validity covered by the 1030-test run.
- Demand material exists as documents only: `docs/openmontage/audit/demand/` (A/B summaries, fact packs), `MASTER_RUN_STATE.md` records quota-exhausted as NOT_MEASURED.

**Unmet**
- No `scripts/measure_niche.py` and no uploads-playlist/outlier/replication implementation anywhere: `grep -rln "uploads playlist|search.list|outlier" --include="*.py" scripts tools` returns only `scripts/s5_checks.py` and `scripts/s7_checks.py` (image QC false positives), and `ls scripts | grep -i niche` returns nothing.
- The viability gate is prose in YAML; there is no importable, tested `viability_gate()` function (`grep -rn "viability" --include="*.py" tools scripts lib` → no matches).
- No outlier definition (`views / median last-20 uploads`) or replication rule in code.

**Verdict basis:** the spec's done-when ("measure_niche.py + reports reproducible from cached data; viability gate is a tested function") is not met.

### L2 — Evidence and scripting — **FAIL**

**Met**
- Ledgers with per-claim IDs: `docs/openmontage/evidence/{CID(55 ids),APOLLO9(45),ARTEMIS(16),S1_SPECULATIVE(13),ISS(12),JWST(12),APOLLO_TEST_FLIGHTS(14)}_CLAIM_LEDGER.md`; S1 ledger states TWO/SINGLE/SPECULATION flags and retrieval dates.
- Scripts with per-sentence claim_ids: 7 `docs/openmontage/slice/*_FULL_SCRIPT_v0.md`.
- `claim_ids` + `claim_ids_resolve` implemented in `tools/qa/qc.py` (checks at lines ~700-855) and exercised by tests; `docs/agent-improvement/EVALS.md` E4/E5 = PASS.
- `claim_ids_resolve` does fail on unknown IDs (tests + EVALS evidence).

**Unmet / defect**
- No footage-aware scripting: nothing in `tools/`, `scripts/`, `lib/` consults an asset inventory before narration (matches for "storyboard" are unrelated backlot scripts).
- **Defect:** `tools/qa/qc.py:816-818` — `for part in parts: source_type = ledger[part]` leaves only the **last** claim_ID's status; `is_single` then tests that one value. A sentence citing `SINGLE_SOURCE, TWO_SOURCES` (in that order) passes unflagged. No regression test covers mixed multi-ID rows.
- Script parsing is format-fragile: `cmd_script_validation` and `split_script_into_chapters` only accept rows whose first cell is `B<digits>` (`run_episode.py:168`, `:678`); the chapter test helper writes `B1-1` and therefore parses zero sentences.

### L3 — Visual sources and rights — **FAIL**

**Met**
- `docs/openmontage/footage/SOURCE_REGISTRY.md` with per-source rights page, `rights_basis`, adapter present/missing.
- Keyless adapters: `tools/video/stock_sources/{nasa,archive_org,loc,nara,wikimedia,...}.py`; museum adapters `tools/museum/adapters.py` (Met, Smithsonian, Rijksmuseum, NGA, Wikimedia) with injectable `http_get` (+ `tests/tools/test_museum_adapters.py`, `test_stock_source_adapters.py`).
- Asset record with sha256/credit/URL/rights_basis: `tools/museum/asset_record.py`.
- Rights classifier: `lib/footage_classifier.py`; third-party credit ⇒ `rights_basis=unknown, usable=False`; 5 tests in `tests/lib/test_footage_classifier.py`.
- Rights model doc: `docs/openmontage/RIGHTS_MODEL.md`.

**Unmet**
- DVIDS adapter absent (spec L3 lists it); `tools/adapters/` from spec §4 does not exist (code lives in `tools/video/stock_sources/` and `tools/museum/`).
- NC/ND rejection is not an explicit classifier regression (5 tests cover third-party, missing, unknown, valid); spec's "NC/ND ⇒ REJECT" is unproven in code.
- Adapters were never exercised on a real episode in this audit; M_STATE records fixtures only.

### L4 — AI illustration engine — **FAIL**

**Met**
- Kaggle bridge with submit/poll (backoff + total timeout), fetch, manifest `job_id`/`sha256`/bytes verification, token scrubbing, fail-closed statuses: `tools/kaggle_bridge/kaggle_bridge.py` (+ `tests/test_s7_runner.py` etc. in the 1030/40-pass runs).
- Prompt builder per model: `tools/prompting/builder.py`, `SOURCES.md`; 28 tests pass (`tests/prompting` + `tests/test_score_rubric.py`).
- Illustration batch + label + manifest: `tools/illustration/illustration_batch.py`; image QC: `illustration_qc.py` (Laplacian, pHash, aspect/text-like).
- Style system: `docs/openmontage/niches/speculative_evolution/STYLE_BIBLE.md`, `image_gen/ILLUSTRATION_STYLE_BIBLE.md`, 6 creature YAMLs.
- Verified model run: S7 SDXL Base 10/10, sha256 verified, 41.4 s/img (`docs/openmontage/S7_STATE.md`).

**Unmet**
- S7 not finished: `s7-klein-1` RUNNING, Z-Image PENDING (`S7_STATE.md` phases S7-4/-5); blind pack and owner scoring PENDING; `BAKEOFF_S7.md` is an untracked WIP skeleton with "FILLED" placeholders; no model is chosen.
- "One command produces N labelled illustrations for an episode" is not demonstrated end-to-end (modules exist; no episode-scale run).
- S5 produced 0 usable images (documented in `S5_STATE.md`/`BAKEOFF_S7.md`), so only SDXL has a verified output set.

### L5 — Voice and audio — **FAIL**

**Met**
- Kokoro-82M via kokoro-onnx works: `Z_STATE.md` Z1 (15.46 s sample), Apollo 9 narration 428.6 s.
- License gate in the TTS tool: `tools/audio/tts_kaggle.py` refuses non-permissive engines, `en_US-lessac-medium` blocked; EVALS E3 PASS.
- `finish_audio` two-pass loudnorm + limiter: `tools/audio/finish_audio.py`, 5 tests; loudness verified on final MP4 (`qa_report.json` entries I=-15.1…-15.3 LUFS).
- Subtitles from word timestamps: `scripts/z3_subtitles.py`, `subtitle_sync` QC check, `word-timestamps.json`.

**Unmet**
- Owner voice acceptance not recorded (`S1_STATE.md` S1-6 PENDING; Z_STATE owner decisions).
- No 10-minute unattended synthesis: longest verified narration 428.6 s (~7 min); the 10-12 min pilot script exists (`S1_STATE.md` S1-4) but was never narrated.
- `scripts/run_episode.py:31` hardcodes `VENV_PY=/tmp/kilo/z1_venv/bin/python`; the narration and subtitle stages BLOCK if that non-repo env is absent (portability risk).
- Music is correctly absent, but no music license-evidence path has been exercised.

### L6 — Editing and render — **FAIL**

**Met**
- `scripts/run_episode.py` with 10 stages, per-stage checkpoint/resume/idempotency, 800 MB disk guard, wall-time/disk logging (`STAGE_REGISTRY`, `run_pipeline`).
- Chapter mode code + `docs/openmontage/LONGFORM_SPEC.md`.
- Motion variety: `tools/motion/motion_variety.py` (pan/zoom/easing, consecutive-move lint), 8 tests; used by `tools/illustration/s1_edl.py`.
- Real drafts: CID 56 s, Artemis 185.43 s, ISS 195.6 s, Apollo 9 428.6 s (media in gitignored `projects/slice_*`, artifacts committed under `docs/openmontage/slice/artifacts/`).

**Unmet**
- **`cmd_edl` is Artemis-hardcoded**: `run_episode.py:279-340` fixes `total = 185.43`, ARTEMIS claim IDs and rationale strings. A new episode cannot produce its own EDL; the spec's "EDL with per-cut rationale per episode" is not generic.
- **2 red tests at HEAD**: `tests/test_run_chapters.py::test_split_script_into_chapters_respects_max_duration` and `..._single_chapter_when_short` fail because the parser rejects `B1-1` rows (`run_episode.py:678-680`) — chapter mode was never end-to-end (Z4 documented the dry-run gap).
- Chapter-mode render/concat has never produced a verified output (`Z_STATE.md` Z4 "dry-run NOT completed").

### L7 — Quality gates — **FAIL**

**Met**
- `tools/qa/qc.py` implements ffprobe, full decode, blackdetect, freezedetect (with `static_by_design` exemption), silencedetect, ebur128 + true peak, duration vs script, subtitle sync, credits, `claim_ids`, `claim_ids_resolve`, `rights_basis`, added-value, plus `ai_illustration_label`.
- Fail-closed status set `PASS|REVIEW|BLOCKED|FAILED|NOT_RUN` (`qc.py:46`); missing inputs ⇒ NOT_RUN, unrunnable ⇒ BLOCKED.
- 13 QC tests pass; EVALS E1-E5 PASS; real reports exist (`docs/openmontage/slice/artifacts/qa_report.json`, `qa_report_iss.json`).

**Unmet**
- Speculative-label gate and motion-variety lint are **not called by `qc.py`**: they live in `tools/illustration/s1_speculative_gate.py` and `tools/motion/motion_variety.py`; `grep` finds no qc.py reference.
- Thresholds: `config/qc_thresholds.json` exists, but `cmd_qc` does not pass `config_path` (`run_episode.py:519-545`), so `DEFAULT_THRESHOLDS` in `qc.py:32` are used. The config file is effectively decorative in the pipeline.
- `ai_illustration_label` is implemented but absent from the tool's declared `capabilities` list (discoverability drift).

### L8 — Packaging — **FAIL**

**Met**
- `tools/packaging/packaging.py`: `generate_thumbnail`, `build_metadata_block`, `disclosure_checklist` citing official YouTube help URLs; 3 tests pass.
- Drafts: `docs/openmontage/package/{CID_PACKAGE_DRAFT.md,ARTEMIS_SHORTS_PLAN.md,THUMBNAIL_NOTES.md}`, `slice/artifacts/ARTEMIS_PACKAGING.md`.

**Unmet**
- The module is imported **nowhere** (`grep -rln "generate_thumbnail|disclosure_checklist" --include="*.py" tools scripts` → only its own file).
- `run_episode.py:552-568` `cmd_package_draft` merely copies artifacts and writes `package_manifest.json`; credits/titles are not generated from `rights_records.json`, contradicting the done-when ("zero manual copy-paste of credits").

### L9 — Owner review and independent verification — **NOT_CHECKED**

**Exists**
- `scripts/review_pack.py` (`bundle_review_pack`, `run_evals`) + `tests/tools/test_review_pack.py`; `docs/openmontage/REVIEW_PACK.md` with reviewer prompt and verify commands.
- Blind-sheet + tally tooling: `scripts/s7_blind_pack.py`, `scripts/s7_tally.py`, `scripts/s7_agent_assessment.py` (tests pass); owner-vs-agent disagreement and INSUFFICIENT handling implemented.

**Not verifiable from the repo**
- No evidence any independent read-only reviewer session ran (no dated reviewer output file).
- No owner blind-scoring results committed (`projects/s7_blind/` is gitignored and absent), so the "blind sheet → winner" path is unproven.
- Per-episode owner checklist (`OWNER_ACTIONS.md`) is a to-do list, not a completed review record.

### L10 — Operations and learning loop — **NOT_CHECKED**

**Met**
- 7 state files (`MASTER_RUN_STATE.md`, `S1/S4/S5/S7/M/Z_STATE.md`) with resume rules; `docs/agent-improvement/{LESSONS,EVALS,CHANGELOG,BACKLOG}.md`.
- CI-style fast suite green (10/10 files, 191.85 s, disk checked before/after).
- Portability: `scripts/rebuild_slice_assets.sh` re-downloads + sha256-verifies, fails closed; manifest `docs/openmontage/assets/CID_SLICE_MANIFEST.json`; 13-14 tests.
- Disk discipline observed: 2639 MB free; 1.7 GB media under gitignored `projects/`.

**Unmet / not verifiable**
- Analytics loop never ran: `tools/analytics/analytics_import.py` + 3 tests exist, but `docs/openmontage/analytics/` does not exist and no Studio CSV was ever imported. The loop's done-when depends on a published video.
- `lib/zero_cost_gate.py` exists (with `tests/factory/test_zero_cost_gate.py`) but is referenced by **no** pipeline/provider code (`grep -rln "zero_cost_gate|ZeroCostGate" --include="*.py"` → tests only), so AGENTS.md's "strict zero-cost is the default" is not enforced at runtime.
- Codespaces usage hygiene is owner-only and cannot be audited here.

---

## 4. Cross-cutting findings (affect several layers)

1. **Spec file is remote-only and at the wrong path.** `FACTORY_100_SPEC.md` is added by `origin` commit `696eb6f` at repo root; spec §4 declares `docs/openmontage/FACTORY_100_SPEC.md`. Local HEAD lacks it. See SCR-01.
2. **Spec §5 status is stale.** It says the 3-model bake-off "failed/blocked", but `S7_STATE.md` records SDXL 10/10 DONE and klein in flight. Spec should point at state files instead of duplicating status. See SCR-02.
3. **Two tests are red at HEAD** (`tests/test_run_chapters.py`, 2 of 5), so chapter mode is not "done" regardless of `Z_STATE.md`.
4. **Full-repo test collection fails** on the untracked nested `youtube-niche-finder/` (`psycopg2`). Factory CI must pin explicit paths (it does) and the nested repo must not be on the collection path.
5. **Several modules are built but unwired**: packaging, speculative gate, motion lint in QC, zero-cost gate. Green unit tests overstate readiness.
6. **Environment coupling**: `run_episode.py` depends on `/tmp/kilo/z1_venv/bin/python` for narration/subtitles; the "clean account rebuild" claim in §7 cannot hold with that default.
7. **Config drift**: `config/qc_thresholds.json` is not loaded by the pipeline; thresholds live in code defaults.

---

## 5. What this audit did NOT verify

- Full test suite (only 1072 factory-relevant tests of 2476 collected under `tests/`; `tests/contracts`, provider suites, `tests/pipelines` not run).
- Any Kaggle/network action (no jobs submitted, no downloads); S7/S5 statuses are taken from state files, not re-polled.
- Media quality (owner-only by rule): no video/still was viewed.
- Rights of actual assets (only the code path/classifier was inspected).
- Real 8-10 minute episode end-to-end (none exists).
- Independent review (L9) and analytics (L10) by definition require actors/events outside this session.

---

## 6. Smallest next step (not performed)

F1 (image engine decision) is the only milestone that can advance without new code: finish `s7-klein-1`/Z-Image, build the blind pack, and have the owner score it. In parallel, the two red chapter tests and the `cmd_edl` hardcode are the cheapest code fixes that move L6, but they are outside a read-only milestone.
