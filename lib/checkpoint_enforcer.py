"""Checkpoint enforcement — validates that checkpoint_required stages actually wrote checkpoints.

The pipeline manifest declares `checkpoint_required: true` per stage, but
the existing checkpoint module is passive — it writes when called but never
verifies that a required checkpoint was actually created.

This module adds two functions:
  - verify_stage_checkpointed(): call after each stage — raises if required
    checkpoint is missing.
  - verify_pipeline_checkpoints(): batch check returning a report with
    passed / degraded / blocked verdict.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from lib.checkpoint import read_checkpoint, get_pipeline_stages
from lib.pipeline_loader import load_pipeline

log = logging.getLogger(__name__)


class CheckpointEnforcementError(RuntimeError):
    """Raised when a required checkpoint is missing or invalid."""


def _is_checkpoint_required(manifest: dict[str, Any], stage_name: str) -> bool:
    """Check if a stage declares checkpoint_required: true in the manifest."""
    for stage in manifest.get("stages", []):
        if stage.get("name") == stage_name:
            return bool(stage.get("checkpoint_required", False))
    return False


def verify_stage_checkpointed(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    pipeline_type: str,
) -> None:
    """Verify that a completed stage has a valid checkpoint if the manifest requires one.

    Raises CheckpointEnforcementError if checkpoint_required is True but no
    valid checkpoint file exists for this stage.
    """
    try:
        manifest = load_pipeline(pipeline_type)
    except FileNotFoundError:
        log.warning(
            "Cannot enforce checkpoint for stage %r — pipeline %r manifest not found",
            stage, pipeline_type,
        )
        return

    if not _is_checkpoint_required(manifest, stage):
        return  # Not required — nothing to enforce

    cp = read_checkpoint(pipeline_dir, project_id, stage)
    if cp is None:
        raise CheckpointEnforcementError(
            f"Stage {stage!r} in pipeline {pipeline_type!r} declares "
            f"checkpoint_required: true, but no checkpoint file was created. "
            f"The pipeline contract requires each stage to write a valid "
            f"checkpoint via write_checkpoint() before proceeding."
        )

    status = cp.get("status", "")
    if status not in ("completed", "awaiting_human", "in_progress"):
        raise CheckpointEnforcementError(
            f"Stage {stage!r} has a checkpoint but its status is {status!r}, "
            f"which does not indicate successful completion."
        )


def verify_pipeline_checkpoints(
    pipeline_dir: Path,
    project_id: str,
    pipeline_type: str,
    completed_stages: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Batch-verify all completed stages have the checkpoints the manifest requires.

    Args:
        pipeline_dir: Root directory for pipeline checkpoint files.
        project_id: Project identifier.
        pipeline_type: Pipeline manifest name (e.g. "animated-explainer").
        completed_stages: If provided, only check these stages. Otherwise
            checks all stages defined in the pipeline manifest.

    Returns:
        {
            "status": "passed" | "degraded" | "blocked",
            "missing_required": [{"stage": str, "checkpoint_required": True}],
            "present": [str],
            "total_required": int,
            "total_present": int,
        }
    """
    try:
        manifest = load_pipeline(pipeline_type)
    except FileNotFoundError:
        return {
            "status": "blocked",
            "error": f"Pipeline manifest {pipeline_type!r} not found",
            "missing_required": [],
            "present": [],
            "total_required": 0,
            "total_present": 0,
        }

    stages_to_check = completed_stages or get_pipeline_stages(pipeline_type)
    missing_required: list[dict[str, Any]] = []
    present: list[str] = []
    total_required = 0

    for stage in stages_to_check:
        required = _is_checkpoint_required(manifest, stage)
        if not required:
            continue

        total_required += 1
        cp = read_checkpoint(pipeline_dir, project_id, stage)

        if cp is not None and cp.get("status") in ("completed", "awaiting_human", "in_progress"):
            present.append(stage)
        else:
            missing_required.append({
                "stage": stage,
                "checkpoint_required": True,
                "checkpoint_found": cp is not None,
                "checkpoint_status": cp.get("status") if cp else None,
            })

    # Determine verdict
    if not missing_required:
        status = "passed"
    elif len(missing_required) == total_required:
        status = "blocked"
    else:
        status = "degraded"

    return {
        "status": status,
        "missing_required": missing_required,
        "present": present,
        "total_required": total_required,
        "total_present": len(present),
    }
