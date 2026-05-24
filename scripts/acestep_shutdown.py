"""Stop the local ACE-Step API server and release its VRAM.

The `acestep_music` tool intentionally leaves the FastAPI server running
between calls so back-to-back jobs don't pay the cold-start cost (model
weights stay loaded). For one-shot runs that wastes ~12-18 GB of VRAM on
the active GPU indefinitely.

Run this when you're done with music generation for the session:

    python scripts/acestep_shutdown.py

It reads the PID captured at server launch (~/.cache/openmontage/acestep_server.pid),
stops only that process tree, and clears the PID file. Only PIDs we
recorded ourselves are touched — no broad image-name kills.

Exit codes:
  0  — server stopped successfully, or nothing to stop (idempotent)
  2  — one or more PIDs in the tree could not be stopped
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python scripts/acestep_shutdown.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.audio.acestep_music import stop_server_tree  # noqa: E402


def main() -> int:
    result = stop_server_tree()
    print(json.dumps(result, indent=2))

    if result["parent_pid"] is None and not result["pid_file_removed"]:
        # Nothing was tracked. Exit 0 — idempotent.
        return 0
    if result["survivors"]:
        print("WARN: some PIDs could not be stopped", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
