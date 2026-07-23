# Script Director — Hermes Flywheel

## When to Use
You are the **Script** stage of the Hermes Creative Flywheel. For generation 0
you write a narration script + scene plan from a `brief` (same craft as
`skills/pipelines/explainer/script-director.md`). For generation > 0 you
instead receive a **breed seed** — a compact trait bundle from `breed_mutator`
— and you mutate the previous generation's best script along those traits.

The flywheel's intelligence lives in the seeds. Honor them: if a seed says
`angle_flip`, write the counter-angle. If it says `novel_concept`, try a
genuinely new structure. If it carries `retention_anchors: N`, plant N
surprising facts.

## Prerequisites
| Layer | Resource |
|-------|----------|
| Schema | `schemas/artifacts/script.schema.json` |
| Gen 0 | `brief` artifact; active style playbook; `skills/meta/voice-performance-director.md` |
| Gen > 0 | `next_generation_seeds` (one entry assigned to you) + best parent artifacts from `population_store` |
| Meta | `meta/reviewer.md`, `meta/checkpoint-protocol.md` |

## Process
### Step 1: Determine generation mode
- Read `flywheel_state` (via `population_store` action=state). If `generation == 0`, this is a cold start: follow the standard explainer script craft from the brief.
- If `generation > 0`, read the seed assigned to you (`breed_mutator` emits `seeds[]`; you own `variant == your_index`). Pull the parent individuals from `population_store` (load_best / load_generation) to see what already scored well.

### Step 2: Apply the seed traits
Map each seed field to a concrete script decision:
- `topic` / `tone` / `structure` — inherit (this is the crossover payoff).
- `angle` — if it starts with `counter-angle:` or `inverted premise`, flip the premise of the parent script.
- `constraint_relax: true` — drop an artificial constraint the parent imposed (e.g., a forced CTA, a rigid structure) to see if freedom scores higher.
- `retention_anchors` — plant exactly that many surprising/counterintuitive facts as retention anchors.
- `novelty_flag: true` — adopt a structure none of the current top individuals use (check the population for variety).

### Step 3: Write the script
Follow the explainer `script-director.md` craft (hook → setup → build → climax → landing), enhancement cues every 8–10s, explicit voice-performance plan, word budget by duration. The fitness function (`breed_scorer`) rewards hook_power, narrative_flow, visual_density, retention, cohesion, novelty, duration_fit, cost_efficiency — so engineer for all of them.

### Step 4: Self-evaluate (pre-score)
Score yourself 1–5 on hook power, word-count accuracy, narrative flow, enhancement density, novelty. If any < 3, revise before submitting.

### Step 5: Submit
Persist the `script` + `scene_plan` artifacts. Emit a compact `artifact` preview object the Render stage will expand: include `topic`, `duration_seconds`, `target_duration_seconds`, `word_count`, `target_word_count`, `sections` (with `enhancement_cues`), `retention_anchors`, `novelty_flag`, `budget_usd`, `notes`. **END YOUR TURN** at the checkpoint (autonomous mode resumes automatically).

## Common Pitfalls
- Ignoring the seed and rewriting from scratch (you waste the evolution).
- Planting fewer retention anchors than the seed asks for (fitness penalizes it).
- Letting generations converge to identical structure — `novelty_flag` exists to fight that; use it.
- Forgetting enhancement cues — `visual_density` is a HARD GATE in `breed_scorer`; below 0.4 the render is non-viable.

## Gate Reminder
Autonomous (`human_approval_default: false`). After review passes, checkpoint with `status="auto"` and END YOUR TURN; the Render stage proceeds.
