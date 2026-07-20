---
description: Open the Backlot living storyboard — the browser board that shows pipeline stages, script, scene plan, and generated assets live as a production runs.
argument-hint: [project-id (optional — defaults to the current/most recent project)]
---

Open the Backlot board for the requested project:

```bash
python -m backlot open $ARGUMENTS
```

- No argument → open the library view (all projects): `python -m backlot open`
- The command is idempotent: it starts the Backlot server if it isn't running, then opens the browser at the project's board.
- If the command fails, report it and continue with whatever the user asked — the board is an observer, never a blocker.
- The board derives everything from disk (`projects/<id>/` checkpoints, artifacts, assets, events). You never update the UI manually; keep checkpoints and artifacts honest per `skills/meta/checkpoint-protocol.md` and the board stays honest too.
