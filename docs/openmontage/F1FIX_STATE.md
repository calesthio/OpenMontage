# F1-fix State — pipeline correctness (Kilo)

**Date:** 2026-10-21
**Branch:** `factory/business-documentary-pilot`
**Scope:** `docs/ tools/ scripts/ tests/ config/ .kilo/` (no media, no secrets, no Kaggle calls; one status call was never needed because no job was touched)
**Inputs read:** `docs/openmontage/FACTORY_GAP_AUDIT.md`, `docs/openmontage/SPEC_CHANGE_REQUESTS.md`, `FACTORY_100_SPEC.md`, `docs/openmontage/*_STATE.md`, `OPENCODE_REQUESTS.md`.
**Approvals applied:** the milestone instruction lists five fixes, matching SCR-05, SCR-06 and SCR-07 plus two F0 findings (red chapter tests, repo-root pytest collection). No owner annotations were present in `SPEC_CHANGE_REQUESTS.md`; this list is the recorded approval. All other SCRs (01-04, 08-10) were **not** applied. `FACTORY_100_SPEC.md` was not edited.

**Completed work not redone:** F0 audit, S7 harness, existing qc/claims/EDL stages were read, not rebuilt. Kilo's in-flight S5/S7 files (`docs/openmontage/S5_STATE.md`, `scripts/s5_push_bakeoff.py`, `tests/test_s5_runner.py`, `tests/test_s5_push_bakeoff.py`, `tools/kaggle_bridge/s5_bakeoff_run.py`) were left uncommitted and untouched.

---

## 1. QC thresholds from config (SCR-05) — DONE

**RED (before fix)**
```
pytest tests/tools/test_qc_tool.py -q -k "thresholds or config ..." 
FAILED test_default_thresholds_come_from_repo_config        (no thresholds_source)
FAILED test_missing_thresholds_config_fails_closed          (success=True)
FAILED test_malformed_thresholds_config_fails_closed        (success=True)
4 failed, 5 passed
```
Also: `config/qc_thresholds.json` was **not valid JSON** (`# comment` lines;
`json.load` → JSONDecodeError), and `qc.py` only read a config when
`config_path` was passed, so the pipeline always used `DEFAULT_THRESHOLDS`.

**Fix**
- `tools/qa/qc.py`: `DEFAULT_CONFIG_PATH = <repo>/config/qc_thresholds.json`;
  `load_thresholds()` returns `(thresholds, source, error)`; missing file,
  unreadable/JSON-invalid file, non-object, or non-numeric known key ⇒
  `ToolResult(success=False)`, one-entry `thresholds_config` **BLOCKED** report
  written to `output_path`, verdict `BLOCKED`; success data reports
  `thresholds_source`.
- `scripts/run_episode.py` `cmd_qc`: passes `config_path` explicitly.
- `config/qc_thresholds.json`: strict JSON, values unchanged (−14 LUFS, −1.5
  dBTP, 2.0 s, 0.05, 0.10, 1.0 s, 0.5 s). Comments moved to `QA_SPEC.md`.

**GREEN**
```
pytest tests/tools/test_qc_tool.py -q -k "thresholds or config ..." → 9 passed
pytest tests/tools/test_qc_tool.py -q                               → 22 passed, exit 0
```
Verdict-flip test: same 1080p clip, `lufs_target=-30` config ⇒ `ebur128 FAILED`,
verdict `FAILED`; repo config ⇒ `ebur128 PASS`, verdict not FAILED.

## 2. claim_ids_resolve inspects every id (SCR-06) — DONE

**RED (before fix)**
```
test_single_source_second_id_is_still_flagged
E  assert 'PASS' == 'FAILED'   ('SINGLE-01, TWO-01', no flags)
4 failed, 5 passed
```
Cause: `for part in parts: source_type = ledger[part]` left only the **last**
id's source type.

**Fix:** a line is SINGLE_SOURCE if **any** cited id resolves to a SINGLE row
(`single_ids` list), and the evidence names those ids. Resolution of every id
(including an unknown id in the middle) is unchanged and now covered.

**GREEN:** 4 new mixed-ID tests pass; `claim_ids_resolve` PASS test with flags
still passes; real Artemis/Apollo ledgers unaffected (qc file 22/22).

## 3. Episode-generic EDL (SCR-07) — DONE

**RED (before fix)**
```
pytest tests/test_edl_generic.py -q → 5 failed in 0.37s
```
The old `cmd_edl` wrote a fixed 12-cut Artemis plan (`total = 185.43`,
`ARTEMIS-*` claim ids) into `docs/openmontage/slice/<topic>/`, ignoring
`state["script_path"]`/`state["edl_path"]`.

