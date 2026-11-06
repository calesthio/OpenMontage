# Backlot — the living storyboard

A read-only local board that shows a production happening: pipeline stages
lighting up, the script as a screenplay page, the scene plan as a filmstrip
that fills in as assets generate, decisions, spend, and activity — all
derived from what the pipeline already writes to `projects/<id>/`.

```bash
python -m backlot open <project-id>   # start server if needed + open browser
python -m backlot open                # library view (all projects)
python -m backlot serve --port 4750   # run the server in the foreground
```

Backlot binds to `127.0.0.1` and accepts HTTP requests only for `127.0.0.1`
or `localhost`, on the selected port. Other `Host` headers receive HTTP 400
to protect local project data from DNS rebinding.

## How it stays live

No agent involvement. A `watchfiles` watcher on `projects/` publishes change
notifications over SSE; the browser refetches board state. State sources:

| Board element | Disk source |
|---|---|
| identity / rail order | `project.json` + `pipeline_defs/<type>.yaml` |
| stage states, gates, versions | `checkpoint_<stage>.json` + `history/` |
| script card / modal | `artifacts/script.json` |
| filmstrip cards | `scene_plan × script × asset_manifest` join |
| generating shimmer, activity | `events.jsonl` (written by `BaseTool` instrumentation) |
| cost meter | checkpoint `cost_snapshot` |
| renders | `renders/*.mp4` (+ root-level mp4 heuristic) |

Projects without checkpoints degrade gracefully to a "what the watcher
found" view — media, snapshots, renders.

**Replay**: a completed run can be scrubbed end-to-end (▶ REPLAY RUN on the
board) — reconstructed from checkpoint history and event timestamps.

Try it without a real production:

```bash
python scripts/backlot_simulate_run.py          # live demo run (~1 min)
python -m backlot open backlot-demo-run
```

## Series

Several projects can be episodes of one show. Add an optional `series` label
to each episode's `project.json` (or pass `series=` to
`lib.checkpoint.init_project`). Folders stay flat in `projects/`; nothing moves.

```json
{ "title": "Episode 3: The Heist", "pipeline_type": "animation", "series": "my-show" }
```

- The library shows one card per series next to the loose projects.
- `/?series=my-show` opens the series: the usual project grid, filtered, with
  links back to the library and to the series list (`/?view=series`).
- An episode's board links back to its series.

Projects without `series` (including older projects with no `project.json`)
show as loose cards, exactly as before.

Design doc: `internal/design/LIVING_STORYBOARD.md`.
