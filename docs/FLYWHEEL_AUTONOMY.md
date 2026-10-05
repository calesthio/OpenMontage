# Running the Flywheel Autonomously

The creative loop (`Script → Render → Score → Breed`) is autonomous by design.
This document covers the **ops wrapper** — `scripts/flywheel_run.py` — that
executes, monitors, and self-heals the loop, and how to trigger it on a schedule
so the whole thing runs with no manual intervention.

## Executor
```bash
# from repo root, with the clean venv
env -u PYTHONPATH ./.venv_clean/bin/python scripts/flywheel_run.py \
    --project my-campaign --generations 6 --population-size 4 --budget 5.00
```
Flags: `--generations`, `--population-size`, `--budget`, `--mutation-rate`,
`--elite-fraction`, `--exploration`, `--convergence-threshold`, `--base-pipeline`,
`--seed`, `--no-watch`. The script writes live checkpoints + a `flywheel/` panel
Backlot can render, persists the population, and emits `run_summary.json`.

It is **deterministic and offline**: renders are dry-run payloads scored by
`breed_scorer`; swap in the real `render-director` skill output for live media.

## Monitor / self-heal
- `monitor(project_dir, cfg)` → `{"status": "ok"|"degraded", "best", "failed_count", "converged"}`.
- `self_heal(...)` retries the last generation (max 2x) on hard failure.
- Exit code is non-zero on unrecoverable failure — safe for CI gates.

## Schedule it (no manual intervention)
Pick ONE trigger; all call the same script:

### A. Hermes cron (recommended for this environment)
Create a cron job pointing at the command above. It runs in a fresh session and
the agent can be notified on completion. Example cadence: `0 9 * * *` (daily).

### B. macOS launchd (local daemon)
```xml
<!-- ~/Library/LaunchAgents/com.openmontage.flywheel.plist -->
<key>ProgramArguments</key>
<array>
  <string>bash</string><string>-c</string>
  <string>cd /Users/hyder/Documents/GitHub/OpenMontage && env -u PYTHONPATH ./.venv_clean/bin/python scripts/flywheel_run.py --project daily --generations 6</string>
</array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer></dict>
```

### C. GitHub Action (CI)
```yaml
# .github/workflows/flywheel.yml
on: { schedule: [{ cron: "0 9 * * *" }] }
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -r requirements.txt && pip install "mcp>=1.0"
      - run: python scripts/flywheel_run.py --project ci-run --generations 1 --no-watch
```

## Git commit / push — SAFE, OPT-IN ONLY
The script supports `--commit` and `--push`, but:
- **Push is gated behind `--branch`** (explicit; never auto-derived) and is
  **off by default**. It never force-pushes.
- Do NOT auto-publish to a remote without explicit confirmation. For scheduled
  runs, prefer committing artifacts locally and reviewing before pushing.

## What is "fully autonomous" here
- The loop runs itself (no human in the loop by default — checkpoint gates are
  opt-in via `human_approval_default`).
- Monitoring + bounded self-heal recover from transient failures.
- Scheduling triggers it without manual starts.
- Git publishing is the **one** step kept behind an explicit opt-in, because
  pushing to a shared remote is a side-effecting action that should not happen
  silently.
