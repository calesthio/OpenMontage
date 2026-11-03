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

Backlot defaults to binding `127.0.0.1` and accepts HTTP requests only for
`127.0.0.1` or `localhost` (plus optional extra hosts below). Other `Host`
headers receive HTTP 400 to protect local project data from DNS rebinding.

Optional environment variables (defaults preserve local-only behavior):

| Variable | Default | Purpose |
|---|---|---|
| `BACKLOT_HOST` | `127.0.0.1` | Uvicorn bind address (e.g. `0.0.0.0` behind a reverse proxy) |
| `BACKLOT_LOG_LEVEL` | `warning` | Uvicorn log level |
| `BACKLOT_ALLOWED_HOSTS` | *(unset → loopback only)* | Comma-separated `Host` values allowed by `TrustedHostMiddleware` |
| `BACKLOT_PORT` | `4750` | Port when not passing `--port` |

When setting `BACKLOT_ALLOWED_HOSTS`, include every hostname clients use
(including `127.0.0.1` and `localhost` if you still open the board locally).

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

Design doc: `internal/design/LIVING_STORYBOARD.md`.
