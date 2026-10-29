# OpenMontage Long-Form Spec — 40–50 min episodes (Milestone Z4)

**Source:** Z4 chapter mode (test-first, scripts/run_episode.py, tests/test_run_chapters.py)
**Status:** spec only — dry-run on Artemis blocked by unreachable Kokoro-82M weights (HF xet/CDN blocked from this network)

## 1. Chapter mode pipeline (implemented + tested)

`scripts/run_episode.py --chapters <topic_id>`:

1. **Split** script into chapters, each <= 6 min (360 s) of estimated narration
   (`_estimate_sentence_duration`: ~2.5 words/sec + 0.3s breath per sentence).
2. **Per chapter**: run the full Z3 pipeline (claim ledger → script → rights → narration → subtitles → EDL → render → finish_audio → qc → package) with its own checkpoint (`chapter_<i>` in chapter_state.json).
3. **Per-chapter resume**: OK chapters skipped on re-run; checkpoint hash mismatch forces re-execution.
4. **Disk budget**: checked globally before chapter 0 and before each chapter; < 800 MB free → BLOCKED, fail-closed.
5. **Concatenate** chapter videos with 1 s crossfades (ffmpeg xfade + acrossfade).
6. **Final loudness pass**: finish_audio loudnorm on the concatenated final file.

All 5 orchestration tests pass (split respects max duration, single chapter when short, per-chapter checkpoint+resume, chapter failure blocks remaining, disk budget before each chapter).

## 2. 40–50 min long-form targets

| Metric | Target | Basis |
|---|---|---|
| Total runtime | 40–50 min | Long-form YouTube episode |
| Chapter count | 7–9 chapters | 40–50 min / ~6 min per chapter |
| Claim count | 80–120 load-bearing claims | ~2 claims/min × 40–50 min |
| Sources per claim | 2 (NASA/ESA primary) | Single-source claims flagged |
| Footage-minutes needed | ~35–45 min of usable visuals | ~90% visual coverage of runtime |
| Narration share | >= 60% of chapter runtime | Spoken narration present for most of chapter |
| Original graphics | >= 1 per 90 s | Claim cards, source cards, stat cards |
| Archive clip limit | <= 20 s unannotated | Any archive clip > 20 s needs on-screen annotation |
| Still-only limit | <= 15 s | Consecutive still frames max 15 s |

## 3. Added-value gate (per chapter, must all pass)

A chapter is releasable only if:

- **Narration share**: narration audio present for >= 60% of chapter duration.
- **Original graphics**: at least one original graphics card per 90 s of chapter runtime (title, claim, source, stat, or credits card).
- **Archive annotation**: no archive clip > 20 s without on-screen annotation (claim_id, source card, or lower-third).
- **Still-only**: no run of still-only frames > 15 s.
- **Claim sourcing**: every load-bearing claim has 2 NASA/ESA primary sources reachable from this environment; single-source claims flagged in credits.
- **Rights**: every clip rights_basis in (`explicit_license`, `source_policy_us_gov`); unknown → BLOCKED.

## 4. Step ladder with go/no-go

| Step | Length | Entry criterion | Go/no-go driver |
|---|---|---|---|
| 1 | 3–4 min | Artemis draft (Z2 complete, QC PASS) | Owner decision |
| 2 | 8–10 min | Step 1 published + metrics reviewed | Owner's YouTube Studio metrics (CTR, AVD, retention) |
| 3 | 15–20 min | Step 2 published + metrics reviewed | Owner's YouTube Studio metrics |
| 4 | 40–50 min | Step 3 published + metrics reviewed | Owner's YouTube Studio metrics |

**No invented thresholds.** Go/no-go at each step is driven exclusively by the owner's YouTube Studio metrics (CTR, average view duration, retention curve, subscriber conversion). This spec records the ladder structure only; metric values and decisions belong to the owner.

## 5. Footage budget per topic (to be filled per topic)

| Topic | HD clips available | Rights basis | Primary docs reachable | Est. usable visual minutes | Max feasible length |
|---|---|---|---|---|---|
| (per topic — see Z5 SERIES_PLAN.md) | | | | | |

**Rule:** no demand claims beyond measured data (Z5). Footage-minutes needed vs available must be measured per topic before greenlighting a 40–50 min episode.

## 6. Not covered here

- Packaging (titles, thumbnails, description, synthetic-voice disclosure): Z7
- Scripts + claim ledgers for top 3 topics: Z6
- Series plan + topic ranking: Z5
