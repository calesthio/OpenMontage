# Flywheel Director — Hermes Creative Flywheel (Orchestrator)

## When to Use
You are the **executive producer / orchestrator** of the Hermes Creative
Flywheel. You own the autonomous loop: Script → Render → Score → Breed, repeated
across generations until convergence or the generation target. You are the
"autonomous dynamic content engine" — you keep the flywheel turning with no
human in the loop, while still writing checkpoints so a human can inspect or
take over at any gate.

This skill is also the contract for the **Hermes MCP integration**: when driven
by an external agent over MCP (`mcp_openmontage`), each stage below maps to an
MCP tool call. The loop logic is identical whether a human agent or an MCP
client runs it.

## Loop contract
```
gen = 0
loop:
  1. SCRIPT     run N Script stages (N = population_size), one per seed
                (gen 0: seeds are blank starts from the brief)
  2. RENDER     run each individual's Render stage (underlying pipeline)
  3. SCORE      score + record every individual (population_store)
  4. BREED      select parents + emit next_generation_seeds
  5. DECIDE     terminate if gen >= target OR converged; else gen++ and repeat
```

## Process
### Step 1: Initialize the run
- Create the Backlot project (`projects/<name>/flywheel/`). Set `budget_usd`
  from manifest (`budget_default_usd`); per-individual budget = total / population_size.
- Read manifest `metadata.flywheel` for `population_size, elite_fraction,
  exploration, mutation_rate, generations_target, convergence_threshold`.
- For gen 0, derive `population_size` blank seeds (topic from `brief`, no parents).

### Step 2: Drive each stage via the stage directors
For every stage, read the matching `*-director.md` skill BEFORE acting. In
autonomous mode, checkpoints are `status="auto"` and you continue without
waiting — but you still WRITE the checkpoint (Backlot shows progress).

### Step 3: Track convergence
Maintain `best_score` per generation (from `population_store` state). If
`best(gen) - best(gen-1) < convergence_threshold` for two consecutive
generations, set `converged: true`.

### Step 4: Terminate gracefully
On termination:
- Write `flywheel_state` final `{generation, best_score, best_individual_id, converged}`.
- Emit a `run_summary`: best individual, its score + components, generations run, total cost, whether converged.
- The best individual's `render_path` / `artifact` is the flywheel's output.

## MCP mapping (agentic integration)
When driven over MCP, the loop is the same; the driving agent calls:
- `om_list_pipelines` / `om_load_pipeline(name="hermes-flywheel")`
- `om_run_stage(pipeline, stage, project_dir, inputs)` — runs a stage director
- `om_score_artifact(artifact)` → `breed_scorer`
- `om_breed(generation, individuals)` → `breed_mutator`
- `om_population(project_dir, action)` → `population_store`
- `om_backlot_state(project_dir)` → read board state

## Guardrails
- Never exceed the run budget (reserve via `cost_tracker` before paid renders).
- Always record scored individuals, even failures (the loop learns from them).
- Preserve `parent_ids` lineage so stagnation is detectable.
- Respect `max_wall_time_minutes` from the manifest — bail out with a partial `run_summary` rather than hang.

## Common Pitfalls
- Human-in-the-loop by accident: if a stage's `human_approval_default` is true, the loop blocks. Set false for autonomy.
- Not writing checkpoints → invisible run, no Backlot visibility, no resume.
- Infinite loop: always check `generations_target` AND convergence.
