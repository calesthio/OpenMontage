# Score Director — Hermes Flywheel

## When to Use
You are the **Score** stage — the fitness function of the flywheel. You take the
rendered `artifact` and compute an explainable fitness with `breed_scorer`, then
persist the individual to `population_store`. This is the measurement that makes
evolution possible; it must be honest and reproducible.

## Process
### Step 1: Compute fitness
Call `breed_scorer` action=`rubric` with the `artifact`:
- If you (the agent) have taste-judged the piece, include `llm_score` (0–1) in the artifact so the rubric folds it into hook_power / narrative_flow / cohesion.
- Otherwise `breed_scorer` derives structural proxies — still valid, just less "tastey".

Read back `score`, `components`, `explanation`, `passed_hard_gate`.

### Step 2: Record the individual
Assemble the individual and call `population_store` action=`record`:
```json
{
  "project_dir": "projects/<name>",
  "individual": {
    "id": "<variant id>", "generation": <gen>,
    "parent_ids": <from seed>, "pipeline": "<base>",
    "topic": "...", "artifact": <artifact>,
    "score": <fitness>, "created_at": <epoch>,
    "notes": "<explanation>"
  }
}
```
The store maintains `flywheel_state` (generation, best_score, count) and appends to `population.jsonl` — visible on the Backlot board.

### Step 3: Surface the result
Write `score_report` = `{individual_id, generation, score, components, explanation, passed_hard_gate, best_score_so_far}`. Emit it as the stage artifact.

### Step 4: Pass-through (no creative decision)
Scoring is non-creative. `checkpoint_required: false`; autonomous mode proceeds straight to Breed. END YOUR TURN.

## Selection criteria the loop depends on
`breed_mutator` ranks individuals by `score`. Be consistent: always store the
same `score` value you report. A hard gate (`visual_density < 0.4`) marks a
render non-viable — such individuals should still be recorded (so the loop can
see what failed) but they will naturally rank low.

## Common Pitfalls
- Storing a different score than you report (breaks ranking).
- Forgetting to persist (the Breed stage has nothing to select from).
- Scoring on vibes alone without `components` — the explainability is the point.

## Gate Reminder
Auto (`human_approval_default: false`, `checkpoint_required: false`). END TURN → Breed.
