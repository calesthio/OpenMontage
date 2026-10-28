# Executive Producer - Business Documentary Pipeline

## When To Use

The factory is producing an original English-language business documentary —
the "Hidden Business Behind Everyday Things" niche: how an obscure industry,
company or supply chain actually makes money, how a familiar product gets made
and serviced, and what happens when the system breaks.

You are here when the ask is a *research-led explainer film*, not a montage,
not a talking head, not a marketing clip:

- "How do commercial laundry businesses work?"
- "Why do pallets matter to global shipping?"
- "Who actually makes the world's X?"
- "What happened to Y when it collapsed?"

If the brief is a tone poem → `documentary-montage`. If it is a product promo →
`animation` / `cinematic`. If it is a presenter → `talking-head` /
`avatar-spokesperson`.

## Philosophy

This pipeline is **evidence-first**. The film's value is the research, not the
footage:

1. **A claim exists only after its evidence exists.** Nothing in the script is
   asserted that the ledger does not carry.
2. **Real footage, honestly labelled.** Illustrative material is labelled
   illustrative. It is never presented as coverage of the named company.
3. **Fail closed.** No valid clip, unverified central thesis, unclear license,
   unknown cost, failed QA — the run stops. It does not ship a thin version.
4. **$0 at the request boundary.** Strict zero-cost mode is the default. A call
   with an unknown price or an unnamed route is BLOCKED, never assumed free.
5. **Manual publish.** The pipeline ends at a reviewed package. It never
   uploads by itself.

## Stages

| # | Stage | Director skill | Produces | Gate |
|---|-------|----------------|----------|------|
| 1 | `topic` | `topic-director.md` | `topic_brief` | human |
| 2 | `research` | `research-director.md` | `research_brief` | auto |
| 3 | `evidence` | `evidence-director.md` | `evidence_ledger` | human |
| 4 | `script` | `script-director.md` | `script` | human |
| 5 | `fact_check` | `factcheck-director.md` | `fact_check_report` | human |
| 6 | `storyboard` | `storyboard-director.md` | `scene_plan` | human |
| 7 | `narration` | `narration-director.md` | `narration_manifest` | auto |
| 8 | `footage` | `footage-director.md` | `asset_manifest` | human |
| 9 | `editorial` | `editorial-director.md` | `alignment_report` | auto |
| 10 | `compose` | `compose-director.md` | `render_report` | auto |
| 11 | `qa` | `qa-director.md` | `qa_report` | auto |
| 12 | `publish` | `publish-director.md` | `publish_package` + `publish_log` | human |

Read the director skill **before** starting the stage it names. The director
skill is the quality bar; this file is the order of operations.

## Budget: strict $0 by default

`orchestration.budget_default_usd` is `0.0`. Before any network or model call
run it through the gate:

```python
from lib.zero_cost_gate import ToolFacts, evaluate_call, facts_from_registry

facts = facts_from_registry("direct_clip_search", "search", cost_usd=0.0,
                            route="archive.org+wikimedia+nasa (no-key)")
decision = evaluate_call(facts)          # blocked unless cost AND route are known
```

- `cost_usd=None` → BLOCKED. Unknown pricing is never "free".
- non-zero cost → BLOCKED unless the user approved *that specific* action.
- auth / billing / rate-limit / transport failure → **stop and report**.
  Never silently reroute to another provider
  (`lib.zero_cost_gate.reroute_allowed()` is always `False`).
- Record the ledger of decisions (`RunBudgetLedger.summary()`) in the
  checkpoint metadata so the report can prove no paid route ran.

## Cross-Stage Rules (binding)

- **ID resolution.** Every `evidence_id`, `source_id`, `scene_id` and
  `asset_id` referenced downstream must resolve to the artifact that defines
  it. Run `lib.artifact_ids.resolve_all()` before every gated checkpoint:

  ```python
  from lib.artifact_ids import assert_resolved, summarize
  problems = resolve_all(artifacts)
  if problems:
      raise DanglingReferenceError(...)   # or checkpoint status=blocked
  ```

- **Fail-closed stage statuses.** A stage that cannot produce a valid artifact
  writes `status="failed"` (or `blocked` where the schema offers it) with the
  reason. It never writes a hollow "success".
- **No silent substitution.** Switching provider, model, runtime, or dropping
  narration/music requires a `decision_log` entry and, for material changes,
  human approval.
- **Idempotence.** Re-running a stage reuses its artifact only when input
  hashes and tool versions are unchanged.
- **Preserve user state.** Never `git reset`, `git clean`, force-push, or
  delete another agent's uncommitted work.

## Runtime Selection (MANDATORY at the storyboard/compose boundary)

Check what is actually installed before locking `render_runtime`:

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
info = registry._tools['video_compose'].get_info()
print(info.get('render_engines'))
"
```

Present **every available runtime** to the human with a plain-language
tradeoff and record the full shortlist as a `render_runtime_selection`
decision (`category: "render_runtime_selection"`). A decision that lists only
the runtime you happened to pick is a CRITICAL reviewer finding. If only one
runtime is available, say so out loud and record the others as
`rejected_because: "runtime not available on this machine"`.

Never swap the locked runtime at compose time — surface a blocker instead.

## Common Pitfalls

- Writing the script before the evidence ledger exists. The script then
  invents its own facts.
- Treating a 200 OK response as proof of a claim. Availability is not accuracy.
- Accepting the first search hit with a plausible filename. License and
  provenance are checked per asset, not per source.
- Rendering a scene with no valid asset to "keep the timeline full".
- Claiming QA passed because a helper class worked. QA measures the final file.
- Letting a paid fallback run because the free path timed out. Stop and ask.

---

## Gate Reminder (Binding)

Gated stages on this pipeline: `topic`, `evidence`, `script`, `fact_check`,
`storyboard`, `footage`, `publish`. After review passes at a gated stage:
checkpoint with `status="awaiting_human"`, present the summary, and **END YOUR
TURN**. Approval is per-gate — an earlier "go ahead" never covers a later one
unless it was recorded as a `decision_log` entry with
`category: "approval_policy"`.
