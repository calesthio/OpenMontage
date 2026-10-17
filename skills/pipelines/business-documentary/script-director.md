# Script Director - Business Documentary Pipeline

## When To Use

Stage 4 of 12. You write the English narration from the approved
`evidence_ledger`. The script is the film's spine: every factual sentence
carries the evidence IDs that support it, and nothing else enters.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `topic_brief`, `evidence_ledger` (validated) | Angle + facts |
| Schema | `schemas/artifacts/script.schema.json` | Output validation |
| Lib | `lib/artifact_ids.check_script_claims()` | Reject unknown `EV-` IDs |

## Process

### 1. Structure for 60–90 seconds (pilot)

| Section | Share | Job |
|---------|-------|-----|
| hook | 10–15% | One concrete image or number that makes the mechanism visible |
| body 1 | 30% | How the money is actually made |
| body 2 | 30% | How the product is made / serviced / moved |
| turn | 10–15% | The dependency, cost or failure |
| close | 10% | What this explains about the thing in the viewer's life |

For editorial pilots, scale the same skeleton — do not pad it.

### 2. Cite as you write

Every factual sentence gets its `evidence_ids`. Write them inline as you
draft; retrofitting citations afterwards is how fabricated claims survive.

```json
{
  "section_id": "body-1",
  "narration": "Route density is the whole business: a truck that stops ten...",
  "duration_seconds": 14.0,
  "evidence_ids": ["EV-edgar-10k-2024-route-density"]
}
```

### 3. Explain a mechanism, do not re-narrate sources

The viewer should finish understanding *why* the economics work, not what a
filing said. Use the evidence to carry a claim you are making.

### 4. Keep numbers speakable and honest

- Round in speech only when the rounding is stated ("about", "roughly").
- Date every number that can move ("as of 2024").
- Add `pronunciation` notes for brands, acronyms, units and company names —
  these feed the narration director.

### 5. Duration discipline

Sum section `duration_seconds` and set `total_duration_seconds`. Narration at
~150 wpm is a starting estimate only; the real number comes from the audio
file at stage 7.

### 6. Self-check before handoff

```bash
python -c "
from lib.artifact_ids import check_script_claims, summarize
print(summarize(check_script_claims(script, evidence_ledger)))
"
```

Any `resolved: false` blocks the checkpoint.

### 7. Quality gate

- Schema-valid `script`.
- Every factual section carries resolving `evidence_ids`.
- Hook, body, turn and close are distinct.
- `total_duration_seconds` is within tolerance of the sum of sections.
- No claim without evidence. No invented number.

## Common Pitfalls

- Writing the hook as a question stack ("Have you ever wondered...?").
- Burying the mechanism in adjectives.
- Citing one source for a contested claim.
- Padding duration with filler sentences to hit a target length.

---

## Gate Reminder (Binding)

`script` gates on human approval. After review passes: checkpoint
`status="awaiting_human"`, present the script with its citation coverage, and
**END YOUR TURN**.
