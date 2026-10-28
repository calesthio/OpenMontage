# SPEC CHANGE REQUESTS — FACTORY_100_SPEC.md

**Date:** 2026-10-21 · **Author:** OpenCode (F0 audit) · **Status:** PROPOSED, not applied.
**Rule:** `FACTORY_100_SPEC.md` is not edited by agents; this file is the proposal channel. Owner decides.

Each item: what the spec says, what the repository shows, proposed wording, impact if ignored.

---

## SCR-01 — Put the spec at the path the spec declares (root vs `docs/openmontage/`)

**Spec:** §4 layout lists `docs/openmontage/FACTORY_100_SPEC.md (this file)`.
**Reality:** the file is at repo root and exists only on `origin` (`696eb6f`), not in the local `HEAD` tree (`git cat-file -e HEAD:FACTORY_100_SPEC.md` → fatal; `git show origin/factory/business-documentary-pilot:FACTORY_100_SPEC.md` works).
**Proposal:** pick one canonical location and state it in §9 as the read command. Recommended: keep the root file (already published) and change §4 to `FACTORY_100_SPEC.md (repo root)`.
**If ignored:** every new session that follows §4 looks in an empty path; agents may fork the spec.

## SCR-02 — §5 "Current state" must not duplicate volatile status

**Spec:** §5 lists builds/failures ("G2 image bake-off failed", "Z-Image blocked") as current.
**Reality:** it is already stale — `docs/openmontage/S7_STATE.md` records SDXL 10/10 DONE (41.4 s/img), klein submitted, and `docs/openmontage/image_gen/BAKEOFF_S7.md` exists as WIP. §5 also contradicts F1 in §6 ("finish the bake-off").
**Proposal:** replace §5 with a pointer: "Current status is authoritative only in `docs/openmontage/*_STATE.md`; §5 records durable, already-closed facts (G2 FAILED, S5 zero images) and nothing in flight."
**If ignored:** agents re-litigate closed failures and mis-rank the build order.

## SCR-03 — Correct the §4 layout: `tools/adapters/` does not exist

**Spec:** §4 lists `tools/{kaggle_bridge,qa,audio,illustration,prompting,adapters}/`.
**Reality:** adapters live in `tools/video/stock_sources/` (nasa, archive_org, loc, nara, wikimedia, …) and `tools/museum/` (Met, Smithsonian, Rijksmuseum, NGA, Wikimedia); `tools/adapters/` is absent. DVIDS has no adapter.
**Proposal:** update the layout to the real paths and drop `adapters/`; add "DVIDS: MISSING" to L3 until written.
**If ignored:** audits and new agents report a phantom directory and may duplicate working adapters.

## SCR-04 — Make zero-cost enforcement a stated acceptance criterion, not prose

**Spec:** §1.2 "Budget $0 … unknown price = forbidden"; AGENTS.md: "strict zero-cost mode is the default".
**Reality:** `lib/zero_cost_gate.py` exists and is tested (`tests/factory/test_zero_cost_gate.py`), but no `tools/`/`scripts/` code references it (`grep -rln "zero_cost_gate|ZeroCostGate" --include="*.py"` → tests only). Route selection does not consult it.
**Proposal:** add to L10 (and to §7 "100% done"): "Provider/route resolution calls `lib.zero_cost_gate`; an unpriced or unnamed route returns BLOCKED. A test proves a paid route is refused by the pipeline, not only by the gate unit test."
**If ignored:** a green unit suite can coexist with a pipeline that would happily call a paid provider.

## SCR-05 — L7: state that QC must load `config/qc_thresholds.json` by default

**Spec:** L7 "Threshold changes only by owner decision"; AGENTS.md places thresholds in `config/qc_thresholds.json`.
**Reality:** `tools/qa/qc.py` only loads a config when `config_path` is passed; `scripts/run_episode.py` `cmd_qc` does not pass it, so `DEFAULT_THRESHOLDS` (`qc.py:32`) apply. Editing the config changes nothing in the pipeline.
**Proposal:** add to L7: "The pipeline passes `config/qc_thresholds.json`; a test asserts the config value wins over the code default."
**If ignored:** owner-approved threshold changes silently do nothing.

