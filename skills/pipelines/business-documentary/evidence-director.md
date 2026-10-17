# Evidence Director - Business Documentary Pipeline

## When To Use

Stage 3 of 12. You normalize the `research_brief` into an `evidence_ledger`:
one row per checkable claim, with a stable ID, a verbatim extract and an
honest quality/caveat read. This ledger is the only place a fact may come
from for the rest of the run.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact in | `research_brief` (validated) | Source map |
| Schema | `schemas/artifacts/evidence_ledger.schema.json` | Output validation |
| Lib | `lib/artifact_ids.py` | `source_id` resolution |

## Process

### 1. One entry per checkable claim

A claim is checkable when a reader could go to the source and confirm or
refute it. "The company grew" is not checkable; "segment revenue rose from
$A in 2019 to $B in 2024 (10-K p.32)" is.

### 2. Derive IDs, never invent them

`evidence_id` = `EV-<slug>` derived from source + claim, e.g.
`EV-edgar-10k-2024-segment-revenue`. It must be stable across reruns and
unique inside the ledger. An ID that exists nowhere in the ledger and is cited
by the script is a fabrication — the stage must fail.

### 3. Verbatim extracts only

`extract` is copied from the source, not paraphrased. If the source is an
image or a video, quote the caption/transcript and say where it came from.
A paraphrase in the extract field is a defect.

### 4. Label the claim honestly

`claim_label` separates **fact / interpretation / estimate / forecast /
opinion**. An analyst's projection is not a fact. A company's own market-size
claim is an estimate unless independently method-checked.

### 5. Carry the numbers properly

Each exact number gets a `metrics[]` entry with `value`, `unit`, `as_of_date`
and `geography`, plus a `methodology_note` when the method matters (e.g. how
an industry body counts "revenue").

### 6. Record quality and caveats

- `quality`: high / medium / low.
- `caveats[]`: single source, contested figure, company-self-reported,
  projection, translation, outdated.
- `corroborated_by[]`: other `SRC-...` IDs that independently support it.

### 7. Fail closed on the central thesis

If the central thesis has no primary evidence, the ledger records the gap in
`metadata.source_gaps` and the run moves to `script` with the thesis either
dropped or explicitly downgraded to a labelled hypothesis. The pipeline does
not proceed on hope.

### 8. Quality gate

- Every entry: non-empty verbatim extract, resolving `source_id`, label,
  quality, caveats (possibly empty only for uncontested facts).
- No duplicate `evidence_id`.
- `metadata.source_gaps` is present.

## Common Pitfalls

- Paraphrasing into the extract field and calling it a quote.
- Marking an industry trade-association projection as `fact`.
- One giant entry that bundles five claims — it can never be refuted or fixed
  precisely.
- Leaving `caveats` empty on every entry to look confident.

---

## Gate Reminder (Binding)

`evidence` gates on human approval. After review passes: checkpoint
`status="awaiting_human"`, present the ledger summary (claim count, source
gaps, anything contested), and **END YOUR TURN**.
