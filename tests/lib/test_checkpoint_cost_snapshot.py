"""A malformed `cost_snapshot` must fail the write, not render as $0.00.

`CostTracker.cost_snapshot()` returns `total_spent_usd` / `total_reserved_usd`
/ `budget_remaining_usd`, and `backlot/ui/board.js` reads exactly those keys.
The checkpoint schema listed them without `additionalProperties: false`, so an
agent hand-writing `{"spent_usd": 0.60}` produced a checkpoint that validated
and left the board's cost meter reading $0.00 with no bar. The spend was on
disk and invisible.
"""

import pytest

from lib.checkpoint import CheckpointValidationError, init_project, write_checkpoint


def _project(tmp_path):
    init_project("cost-probe", title="Cost Probe", pipeline_type="cinematic", pipeline_dir=tmp_path)
    return tmp_path


def test_unknown_cost_keys_are_rejected(tmp_path) -> None:
    root = _project(tmp_path)
    with pytest.raises(CheckpointValidationError):
        write_checkpoint(
            root, "cost-probe", "research", "in_progress", {},
            pipeline_type="cinematic",
            cost_snapshot={"spent_usd": 0.60, "budget_usd": 0.60},
        )


def test_snapshot_without_total_spent_is_rejected(tmp_path) -> None:
    root = _project(tmp_path)
    with pytest.raises(CheckpointValidationError):
        write_checkpoint(
            root, "cost-probe", "research", "in_progress", {},
            pipeline_type="cinematic",
            cost_snapshot={"budget_remaining_usd": 1.40},
        )


def test_cost_tracker_shape_is_accepted(tmp_path) -> None:
    root = _project(tmp_path)
    path = write_checkpoint(
        root, "cost-probe", "research", "in_progress", {},
        pipeline_type="cinematic",
        cost_snapshot={
            "total_spent_usd": 0.60,
            "total_reserved_usd": 0.0,
            "budget_remaining_usd": 1.40,
        },
    )
    assert path.exists()
