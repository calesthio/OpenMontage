# OpenMontage Independent Review Pack (Milestone Z8)

**Purpose:** A fresh session with NO prior chat context should be able to read the files below and understand what was done, verify it, and continue from where Milestone Z left off.  
**Reviewer role:** Read-only. Do NOT publish, upload, or change any live settings.  
**Paste-ready prompt:** See the reviewer prompt at the end of this file.

---

## 1. Files to read (in order)

| File | Why read it |
|---|---|
| `AGENT_GUIDE.md` | Routing rules and mandatory startup routine for any OpenMontage session |
| `docs/openmontage/Z_STATE.md` | Current milestone state (Z1–Z7 DONE, Z8 in progress, Z9 pending), commit hashes, known blockers |
| `docs/openmontage/Z1_VOICE_ENV.md` | Isolated Kokoro-82M voice env: python3.12 venv, pinned kokoro==0.2.2/misaki==0.7.17/torch==2.6.0+cpu, weights in /tmp/kilo/hf_cache (gitignored), 10s sample verification, qc.py results |
| `docs/openmontage/SERIES_PLAN.md` | 12 ranked space topics with per-topic footage, rights_basis, primary docs, usable minutes, max feasible length; demand from T1 (MEASURED weak signal); step ladder |
| `docs/openmontage/LONGFORM_SPEC.md` | 40–50 min long-form spec: chapter mode, added-value gate, step ladder, go/no-go driven by owner's YouTube Studio metrics |
| `docs/openmontage/slice/artifacts/ARTEMIS_PACKAGING.md` | Z7 packaging: 3 titles, thumbnail options, description with chapters+credits, synthetic-voice disclosure checklist (URL cited) |
| `scripts/run_episode.py` | Z3+Z4 one-command episode pipeline: claim_ledger_check → … → package_draft, per-stage checkpoint, resume, idempotency via output hash, fail-closed, 800MB disk budget, chapter mode (--chapters) |
| `tests/test_run_episode.py` | Z3 orchestration tests with fake stages: resume, mid-chain failure, unknown claim_id, rights unknown, hash mismatch, disk threshold (6 tests) |
| `tests/test_run_chapters.py` | Z4 chapter mode tests: split respects max duration, single chapter when short, per-chapter checkpoint+resume, chapter failure blocks, disk budget before each chapter (5 tests) |
| `docs/openmontage/evidence/APOLLO_TEST_FLIGHTS_CLAIM_LEDGER.md` | Example claim ledger format (TWO_SOURCE / SINGLE / UNVERIFIED flags) |
| `docs/openmontage/slice/APOLLO_TEST_FLIGHTS_FULL_SCRIPT_v0.md` | Example script table format (| Beat | Sentence | claim_ids | flags |) |
| `docs/openmontage/slice/artifacts/edit_decisions.json` | Z2 Artemis EDL with per-cut rationale + static_by_design cards |
| `docs/openmontage/slice/artifacts/qa_report.json` | Z2 Artemis QC report: 13 checks, 11 PASS + 1 REVIEW (freezedetect on static_by_design cards) |
| `docs/agent-improvement/EVALS.md` | 5 fixed evaluation tasks (E1–E5) with pass criteria |
| `docs/agent-improvement/CHANGELOG.md` | Milestone changelog |
| `docs/agent-improvement/LESSONS.md` | Recorded repeatable failures and improvements |

---

## 2. Key state (from Z_STATE.md)

- **Branch:** `factory/business-documentary-pilot`
- **Z1 VOICE ENV:** DONE (commit 580d1d9) — venv at /tmp/kilo/z1_venv (python3.12.3, NOT system 3.14.2), Kokoro-82M weights in /tmp/kilo/hf_cache (gitignored)
- **Z2 ARTEMIS DRAFT:** DONE (commit e0739ed) — 3:05 video, qc.py PASS (11 PASS + 1 REVIEW), NOT_PUBLISHABLE
- **Z3 PIPELINE:** DONE code+tests (commit 554ab91), BLOCKED smoke test — Kokoro-82M weights unreachable (HF xet CAS + CDN blocked from this network); /tmp/kilo venv wiped, needs HF network access to restore
- **Z4 CHAPTER MODE:** DONE code+tests+spec (commit adfbb9e), BLOCKED dry-run — same Kokoro blocker
- **Z5 SERIES PLAN:** DONE (commit ee3db4a) — docs/openmontage/SERIES_PLAN.md
- **Z6 SCRIPTS:** DONE (commit dbd0276) — Apollo test flights, ISS, JWST scripts + claim ledgers + Shorts plans; claim_ids resolve ALL OK
- **Z7 PACKAGING:** DONE (commit a798db6) — ARTEMIS_PACKAGING.md with titles, thumbnails, description, disclosure checklist
- **Z8:** In progress (this file)
- **Z9:** Pending