**Fix:** `cmd_edl` now parses the episode script (`B<n>` / `B<n>-<m>` rows),
groups beats, takes the measured narration duration (explicit state value →
explicit manifest → this episode's wav; the shared artifacts manifest is NOT
used implicitly), and allocates title / per-beat / credits graphics cards with
contiguous timing, per-cut rationale, beat label and `claim_ids`. All cards are
`static_by_design`; no topic name, claim id, asset id or duration literal.
BLOCKED with a reason when the script is missing/unparseable or no measured
narration duration exists.

**GREEN**
```
pytest tests/test_edl_generic.py -q → 5 passed
```
Two fake episodes: 60 s / 3 beats ⇒ 5 cuts; 20 s / 1 beat ⇒ 3 cuts; both
contiguous to `total_duration_s`; no `ARTEMIS`/`185.43` in either file.
Real scripts still parse: Artemis 20 rows/6 beats, Apollo 9 9/9, ISS 12/4,
CID 40/6 (read-only check).

**Trade-off:** the generic EDL emits graphics cards only. Footage inserts need
an episode asset inventory / render_manifest mapping, which is F2 scope; the
previous Artemis insert plan is gone by design (it was the hardcode being
removed).

## 4. Red chapter-mode tests — FIXED

**Diagnosis (evidence)**
- HEAD had `2 failed, 3 passed` in `tests/test_run_chapters.py`.
- `_write_chapter_script()` writes rows `| B<chapter>-<sentence> | ... |`;
  both readers required `cells[0][1:].isdigit()`, so `B1-1` parsed to **zero
  sentences**. This is a product bug: a real `--chapters` run would write empty
  chapter scripts, not just a bad test.
- Test docstring also claimed "expect 4 chapters" while asserting 7 (20×20 s at
  60 s/chapter = 7).

**Fix:** one shared `_parse_script_rows()` (regex `^B(\d+)(?:-\d+)?$`) used by
`cmd_script_validation`, `split_script_into_chapters` and `cmd_edl`; docstring
corrected to 7. No test expectation was weakened.

**GREEN:** `pytest tests/test_run_chapters.py -q` → **5 passed** (was 2 failed).

## 5. pytest collection excludes the nested project — DONE

**RED (before fix)**
```
pytest --collect-only -q  → ModuleNotFoundError: No module named 'psycopg2'
(youtube-niche-finder/backend/infrastructure/postgres/connection.py)
```

**Fix:** root `pytest.ini` with `norecursedirs` (pytest defaults kept) adding
`youtube-niche-finder`, `remotion-composer`, `projects`. Deliberately did NOT
exclude `backlot`: it matched `tests/backlot` and silently dropped 23 tests
(caught by comparing counts).

**GREEN**
```
pytest --collect-only -q  → 2491 tests collected, exit 0 (269 s)
pytest tests --collect-only -q → same set
```

---

## Commands and exit codes (observed)

| Command | Result |
|---|---|
| `pytest tests/tools/test_qc_tool.py -k "thresholds or config or single_source or unknown_id_in_the_middle or all_ids"` | RED 4 failed / 5 passed → GREEN **9 passed** |
| `pytest tests/tools/test_qc_tool.py -q` | **22 passed**, exit 0 (388.90 s) |
| `pytest tests/test_edl_generic.py -q` | RED 5 failed → GREEN **5 passed** |
| `pytest tests/test_run_chapters.py -q` | RED 2 failed/3 passed → GREEN **5 passed** |
| `pytest tests/test_run_episode.py tests/test_run_chapters.py tests/test_edl_generic.py tests/tools/test_finish_audio.py -q` | **24 passed**, exit 0 |
| `pytest --collect-only -q` | RED (psycopg2) → GREEN **2491 collected**, exit 0 |
| `python scripts/ci_fast_suite.py` | see §CI result below |
| `python -m py_compile scripts/run_episode.py tools/qa/qc.py` | exit 0 |

## CI fast suite

`python scripts/ci_fast_suite.py` → **10/10 test files passed, `"ok": true`,
exit 0**, 410.85 s wall, disk free 2580 MB after (floor 800 MB). Includes
`test_qc_tool.py`, `test_finish_audio.py`, `test_illustration_*`,
`test_museum_adapters.py`, `test_motion_variety.py`, `test_packaging.py`,
`test_analytics_import.py`, `test_footage_classifier.py`,
`test_artifact_id_resolution.py`.

## Limits / not done

- Full 2491-test suite not executed; only the impacted files + CI fast subset.
- No Kaggle job submitted, polled or cancelled this milestone (nothing needed it).
- Packaging wiring (SCR-08), zero-cost gate wiring (SCR-04) and the other
  unapproved SCRs remain open.
- `cmd_edl` is generic but graphics-only until F2 supplies an asset inventory.
