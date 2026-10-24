# Topic Director - Business Documentary Pipeline

## When To Use

Stage 1 of 12. You turn a rough subject — or nothing at all — into the
`topic_brief` that every later stage is measured against. This is the last
point where the subject is cheap to change.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/topic_brief.schema.json` | Artifact validation |
| Guide | `pipeline_defs/business-documentary.yaml` | Stage contract |
| Meta | `skills/meta/reviewer.md` | Self-review before checkpoint |

## Process

### 0. Runtime is presented here, before any asset exists (MANDATORY)

AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": the
composition runtime is a **conversation at planning time**, never a default.
Before the angle is approved, check what this machine can actually run:

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
print(registry._tools['video_compose'].get_info().get('render_engines'))
"
```

Present **every available runtime** with a one-line tradeoff tied to this
brief and a recommendation, then record the shortlist as a
`render_runtime_selection` entry in `decision_log`
(`category: "render_runtime_selection"`):

- **ffmpeg** — always available locally; direct cuts, trims, subtitle burn and
  Ken Burns motion. Cheapest and most predictable, least expressive.
- **hyperframes** (HyperFrames) — HTML/CSS/GSAP composition rendered through
  `npx hyperframes`: kinetic typography, motion graphics, data-driven scenes.
  Needs Node ≥ 22 + ffmpeg on PATH.
- **Remotion** — React composition with spring physics and the stock scene
  catalog. Needs `remotion-composer/node_modules` installed.

If `hyperframes` is not installed on this machine, say so explicitly and record
it as `rejected_because: "runtime not available on this machine"` — it stays in
the shortlist even when it cannot run.

A runtime that is not installed is recorded as
`rejected_because: "runtime not available on this machine"` — never dropped
from the list, and never swapped in silently at compose time. The locked
value travels unchanged into `edit_decisions.render_runtime` and
`render_report.metadata.render_runtime`.

### 1. Name the mechanism, not the subject

"Commercial laundry" is a subject. "How a $X industry built its margin on
route density, chemical contracts and reusable linen rental instead of on
washing" is an angle.

Write `unique_question` as ONE sentence that names an economic mechanism —
how money is made, how a product is made and serviced, or how a system fails.

Test: could a reader answer it with a single sentence of arithmetic? If not,
sharpen it.

### 2. Check that the angle is *sourceable* BEFORE locking it

Before the angle is approved, list the primary-source classes the angle needs
(`primary_source_expectations`) and confirm at least the plausible ones exist:

- corporate filings / annual reports (SEC EDGAR, company IR pages),
- regulator or agency documents,
- court records,
- patents,
- trade-association or industry data,
- official press releases.

**No web-search tool is registered in this repo.** Research runs on
sources you can actually reach — user-supplied links, fetched documents, or
`video_downloader` / `transcript_fetcher` when those dependencies are
installed. If the angle depends on a source class nobody can reach, pick a
different angle now, not at stage 5.

### 3. Fix the duration

| Duration | Use |
|----------|-----|
| 60–90s | E2E pilot — proves every stage runs |
| 6–10 min | first editorial pilot, only after a passing E2E |
| 8–15 min | target standard once the script and material earn it |

A longer target does not make a better film; it makes more unverified claims.

### 4. Record the constraints (mandatory)

`constraints` must state, at minimum:

- strict zero-cost mode (`budget_default_usd: 0.0`; unknown cost = BLOCK),
- English (US) narration,
- real footage with per-asset provenance and license,
- no automatic publishing.

### 5. Record the "why it works" case

`why_it_works` — 2–5 entries naming what earns the film: a mechanism nobody
explains, a surprising number, a scale, a failure, a dependency.

### 6. Quality gate

- `unique_question` is one sentence naming a mechanism.
- `target_duration_seconds` is concrete and matches the pilot phase.
- `primary_source_expectations` is non-empty and plausible.
- `constraints` includes the zero-cost statement.
- No number, company or causal claim appears anywhere in the brief. Claims
  belong to `evidence_ledger`, not to the topic.

## Common Pitfalls

- Choosing a topic because the footage is easy to find. The film is the
  research; the footage is illustration.
- Choosing a topic whose central claim is contested trade gossip.
- Locking an 8-minute ambition for the pilot. Prove the pipeline at 60–90s.
- Writing sample claims into the brief to make it look substantive.

---

## Gate Reminder (Binding)

`topic` gates on human approval (`human_approval_default: true`). After review
passes: checkpoint `status="awaiting_human"`, present the brief, and **END
YOUR TURN**. Do not start research in the same response.
