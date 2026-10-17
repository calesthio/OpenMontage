# Global Check — OpenMontage MASTER RUN P7

**Date:** 2026-10-17
**HEAD:** 501585b (factory/business-documentary-pilot)
**Status:** All phases complete except P3 (BLOCKED - GPU/kaggle quota). P7 is the final gate review.

---

## (a) Phase table — status and commit hashes

| Phase | Status | Commit hash | Evidence |
|---|---|---|---|
| P1 Voice license evidence | DONE | 94c789d | docs/openmontage/VOICE_BAKEOFF_LICENSES.md |
| P2 Evidence ledger + script | DONE | 9bf1605 | docs/openmontage/evidence/CID_CLAIM_LEDGER.md, docs/openmontage/slice/CID_SLICE_SCRIPT_v0.md, docs/openmontage/slice/CID_SLICE_CLAIM_IDS.json |
| P3 Kaggle voice bake-off | BLOCKED | — | Kaggle GPU job QUEUED 15+ min, never reached RUNNING. Owner: verify Kaggle phone number / GPU quota; 1 retry remains. |
| P4 TTS integration | DONE | fafc238 | tools/audio/tts_kaggle.py, config/voice.json, tests/tools/test_tts_kaggle.py (5 pass) |
| P5 Footage source registry | DONE | 501585b | docs/openmontage/footage/SOURCE_REGISTRY.md; 16 adapters verified via auto-discovery |
| P6 Technical slice ~50s | DONE | 501585b | projects/slice_cid_v0/ (gitignored); QC qa_report.json 12/12 PASS |
| P7 Global check | IN_PROGRESS | — | This document |

## (b) Tests run — exact commands and exit codes

| Test command | Tests | Result | Exit code |
|---|---|---|---|
| `python3 -m pytest tests/tools/test_qc_tool.py -q` | 11 | PASS | 0 |
| `python3 -m pytest tests/tools/test_kaggle_bridge.py -q` | 16 | PASS | 0 |
| `python3 -m pytest tests/tools/test_tts_kaggle.py -q` | 5 | PASS | 0 |
| **Combined** | **32** | **PASS** | **0** |

Combined command: `python3 -m pytest tests/tools/test_qc_tool.py tests/tools/test_kaggle_bridge.py tests/tools/test_tts_kaggle.py -q` → `32 passed in 171.89s`

Additional verification:
- `python3 -m py_compile tools/audio/finish_audio.py tools/audio/tts_kaggle.py tools/kaggle_bridge/kaggle_bridge.py tools/qa/qc.py` → OK
- `kaggle kernels list --mine --page-size 5` → exit 0 (auth confirmed, owner=forts845)

## (c) ffprobe + full decode + qa_report summary for the slice

**Slice file:** `projects/slice_cid_v0/final_slice.mp4` (gitignored, not committed)

**ffprobe:**
- Duration: 48.93s
- Size: 13,857,204 bytes
- Video: 1920x1080 @ 30fps, h264
- Audio: aac @ 44100Hz

**qa_report.json — all 12 checks PASS:**

| Check | Status | Measured value | Threshold |
|---|---|---|---|
| ffprobe_streams | PASS | 1920x1080, 30fps, video+audio | w=1920,h=1080,fps=30 |
| full_decode | PASS | no decode errors | exit 0 |
| blackdetect | PASS | 0.0 black ratio | <= 0.05 |
| freezedetect | PASS | 0.0s max freeze | <= 2.0s |
| silencedetect | PASS | 0.0 silence ratio | <= 0.10 |
| ebur128 | PASS | I=-15.2 LUFS, TP=-4.4 dBFS | I=-14±2 LUFS, TP<=-1.5 |
| duration_vs_script | PASS | 0.003s drift | <= 5.0s |
| subtitle_sync | PASS | 0.0s drift | <= 0.5s |
| credits_complete | PASS | all required fields | title, director, production |
| claim_ids | PASS | 9/9 sentences | 100% with claim_id |
| rights_basis | PASS | 4/4 clips | 100% explicit_license/source_policy_us_gov |
| added_value | PASS | 0 unannotated > 20s | 0 unannotated > 20s |