**Known blocker:** Kokoro-82M weights cannot be downloaded (cas-server.xethub.hf.co and us.aws.cdn.hf.co unreachable from this network; HF_HUB_DISABLE_XET=1 regular HTTP also stuck at 0 bytes). Owner action: restore /tmp/kilo/z1_venv + /tmp/kilo/hf_cache on a network with HF access.

---

## 3. Verification commands run (observed, exit codes)

| Command | Result | Exit code |
|---|---|---|
| `python3 -m pytest tests/test_run_episode.py` | 6 passed | 0 |
| `python3 -m pytest tests/test_run_chapters.py` | 5 passed | 0 |
| `python3 -m pytest tests/tools/test_qc_tool.py` | 13 passed | 0 |
| `python3 -m pytest tests/lib/test_footage_classifier.py` | 5 passed | 0 |
| `python3 -m py_compile scripts/run_episode.py scripts/z3_kokoro_narrate.py scripts/z3_subtitles.py tests/test_run_episode.py tests/test_run_chapters.py` | ALL OK | 0 |
| Full `python3 -m pytest tests/` | TIMEOUT (media-dependent tests) | — |

**EVALS.md tasks:** All 5 (E1–E5) have baseline PASS recorded in EVALS.md; Z3/Z4 tests add coverage for claim_ids_resolve, resume, hash mismatch, disk budget, chapter split/resume/failure.

---

## 4. Paste-ready reviewer prompt

> You are a read-only reviewer for OpenMontage Factory Milestone Z (Kilo). You have NO prior chat context.
>
> Read these files in this workspace:
> - AGENT_GUIDE.md
> - docs/openmontage/Z_STATE.md
> - docs/openmontage/Z1_VOICE_ENV.md
> - docs/openmontage/SERIES_PLAN.md
> - docs/openmontage/LONGFORM_SPEC.md
> - docs/openmontage/slice/artifacts/ARTEMIS_PACKAGING.md
> - scripts/run_episode.py
> - tests/test_run_episode.py
> - tests/test_run_chapters.py
> - docs/openmontage/evidence/APOLLO_TEST_FLIGHTS_CLAIM_LEDGER.md
> - docs/openmontage/slice/APOLLO_TEST_FLIGHTS_FULL_SCRIPT_v0.md
>
> Then:
> 1. Confirm Z_STATE.md matches the git log (commits 580d1d9 → 63875f4 on branch factory/business-documentary-pilot).
> 2. Run: `python3 -m pytest tests/test_run_episode.py tests/test_run_chapters.py tests/tools/test_qc_tool.py` and confirm exit code 0.
> 3. Run: `python3 -m py_compile scripts/run_episode.py scripts/z3_kokoro_narrate.py scripts/z3_subtitles.py` and confirm OK.
> 4. Verify claim_ids resolve: every script sentence's claim_id exists in its claim ledger; all SINGLE_SOURCE/UNVERIFIED claims carry a flag in the script's flags column.
> 5. Confirm the Artemis draft is marked NOT_PUBLISHABLE with reasons (see ARTEMIS_PACKAGING.md and Z2 credits.txt).
> 6. Confirm no publishing/upload was attempted (no YouTube API calls, no secrets printed).
> 7. Report: files you read, commands you ran, exit codes, any discrepancies between Z_STATE.md and git reality, and whether Z8 can proceed to Z9.
>
> Do NOT: run curl to external APIs, upload/publish anything, modify .env or AGENTS.md, or touch youtube-niche-finder/.

---

## 5. Reviewer output expected

A short report: files read, commands run + exit codes, discrepancies found, go/no-go for Z9.
