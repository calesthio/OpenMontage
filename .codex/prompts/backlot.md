# /backlot — open the living storyboard

Open the Backlot board (browser UI showing pipeline stages, script, scene plan, and generated assets live) for the requested project:

```bash
python -m backlot open <project-id>
```

- No project id → open the library view: `python -m backlot open`
- Idempotent: starts the Backlot server if needed, then opens the browser at the project's board.
- If it fails, report and continue — the board is an observer, never a blocker.
- The board derives all state from `projects/<id>/` on disk; never update the UI manually. Keep checkpoints and artifacts honest per `skills/meta/checkpoint-protocol.md`.
