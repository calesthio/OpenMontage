# Hermes Creative Flywheel — Autonomous Content Engine

An evolutionary content engine wired into OpenMontage's instruction-driven
pipeline system. It turns video production into a self-improving loop:

```
Script → Render → Score → Breed  (×N individuals per generation, repeated)
```

- **Script** — write/expand a narration script + scene plan (from a seed in gen > 0).
- **Render** — run an underlying OpenMontage pipeline (assets → edit → compose).
- **Score** — `breed_scorer` fitness function (explainable, 0–1) + `population_store`.
- **Breed** — `breed_mutator` selects the fittest parents, crosses + mutates them
  into seed variants for the next generation. Closes the loop.

The loop converges toward better videos autonomously (no human in the loop by
default; checkpoint gates are opt-in via `human_approval_default`).

## Files
| Path | Purpose |
|------|---------|
| `pipeline_defs/hermes-flywheel.yaml` | Pipeline manifest (validated by `pipeline_manifest.schema.json`). |
| `skills/pipelines/hermes-flywheel/*.md` | Stage director skills (script/render/score/breed/flywheel). |
| `skills/creative/hermes-flywheel.md` | Hermes skill: autonomous loop driver. |
| `skills/creative/video-media-skill-selector.md` | Reference: how to choose a Video & Media skill (planning/editing/transcription/audio/delivery), with preflight + rights discipline for the Render stage. |
| `tools/evolution/breed_scorer.py` | Fitness function (the "Score" stage). |
| `tools/evolution/breed_mutator.py` | Crossover + mutation (the "Breed" stage). |
| `tools/evolution/population_store.py` | Per-generation persistence under `projects/<name>/flywheel/`. |
| `mcp_openmontage/server.py` | **MCP server** — agentic integration surface (7 tools + resources). |
| `backlot/state.py` (`_collect_flywheel`) | Backlot board panel for live flywheel state. |
| `tests/contracts/test_flywheel_evolution.py` | Contract tests (11 passing). |

## Run the MCP server (agentic integration)
```bash
# from the OpenMontage repo root, with the clean venv:
. .venv_clean/bin/activate        # or: env -u PYTHONPATH ./.venv_clean/bin/python
pip install "mcp>=1.0"
python -m mcp_openmontage.server
# or, for hot-reload dev:  mcp dev mcp_openmontage/server.py
```
Exposed MCP tools: `om_list_pipelines`, `om_load_pipeline`, `om_run_stage`,
`om_score_artifact`, `om_breed`, `om_population`, `om_backlot_state`.
Resources: `openmontage://pipelines/{name}`, `openmontage://registry`.

## Drive it from the Hermes agent
Load the `hermes-flywheel` skill (in `skills/creative/`). It maps each flywheel
stage to the MCP tools above so any MCP-capable client — Hermes, Claude, Cursor,
etc. — can run the autonomous loop and watch it on the Backlot board.

## Watch it live
Start Backlot (`python -m backlot`) and open the board for `projects/<name>/`.
The flywheel panel shows generations, best fitness per generation, and the
evolving population — a true dynamic content engine dashboard.

## Note on the environment
OpenMontage requires Python ≥3.10. The clean venv here is `.venv_clean`
(built with `PYTHONPATH` unset to avoid inheriting the hermes-agent 3.11
site-packages). The default `python3` on this machine is 3.9.6.
