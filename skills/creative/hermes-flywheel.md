---
name: hermes-flywheel
description: >-
  Drive the Hermes Creative Flywheel autonomously: an evolutionary content
  engine that runs OpenMontage's pipeline as a generation, scores each render
  with an explainable fitness function, then breeds the fittest into seed
  variants for the next generation (Script -> Render -> Score -> Breed). Use
  when the user wants autonomous, self-improving video generation, or when
  driving OpenMontage over the mcp_openmontage MCP server. Trigger on phrases
  like "run the flywheel", "autonomous content engine", "breed better videos",
  or any request to iterate/evolve a video concept without manual review.
---

# Hermes Creative Flywheel — Autonomous Driver Skill

You are the autonomous operator of OpenMontage's **Hermes Creative Flywheel**.
The flywheel turns video production into an evolutionary loop: each generation
produces `population_size` rendered individuals, scores them, and breeds the
best into the next generation's seeds. Your job is to keep it turning until it
converges or hits the generation target — with no human in the loop.

## Mental model
```
              ┌─────────────────────────────────────────────┐
              │  SCRIPT → RENDER → SCORE → BREED  (xN per gen)│
              └──────────────────────┬──────────────────────┘
                                     │ next_generation_seeds
                                     ▼  (loops back to SCRIPT)
```
- **Script**: write/expand the script from a seed (gen 0 = from brief).
- **Render**: run a base OpenMontage pipeline (assets→edit→compose).
- **Score**: `breed_scorer` fitness + `population_store` record.
- **Breed**: `breed_mutator` selects parents, crosses + mutates → seeds.

## How to drive it (MCP integration)
When connected to the `openmontage-hermes-flywheel` MCP server, call its tools:
- `om_load_pipeline("hermes-flywheel")` — get stages + config.
- `om_score_artifact(artifact_json)` — fitness for one render.
- `om_breed(action="select_parents"|"breed", ...)` — selection / next-gen seeds.
- `om_population(project_dir, action=...)` — persist/load the population.
- `om_backlot_state(project_dir)` — read the live board.
- `om_run_stage(pipeline, stage, project_dir, inputs_json)` — execute a stage's tools.

If MCP isn't connected, call the same logic directly via the tools:
`breed_scorer`, `breed_mutator`, `population_store` in `tools/evolution/`, and
follow the `skills/pipelines/hermes-flywheel/*-director.md` skills for each stage.

## Loop procedure
1. **Init**: create `projects/<name>/flywheel/`. Read `metadata.flywheel` from the
   manifest for `population_size, elite_fraction, exploration, mutation_rate,
   generations_target, convergence_threshold`. Per-individual budget = total/N.
2. **For each generation g (0..target)**:
   a. **Script** × N: one Script stage per seed (gen 0 seeds are blank starts).
      Read `script-director.md`; honor the seed traits exactly.
   b. **Render** × N: run each individual's base pipeline render. Read
      `render-director.md`. Reserve budget via `cost_tracker` before paid calls.
   c. **Score** × N: `breed_scorer` (action=rubric) → `population_store` (record).
      Record even failures (the loop learns from them; hard gate is visual_density).
   d. **Breed**: `breed_mutator` select_parents → breed (next gen seeds).
   e. **Decide**: terminate if `g >= generations_target` OR best-score gain over
      the last 2 gens < `convergence_threshold`. Else loop with new seeds.
3. **Finish**: write final `flywheel_state` + `run_summary` (best individual, score,
   components, generations, total cost, converged?). Emit the best `artifact`.

## Guardrails (non-negotiable)
- Respect total budget; never exceed per-individual budget.
- Always WRITE checkpoints (Backlot shows progress; run is resumable).
- Preserve `parent_ids` lineage; detect stagnation via score plateaus.
- Honor `max_wall_time_minutes` — bail with a partial `run_summary` rather than hang.
- This is autonomous: stages have `human_approval_default: false`. If you want a
  human gate per generation, set that field true in the manifest before running.

## Output to the user
Report: generations run, best fitness + which generation, total cost, whether it
converged, and a one-line description of the winning concept. Point them to the
Backlot board (`projects/<name>/flywheel/`) for the live view.
