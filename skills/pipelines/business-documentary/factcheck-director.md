# Fact-Check Director - Business Documentary Pipeline

## When To Use

Stage 5 of 12. You verify every claim in the `script` against the
`evidence_ledger` and any independent source you can reach, and you produce a
`fact_check_report` whose `status` can stop the pipeline.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `script`, `evidence_ledger` (validated) | Claims + evidence |
| Schema | `schemas/artifacts/fact_check_report.schema.json` | Output validation |
| Lib | `lib/artifact_ids.check_fact_check_report()` | Reference resolution |

## Process

### 1. Extract every claim from the script

Walk each section. A claim is anything a viewer could repeat as fact: a
number, a date, a causal statement, a superlative, an attribution. Give each a
`claim_id` (`CLM-...`).

### 2. Verdict each one

| Verdict | Meaning |
|---------|---------|
| `confirmed` | The cited evidence supports it as stated |
| `partially_confirmed` | Supported in substance; scope/date/number needs narrowing |
| `disputed` | Credible sources disagree |
| `refuted` | Evidence contradicts it |
| `unverified` | No source establishes it |

`unverified` is a legitimate result and must be reported. It is not a
licence to keep the line.

### 3. Check the arithmetic and the framing

- Do the numbers in the sentence match the numbers in the extract?
- Is a correlation stated as a cause?
- Is one company's experience stated as an industry rule?
- Is a projection stated as an outcome?

### 4. Record conflicts, don't resolve them silently

Use `conflicts[]` with `source_a` / `source_b` and the resolution you applied.
If you cannot resolve it, the claim is `disputed` and needs a caveat in the
script.

### 5. Escalate legally sensitive material

Any accusation of fraud, liability, safety failure or wrongdoing sets
`legally_sensitive: true` and `enhanced_review_required: true`. Those claims
need the strongest available sourcing and an explicit human decision.

### 6. Act on every verdict

- `keep` — supported as written.
- `reword` — narrow the scope/date/number.
- `downgrade_to_hypothesis` — keep only as an explicitly labelled hypothesis.
- `cut` — remove.
- `escalate` — send to enhanced review before proceeding.

### 7. Set the report status

- `blocked` when any `refuted`/`disputed` claim survives in the script, or
  when `summary.central_thesis_status` is `unsupported`.
- `revise` when claims need rewording but the thesis stands.
- `pass` when every claim is confirmed or explicitly labelled.

`blocked` stops the pipeline. Rewrite the script (back to stage 4) or change
the thesis — do not proceed.

### 8. Quality gate

- Every script section has at least one verdict row.
- Every `evidence_ids` entry resolves.
- `summary` counts equal the number of rows.
- `summary.central_thesis_status` is explicit.

## Common Pitfalls

- Verdicting the source rather than the claim ("this is a 10-K, so it's
  true"). Read the line.
- Accepting a company's own market-size claim without a methodology note.
- Marking a claim `confirmed` because the CEO said it on a podcast.
- Letting a "partially confirmed" claim through with its broad framing.

---

## Gate Reminder (Binding)

`fact_check` gates on human approval. When status is `blocked`, checkpoint
`status="failed"` with the blocking reasons and **END YOUR TURN** — never
forward a blocked report into storyboard.