**Overall verdict: PASS** (all checks green, no NOT_RUN, no BLOCKED, no FAILED)

**Note:** Output tagged NOT_PUBLISHABLE — see open gates in section (e).

## (d) Repo hygiene

- `git status --short`: clean except for user-modified `AGENTS.md` (preserved, not committed) and `docs/openmontage/MASTER_RUN_STATE.md` (committed as part of this milestone)
- No large tracked files (>1MB): none
- Secret scan (`git grep` for API key patterns): no secrets introduced by this work. Pre-existing matches in skill docs are false positives (e.g., "sk-" within words like "skill").
- No media files committed: all slice outputs, thumbnails, and contact sheets are in `projects/` (gitignored)
- `kaggle` CLI installed (1.3 MB), `/workspaces` disk: 3.4 GB free (>800 MB threshold)

## (e) Open gates — every open gate

| Gate | Status | Detail |
|---|---|---|
| Voice license (Piper lessac) | BLOCKED | MODEL_CARD has no license field; manifest asserts CC-BY-4.0 but no license text in repo. Cannot publish with Piper voice. |
| Voice license (Kokoro-82M) | PROVISIONAL | Weights Apache-2.0 (clear), but training-data caveats: CC BY items (Koniwa `tnc` <1h CC BY 3.0; SIWIS <11h CC BY 4.0), synthetic-data origin UNKNOWN. Owner sign-off required. |
| Voice license (Chatterbox Turbo) | CLEARED | MIT code + MIT weights, but Perth watermark embedded in output; reference audio optional (not used). |
| Rights flags (identifiable_persons / logo_visible) | UNREVIEWED | All 4 CID clips flagged UNKNOWN in REVIEW_QUEUE.md; owner frame/pixel review required before publish. |
| Third-party credit | CLEAR | All 4 CID clips have no third-party credit in metadata. |
| Single-source claims | BLOCKED | CID-06, CID-10, CID-12, CID-14, CID-15 are TM-only (SINGLE_SOURCE). CID-13 is FS-only SINGLE_SOURCE, LOAD-BEARING, needs second source. S8 (script line) blocked until CID-13 has second source. |
| NASA insignia on vehicles | OWNER DECISION | CID footage may show NASA insignia; per NASA Media Usage Guidelines, insignia use is protected by law and incidental appearance does not convey usage rights. Owner must decide on clearance. |
| Guardian / AdSense / monetization | NOT ASSESSED | No monetization eligibility review performed. |
| Content ID / music policy | N/A | No music used in this slice (MUSIC_POLICY.md: no music unless license evidence exists). |

## (f) Owner actions

See `docs/openmontage/OWNER_ACTIONS.md` for numbered, minimal owner steps.

## (g) Independent read-only review

The owner (or a QA reviewer) can independently verify this milestone by running:

```
/review worktree
```

or, for the QA-specific scope:

```
@qa-reviewer Review docs/openmontage/GLOBAL_CHECK_2026-10-17.md and projects/slice_cid_v0/qa_report.json, read-only. Report PASS/REVIEW/BLOCKED with evidence per check.
```

**Key measured numbers for the owner:**
- Slice: 48.93s, 1920x1080, 30fps, h264/aac, 13.9 MB
- Narration: 46.05s, Kokoro-82M (af_heart), CPU RTF 1.58–1.75
- QC: 12/12 checks PASS
- Clips: 4, all source_policy_us_gov, no third-party credit
- Primary docs: 6 externally verified (NASA Facts FS-2009-02-003-CID + NASA TM-4084 + 4 NTRS citations)
- Claims: 16 in ledger, 8 in script, 9/9 with claim_id
