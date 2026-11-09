"""Smoke test for the Backlot demo driver against the real checkpoint contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_simulated_run_completes_from_a_fresh_project(tmp_path):
    projects_dir = tmp_path / "projects"
    project_id = "backlot-smoke"
    env = os.environ.copy()
    env["OPENMONTAGE_PROJECTS_DIR"] = str(projects_dir)

    result = subprocess.run(
        [sys.executable, "scripts/backlot_simulate_run.py", "--fast", "--project", project_id],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    project_dir = projects_dir / project_id
    proposal = json.loads((project_dir / "checkpoint_proposal.json").read_text())
    assert proposal["status"] == "completed"
    assert proposal["human_approved"] is True
    assert proposal["artifacts"]["proposal_packet"]["approval"]["status"] == "approved"
    proposal_history = list((project_dir / "history").glob("checkpoint_proposal_*.json"))
    assert any(
        json.loads(path.read_text())["status"] == "awaiting_human"
        for path in proposal_history
    )
    assert json.loads((project_dir / "checkpoint_assets.json").read_text())["status"] == "completed"
