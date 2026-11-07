# Editorial Director - Business Documentary Pipeline

## When To Use

Stage 9 of 12. You decide whether each downloaded clip actually serves its
scene. This is the multi-stage alignment review: not one similarity score,
but sampled frames, observed content, a visual class, a factual-specificity
risk, and a reuse penalty.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifacts in | `asset_manifest`, `scene_plan`, `script` (validated) | Picks to review |
| Schema | `schemas/artifacts/alignment_report.schema.json` | Output validation |
| Registry | `frame_sampler`, `visual_qa` | Frame sampling + checks |
| Lib | `lib/artifact_ids.check_alignment_report()` | Scene/asset resolution |

## Process

### 1. Sample several real frames per candidate

One thumbnail is not evidence. Pull frames from the start, middle and end of
each candidate (`frame_sampler`), and inspect them. Record
`frames_inspected` and `frame_paths`.

### 2. Describe what is actually there

`observed_objects` and `observed_actions` — what you can see, in plain words.
If the scene needs a forklift and the frames show a conveyor, the clip is
rejected regardless of its retrieval score.

### 3. Score the alignment, then override the score

`semantic_match` from retrieval, plus your own read. The score ranks
candidates; it does not accept them.

### 4. Check factual specificity

`factual_specificity_risk` measures how likely a viewer is to believe this
footage shows the *specific* company, plant, event or brand named in the
narration. Generic industrial footage under a named company is exactly this
risk. High risk means either the scene becomes explicitly `illustrative` or
the clip is rejected.

### 5. Penalize reuse

`reuse_penalty` applies when the same or a near-duplicate clip already appears
in the film. `summary.max_reuse_count` reports the worst offender.

### 6. Verdict each scene

- `accepted` — serves the scene, class is honest.
- `rejected` — wrong content; another candidate exists.
- `blocked` — no valid asset exists; the run stops.

### 7. Keep the rejection trail

Every pass over a candidate goes into `metadata.rejected_picks` with its
reason. This is the training signal for the golden-set regression tests and
the only way to prove a rejection was not arbitrary.

### 8. Quality gate

- Every scene has a verdict with at least one reason.
- Every `picked_asset_id` resolves against the manifest.
- Every `scene_id` resolves against the scene plan.
- `illustrative` scenes are counted in the summary so the edit can label them.

## Common Pitfalls

- Accepting a clip because the score is high and the deadline is close.
- Believing a frame match proves an event match.
- Reusing one hero clip across scenes to cover weak searches.
- Leaving `observed_objects` empty on an accepted pick.

---

## Checkpoint Note

`editorial` is auto-approved (`human_approval_default: false`). Any `blocked`
scene still stops the run before compose.
