"""Contract tests for the autonomous flywheel runner (scripts/flywheel_run.py).

Deterministic, offline: drives 2 generations and checks the loop converges
toward higher fitness, persists a population, and the monitor reports OK.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
import sys

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.flywheel_run import RunConfig, run, monitor  # noqa: E402
from lib.paths import PROJECTS_DIR  # noqa: E402


@pytest.fixture()
def cfg():
    return RunConfig(
        project="flywheel_test_run", generations=2, population_size=4,
        budget=5.0, mutation_rate=0.6, elite_fraction=0.5, exploration=0.2,
        convergence_threshold=0.02, base_pipeline="animated-explainer",
        no_watch=True, seed=7,
    )


def test_run_produces_improving_population(cfg):
    summary = run(cfg)
    assert summary["best_score"] > 0.0
    assert len(summary["history"]) == 2
    # later generation should not be worse than the first (breeding improves)
    assert summary["history"][1]["best"] >= summary["history"][0]["best"]
    # population persisted
    pop_path = PROJECTS_DIR / cfg.project / "flywheel" / "population.jsonl"
    assert pop_path.exists()
    lines = [l for l in pop_path.read_text().splitlines() if l.strip()]
    assert len(lines) == cfg.population_size * cfg.generations


def test_monitor_reports_ok(cfg):
    run(cfg)
    st = monitor(PROJECTS_DIR / cfg.project, cfg)
    assert st["status"] == "ok"
    assert st["failed_count"] == 0


def teardown_module():
    import shutil

    d = PROJECTS_DIR / "flywheel_test_run"
    if d.exists():
        shutil.rmtree(d)