## SCR-06 — L2: define mixed multi-ID claim rows and require a regression

**Spec:** L2 "unknown id = FAIL", "every SINGLE_SOURCE sentence is listed".
**Reality:** `tools/qa/qc.py:816-818` assigns `source_type` inside `for part in parts`, so only the **last** ID decides `is_single`. A row `"SINGLE_A, TWO_B"` is not flagged. No test covers mixed IDs.
**Proposal:** add one sentence to L2: "A sentence may cite several claim_ids; it is SINGLE_SOURCE if **any** cited claim is SINGLE_SOURCE, and must be flagged accordingly. A regression test covers mixed ordering."
**If ignored:** single-source sentences can pass publication gating by ordering their IDs.

## SCR-07 — L6: forbid a hardcoded EDL in `run_episode.py`

**Spec:** L6 "EDL (edit_decisions.json): every cut has a written rationale…"; F2 requires an end-to-end build for a new topic.
**Reality:** `cmd_edl` (`run_episode.py:279-340`) is Artemis-specific: `total = 185.43`, ARTEMIS claim IDs and rationale strings. Any new episode inherits the Artemis cut plan.
**Proposal:** add to L6 done-when: "`cmd_edl` derives cuts, durations and rationale from the episode's script/asset inventory; no topic name, claim ID or duration literal appears in the function. A test builds an EDL for a second topic and asserts different total duration."
**If ignored:** F2 cannot be built by the pipeline; every episode is Artemis with renamed files.

## SCR-08 — L8: require packaging to be generated, not copied

**Spec:** L8 done-when "package draft is generated from the episode artifacts with zero manual copy-paste of credits".
**Reality:** `tools/packaging/packaging.py` is imported nowhere; `cmd_package_draft` (`run_episode.py:552-568`) copies files and writes a status manifest only.
**Proposal:** add to L8: "`package_draft` calls `tools.packaging` to emit titles/thumbnail/credits from `rights_records.json`; a test asserts the credits block contains every asset credit."
**If ignored:** the packaging module stays test-only and L8 remains FAIL after every milestone.

## SCR-09 — F0/F1 ordering vs an in-flight S7

**Spec:** §6 says start with F0, then F1 "finish the 3-model bake-off (S7)".
**Reality:** S7 is Kilo's in-flight work (`s7-klein-1` RUNNING per `S7_STATE.md`); an F0 audit is read-only and must not block or restart it.
**Proposal:** add to §6: "F0 is read-only and may run in parallel with an in-flight S7; F0 must not submit, cancel or poll jobs. F1 starts from the first S7 phase not DONE."
**If ignored:** an auditor may duplicate or interrupt a GPU run.

## SCR-10 — Git protocol is unsafe on a shared dirty branch

**Spec:** §2 "commit own paths only, `git pull --rebase`, push non-force".
**Reality:** at audit time the branch was **ahead 32 / behind 1** with Kilo's uncommitted edits (`scripts/s5_push_bakeoff.py`, `tests/test_s5_*`, `docs/openmontage/S5_STATE.md`). A plain `pull --rebase` on that tree is unsafe; the divergence existed only to upload the spec file.
**Proposal:** replace with: "If the worktree is dirty or diverged, fetch and rebase only your own commits (`git rebase --onto`/ dedicated worktree); never rebase another agent's tracked edits; if the divergence is only the spec upload, merge it forward instead of rebasing."
**If ignored:** a rebase can silently mix two agents' work or fail mid-milestone.

---

## Not proposed (deliberately)

- No threshold value changes (owner-only).
- No change to the 10-layer structure, the hard rules in §1, or the "100% done" bar in §7.
- No new dependencies or paid routes.
