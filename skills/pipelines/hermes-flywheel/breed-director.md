# Breed Director — Hermes Flywheel

## When to Use
You are the **Breed** stage — you close the loop. You take this generation's
scored individuals (via `population_store`) and the `score_report`, select the
fittest parents with `breed_mutator` action=`select_parents`, then cross + mutate
them into `population_size` seed variants for the next generation.

## Process
### Step 1: Load this generation
`population_store` action=`load_generation` with `generation=<current>`. (If the
run is mid-flight you may also `load_population` top_k to include elites from
prior gens — elitism across the whole run helps.)

### Step 2: Select parents
`breed_mutator` action=`select_parents`:
- `individuals` = this generation's individuals
- `elite_fraction` / `exploration` from manifest `metadata.flywheel`
- Returns `elite` (top-K) + `explorers` (random lower-ranked, for diversity)

### Step 3: Breed next generation
`breed_mutator` action=`breed` with the selected `parents`, `population_size`
from manifest, `mutation_rate`, and a `seed` (use `generation` as seed for
reproducibility, or a fixed run seed). Returns `seeds[]` — each a compact trait
bundle (`topic, tone, structure, angle, retention_anchors, novelty_flag,
parent_ids, mutations`).

### Step 4: Persist + decide continuation
Persist `next_generation_seeds`. Then the **flywheel-director** decides whether
to loop or terminate:
- If `generation >= metadata.flywheel.generations_target` → terminate.
- If best-score gain over the last 2 generations < `convergence_threshold` → terminate (converged).
- Else → advance: the next generation's Script stages consume these seeds.

### Step 5: Submit + END TURN
Emit `next_generation_seeds`. In autonomous mode the orchestrator (or the
driving MCP agent) launches generation+1's Script stages. Checkpoint here is
auto; flip `human_approval_default: true` in the manifest for human oversight of
each new generation.

## Mutation operators (applied probabilistically)
- `angle_flip` — invert/challenge the parent premise.
- `constraint_relax` — drop an artificial constraint.
- `retention_boost` — add one more surprising fact.
- `novel_concept` — force a structure none of the top individuals use.

## Common Pitfalls
- Selecting only elites (no `explorers`) → premature convergence / inbreeding.
- Breeding with `mutation_rate=0` → every generation is a clone; the flywheel stalls.
- Losing `parent_ids` → can't trace lineage or detect stagnation.

## Gate Reminder
Auto by default. Checkpoint `status="auto"`, END TURN; the flywheel-director loops or stops.
