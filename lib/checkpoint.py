"""Checkpoint writer/reader for pipeline state persistence.

Each stage writes a checkpoint after completion. The orchestrator uses
checkpoints to resume pipelines and to present state at human checkpoints.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import jsonschema

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact

# All known stages across all pipelines (used only for artifact name lookup).
ALL_KNOWN_STAGES = frozenset([
    "research", "proposal", "idea", "script", "scene_plan",
    "assets", "edit", "compose", "publish",
])

# Backward-compatible alias — existing code / tests that import STAGES still work.
# New code should use get_pipeline_stages(pipeline_type) instead.
STAGES = ["research", "proposal", "idea", "script", "scene_plan",
          "assets", "edit", "compose", "publish"]

CANONICAL_STAGE_ARTIFACTS = {
    "research": "research_brief",
    "proposal": "proposal_packet",
    "idea": "brief",
    "script": "script",
    "scene_plan": "scene_plan",
    "assets": "asset_manifest",
    "edit": "edit_decisions",
    "compose": "render_report",
    "publish": "publish_log",
}

# Additional artifacts that may be produced alongside canonical ones.
# These are not stage-defining but are required by governance contracts.
SUPPLEMENTARY_ARTIFACTS = {
    "source_media_review",  # Required before first planning stage when user media exists
    "final_review",         # Required by compose stage before presenting to user
    "video_analysis_brief", # Reference-video grounding artifact carried alongside stages
}


def get_pipeline_stages(pipeline_type: str | None) -> list[str]:
    """Return the ordered stage list for a specific pipeline.

    Falls back to STAGES (deterministic canonical order) when pipeline_type
    is not provided or the manifest cannot be loaded.

    Previous versions used a set intersection here, which produced
    nondeterministic ordering. The fallback now uses a stable list.
    """
    if pipeline_type is None:
        # Deterministic canonical fallback — sorted to ensure stable ordering
        import logging
        logging.getLogger(__name__).warning(
            "get_pipeline_stages called without pipeline_type — "
            "using canonical fallback order. Pass pipeline_type for correctness."
        )
        return list(STAGES)

    try:
        from lib.pipeline_loader import load_pipeline_readonly, get_stage_order
        manifest = load_pipeline_readonly(pipeline_type)
        return get_stage_order(manifest)
    except (FileNotFoundError, Exception):
        # Graceful fallback: return all known stages in canonical order
        return list(STAGES)

CHECKPOINT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "checkpoints"
    / "checkpoint.schema.json"
)

# Canonical project root. Checkpoints, artifacts, and the project marker all
# live under PROJECTS_DIR/<project_id>/ — this is the location the Backlot
# board watches. Callers may still pass a different pipeline_dir (tests do),
# but production runs should use the default.
from lib.paths import PROJECTS_DIR  # noqa: E402  (single source of truth)

PROJECT_MARKER_FILENAME = "project.json"
HISTORY_DIRNAME = "history"


class CheckpointValidationError(ValueError):
    """Raised when a checkpoint or its canonical artifacts are invalid."""


@lru_cache(maxsize=1)
def _load_checkpoint_schema() -> dict[str, Any]:
    with open(CHECKPOINT_SCHEMA_PATH) as f:
        return json.load(f)


def _validate_artifacts_for_stage(
    stage: str,
    status: str,
    artifacts: dict[str, Any],
) -> None:
    # Valid stages come from the pipeline manifest (get_pipeline_stages), which
    # can declare stages beyond the 9 canonical ones (e.g. character-animation's
    # `character_design`/`rig_plan`, screen-demo's `real_capture`). Those have no
    # canonical artifact, so look it up defensively — a missing entry means the
    # stage simply has no required artifact, not a crash.
    required_artifact = CANONICAL_STAGE_ARTIFACTS.get(stage)
    if (
        required_artifact is not None
        and status in {"completed", "awaiting_human"}
        and required_artifact not in artifacts
    ):
        raise CheckpointValidationError(
            f"Stage {stage!r} with status {status!r} must include "
            f"canonical artifact {required_artifact!r}"
        )

    for artifact_name, artifact_data in artifacts.items():
        if artifact_name not in ARTIFACT_NAMES:
            continue
        if not isinstance(artifact_data, dict):
            raise CheckpointValidationError(
                f"Artifact {artifact_name!r} must be a JSON object matching its schema"
            )
        try:
            validate_artifact(artifact_name, artifact_data)
        except Exception as exc:
            raise CheckpointValidationError(
                f"Artifact {artifact_name!r} failed schema validation: {exc}"
            ) from exc


def validate_checkpoint(checkpoint: dict[str, Any]) -> None:
    """Validate checkpoint structure and canonical artifact payloads.

    Uses pipeline_type (if present) to resolve the valid stage list.
    Falls back to ALL_KNOWN_STAGES when pipeline_type is absent.
    """
    stage = checkpoint.get("stage")
    status = checkpoint.get("status")
    artifacts = checkpoint.get("artifacts")
    pipeline_type = checkpoint.get("pipeline_type")

    valid_stages = (
        set(get_pipeline_stages(pipeline_type)) if pipeline_type
        else ALL_KNOWN_STAGES
    )

    if not isinstance(stage, str) or stage not in valid_stages:
        raise CheckpointValidationError(
            f"Invalid stage: {stage!r} for pipeline {pipeline_type!r}. "
            f"Valid stages: {sorted(valid_stages)}"
        )
    if not isinstance(status, str):
        raise CheckpointValidationError(f"Invalid status: {status!r}")
    if not isinstance(artifacts, dict):
        raise CheckpointValidationError("Checkpoint artifacts must be a dictionary")

    _validate_artifacts_for_stage(stage, status, artifacts)

    try:
        jsonschema.validate(instance=checkpoint, schema=_load_checkpoint_schema())
    except jsonschema.ValidationError as exc:
        raise CheckpointValidationError(f"Checkpoint failed schema validation: {exc.message}") from exc


def _checkpoint_path(pipeline_dir: Path, project_id: str, stage: str) -> Path:
    return pipeline_dir / project_id / f"checkpoint_{stage}.json"


def _resolve_approval_profile(
    manifest: dict[str, Any],
    pipeline_type: str,
    approval_profile: str,
) -> dict[str, Any]:
    profiles = manifest.get("approval_profiles", {})
    profile = profiles.get(approval_profile) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        available = sorted(profiles) if isinstance(profiles, dict) else []
        raise CheckpointValidationError(
            f"Unknown approval_profile {approval_profile!r} for pipeline "
            f"{pipeline_type!r}; available profiles: {available}"
        )

    # A typo'd stage name in a profile would be silently ignored downstream
    # and drop the gate the profile intended — fail closed instead.
    declared = {
        stage.get("name")
        for stage in manifest.get("stages", [])
        if isinstance(stage, dict)
    }
    overrides = profile.get("stage_overrides", {})
    rerun = profile.get("post_approval_rerun", [])
    unknown = sorted(
        {key for key in overrides if key not in declared}
        | {key for key in rerun if key not in declared}
    )
    if unknown:
        raise CheckpointValidationError(
            f"approval_profile {approval_profile!r} in pipeline {pipeline_type!r} "
            f"references unknown stages: {unknown}. Declared stages: "
            f"{sorted(s for s in declared if s)}"
        )
    return profile


def init_project(
    project_id: str,
    *,
    title: str,
    pipeline_type: str,
    pipeline_dir: Optional[Path] = None,
    style_playbook: Optional[str] = None,
    approval_profile: Optional[str] = None,
) -> Path:
    """Initialize a project workspace with the canonical layout + marker file.

    Creates projects/<project_id>/ with the standard subdirectories and writes
    project.json — the marker the Backlot board uses to render a project's
    identity and stage rail before the first checkpoint exists.

    Idempotent: re-running preserves the original created_at and merges fields.
    Returns the project directory.
    """
    if approval_profile is not None:
        try:
            from lib.pipeline_loader import load_pipeline_readonly
            manifest = load_pipeline_readonly(pipeline_type)
        except Exception as exc:
            raise CheckpointValidationError(
                f"Cannot validate approval_profile for pipeline {pipeline_type!r}"
            ) from exc
        _resolve_approval_profile(manifest, pipeline_type, approval_profile)

    base = pipeline_dir or PROJECTS_DIR
    project_dir = base / project_id
    for sub in (
        "artifacts",
        "assets/images",
        "assets/video",
        "assets/audio",
        "assets/music",
        "renders",
    ):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)

    marker_path = project_dir / PROJECT_MARKER_FILENAME
    marker: dict[str, Any] = {}
    if marker_path.exists():
        try:
            with open(marker_path) as f:
                marker = json.load(f)
        except (json.JSONDecodeError, OSError):
            marker = {}

    marker.setdefault("version", "1.0")
    marker.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    marker["project_id"] = project_id
    marker["title"] = title
    marker["pipeline_type"] = pipeline_type
    if style_playbook is not None:
        marker["style_playbook"] = style_playbook
    if approval_profile is not None:
        marker["approval_profile"] = approval_profile

    with open(marker_path, "w") as f:
        json.dump(marker, f, indent=2)

    return project_dir


def _stage_requires_approval(
    pipeline_type: Optional[str],
    stage: str,
    approval_profile: Optional[str] = None,
) -> Optional[bool]:
    """Read human_approval_default for a stage from its pipeline manifest.

    Returns None when the stage isn't declared in the manifest or no
    pipeline_type was given — the caller then falls back to the value the
    agent passed in.

    A *provided but unknown* pipeline_type raises: a typo must not silently
    disable gate enforcement (fail-closed, not fail-open). Other manifest
    load failures are logged and fall back — a corrupt manifest shouldn't
    strand an otherwise-valid run, but the degradation must be visible.
    """
    if not pipeline_type or pipeline_type == "unknown":
        return None
    from lib.pipeline_loader import get_stage_human_approval_default, load_pipeline_readonly
    try:
        manifest = load_pipeline_readonly(pipeline_type)
    except FileNotFoundError:
        raise CheckpointValidationError(
            f"Unknown pipeline_type {pipeline_type!r} — cannot resolve gate "
            f"policy for stage {stage!r}. Check the spelling against "
            f"pipeline_defs/*.yaml."
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Gate policy unavailable for pipeline %r (%s) — falling back to "
            "the caller's human_approval_required flag.", pipeline_type, exc,
        )
        return None
    default = get_stage_human_approval_default(manifest, stage)
    if not approval_profile:
        return default

    profile = _resolve_approval_profile(manifest, pipeline_type, approval_profile)
    overrides = profile.get("stage_overrides", {})
    if stage not in overrides:
        return default
    return bool(overrides[stage])


def checkpoint_resume_token(checkpoint: dict[str, Any]) -> str:
    """Bind a resume request to one exact awaiting-human checkpoint."""
    payload = json.dumps(
        checkpoint,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _archive_superseded_checkpoint(path: Path, stage: str) -> None:
    """Copy an existing checkpoint into history/ before it is overwritten.

    Preserves the full run record: stage re-runs (script v1 → v2) and gate
    transitions (awaiting_human → completed) remain reconstructable. Repeated
    in_progress refreshes are NOT archived — they are partial-progress
    heartbeats, not versions.

    Archiving is best-effort and must never crash a checkpoint write: the
    Backlot watcher may hold the file open (Windows denies renames of open
    files), so we copy rather than move, and swallow archival I/O failures.
    """
    if not path.exists():
        return
    try:
        with open(path) as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError):
        existing = {}
    if existing.get("status") == "in_progress":
        return

    try:
        import shutil
        stamp = str(existing.get("timestamp", ""))
        safe_stamp = "".join(c for c in stamp if c.isalnum()) or f"{path.stat().st_mtime_ns}"
        history_dir = path.parent / HISTORY_DIRNAME
        history_dir.mkdir(parents=True, exist_ok=True)
        target = history_dir / f"checkpoint_{stage}_{safe_stamp}.json"
        if target.exists():
            target = history_dir / f"checkpoint_{stage}_{safe_stamp}_{path.stat().st_mtime_ns}.json"
        shutil.copyfile(path, target)
    except OSError:
        import logging
        logging.getLogger(__name__).warning(
            "Could not archive superseded checkpoint %s to history/", path
        )


def _decision_log_path(pipeline_dir: Path, project_id: str) -> Path:
    return pipeline_dir / project_id / "decision_log.json"


def _merge_decision_log(
    pipeline_dir: Path, project_id: str, new_log: dict[str, Any]
) -> None:
    """Append new decisions to the project-level decision log.

    Each stage may produce decisions. This function merges them into a
    single cumulative file so reviewers and the bench can inspect the
    full audit trail.
    """
    path = _decision_log_path(pipeline_dir, project_id)
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    else:
        existing = {
            "version": "1.0",
            "project_id": project_id,
            "decisions": [],
        }

    existing_ids = {d["decision_id"] for d in existing.get("decisions", [])}
    for decision in new_log.get("decisions", []):
        if decision.get("decision_id") not in existing_ids:
            existing["decisions"].append(decision)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def write_checkpoint(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    status: str,
    artifacts: dict[str, Any],
    *,
    pipeline_type: Optional[str] = None,
    style_playbook: Optional[str] = None,
    checkpoint_policy: str = "guided",
    human_approval_required: bool = False,
    human_approved: bool = False,
    review: Optional[dict] = None,
    cost_snapshot: Optional[dict] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
    approval_profile: Optional[str] = None,
) -> Path:
    """Write a checkpoint file for a pipeline stage."""
    # Backfill a missing pipeline_type from the project marker so that
    # omitting the kwarg doesn't quietly bypass gate enforcement.
    marker = None
    marker_path = pipeline_dir / project_id / PROJECT_MARKER_FILENAME
    if marker_path.exists():
        try:
            with open(marker_path) as f:
                marker = json.load(f)
        except (json.JSONDecodeError, OSError):
            marker = None
    if not pipeline_type and isinstance(marker, dict) and marker.get("pipeline_type"):
        pipeline_type = marker["pipeline_type"]
    # The persisted project selection is authoritative for approval profiles.
    # Accepting a per-call profile the project never selected would let any
    # stage caller opt itself out of the project's default gates.
    marker_profile = marker.get("approval_profile") if isinstance(marker, dict) else None
    if not (isinstance(marker_profile, str) and marker_profile):
        marker_profile = None
    if approval_profile:
        if approval_profile != marker_profile:
            raise CheckpointValidationError(
                f"approval_profile {approval_profile!r} was passed for project "
                f"{project_id!r} but {PROJECT_MARKER_FILENAME} records "
                f"{marker_profile!r}. Profiles are selected once at "
                f"init_project(); write_checkpoint cannot override the "
                f"persisted selection."
            )
    else:
        approval_profile = marker_profile

    valid_stages = (
        set(get_pipeline_stages(pipeline_type)) if pipeline_type
        else ALL_KNOWN_STAGES
    )
    if stage not in valid_stages:
        raise ValueError(
            f"Invalid stage: {stage!r} for pipeline {pipeline_type!r}. "
            f"Valid stages: {sorted(valid_stages)}"
        )

    # --- Gate enforcement (GI-4) ---
    # The pipeline manifest is the binding source of truth for whether a stage
    # gates on human approval. Without a selected profile, a caller may gate
    # more strictly (e.g. a manual_all checkpoint policy) but never less. An
    # explicit manifest-defined profile is itself the complete policy: its
    # false overrides must not be re-gated by stale unprofiled director input.
    # A gated stage can only be written "completed" with explicit approval
    # (human_approved=True). Skipping a gate is a hard error.
    #
    # Enforcement happens at write time only: pre-existing checkpoints written
    # before gating (or by hand) still read as completed — deliberate
    # back-compat so in-flight and legacy projects keep resuming.
    manifest_gate = _stage_requires_approval(
        pipeline_type,
        stage,
        approval_profile=approval_profile,
    )
    profile_policy_is_binding = approval_profile is not None and manifest_gate is not None
    if profile_policy_is_binding:
        gated = bool(manifest_gate)
        human_approval_required = gated
    else:
        gated = bool(manifest_gate) or human_approval_required
    if gated:
        human_approval_required = True
        if status == "completed" and not human_approved:
            gate_source = (
                f"human_approval_default: true in the {pipeline_type!r} manifest"
                if manifest_gate
                else "human_approval_required=True was passed by the caller"
            )
            raise CheckpointValidationError(
                f"GATE VIOLATION: stage {stage!r} requires human approval "
                f"({gate_source}) but status='completed' was written without "
                f"human_approved=True. Correct protocol: write "
                f"status='awaiting_human', present the artifact summary to the "
                f"user, END YOUR TURN, and only after the user approves "
                f"re-write with status='completed', human_approved=True."
            )

    checkpoint = {
        "version": "1.0",
        "project_id": project_id,
        "pipeline_type": pipeline_type or "unknown",
        "stage": stage,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checkpoint_policy": checkpoint_policy,
        "human_approval_required": human_approval_required,
        "human_approved": human_approved,
        "artifacts": artifacts,
    }
    if style_playbook is not None:
        checkpoint["style_playbook"] = style_playbook
    if approval_profile is not None:
        checkpoint["approval_profile"] = approval_profile
    if review is not None:
        checkpoint["review"] = review
    if cost_snapshot is not None:
        checkpoint["cost_snapshot"] = cost_snapshot
    if error is not None:
        checkpoint["error"] = error
    if metadata is not None:
        checkpoint["metadata"] = metadata

    # Merge decision_log: if this checkpoint carries new decisions,
    # append them to the project-level decision log file, then write the
    # reference back into relevant artifacts so downstream consumers can find it.
    if "decision_log" in artifacts and isinstance(artifacts["decision_log"], dict):
        _merge_decision_log(pipeline_dir, project_id, artifacts["decision_log"])
        log_ref = str(_decision_log_path(pipeline_dir, project_id))

        # Write decision_log_ref into proposal_packet and render_report
        # artifacts if they are present in this checkpoint.
        for artifact_key in ("proposal_packet", "render_report"):
            if artifact_key in artifacts and isinstance(artifacts[artifact_key], dict):
                plan_or_top = artifacts[artifact_key]
                # proposal_packet stores it under production_plan
                if artifact_key == "proposal_packet":
                    plan = plan_or_top.get("production_plan")
                    if isinstance(plan, dict):
                        plan["decision_log_ref"] = log_ref
                else:
                    plan_or_top["decision_log_ref"] = log_ref

    validate_checkpoint(checkpoint)

    path = _checkpoint_path(pipeline_dir, project_id, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize to a temp file first so a mid-write failure (disk full,
    # unserializable metadata) can never leave the stage with a truncated
    # current checkpoint; then archive the superseded file and swap in the
    # new one atomically.
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(checkpoint, f, indent=2)
    # Preserve run history: a superseded completed/awaiting_human checkpoint
    # is copied to history/ (stage versioning, gate audit trail, replay).
    _archive_superseded_checkpoint(path, stage)
    import os
    os.replace(tmp_path, path)

    return path


def record_checkpoint_approval(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    *,
    expected_resume_token: str,
    approval_evidence: dict[str, Any],
) -> Path:
    """Record approval without pretending the gated work already completed.

    The checkpoint remains ``awaiting_human``.  A paid stage can now verify the
    approval evidence, run, and only then replace it with ``completed``.  The
    resume token prevents a reply to an old preview from authorizing a newer
    revision.
    """
    checkpoint = read_checkpoint(pipeline_dir, project_id, stage)
    if checkpoint is None or checkpoint.get("status") != "awaiting_human":
        raise CheckpointValidationError(
            f"Stage {stage!r} has no awaiting_human checkpoint to approve"
        )

    actual_token = checkpoint_resume_token(checkpoint)
    if expected_resume_token != actual_token:
        raise CheckpointValidationError(
            "Stale or invalid checkpoint resume token; request a fresh preview"
        )
    if not isinstance(approval_evidence, dict) or not approval_evidence:
        raise CheckpointValidationError("approval_evidence must be a non-empty object")
    required_evidence = ("decision", "source_message_id", "timestamp")
    missing = [
        key for key in required_evidence
        if not isinstance(approval_evidence.get(key), str)
        or not approval_evidence[key].strip()
    ]
    if missing:
        raise CheckpointValidationError(
            "approval_evidence requires non-empty decision, source_message_id "
            f"and timestamp; missing: {', '.join(missing)}"
        )
    try:
        approval_time = datetime.fromisoformat(
            approval_evidence["timestamp"].replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CheckpointValidationError(
            "approval_evidence timestamp must be ISO-8601"
        ) from exc
    if approval_time.tzinfo is None:
        raise CheckpointValidationError(
            "approval_evidence timestamp must include a timezone"
        )

    metadata = dict(checkpoint.get("metadata") or {})
    metadata["approval_evidence"] = approval_evidence
    metadata["approved_resume_token"] = actual_token
    approved_path = write_checkpoint(
        pipeline_dir,
        project_id,
        stage,
        "awaiting_human",
        checkpoint["artifacts"],
        pipeline_type=checkpoint.get("pipeline_type"),
        style_playbook=checkpoint.get("style_playbook"),
        checkpoint_policy=checkpoint.get("checkpoint_policy", "guided"),
        human_approval_required=True,
        human_approved=True,
        review=checkpoint.get("review"),
        cost_snapshot=checkpoint.get("cost_snapshot"),
        metadata=metadata,
        approval_profile=checkpoint.get("approval_profile"),
    )
    _supersede_post_approval_rerun_checkpoints(
        pipeline_dir,
        project_id,
        approved_stage=stage,
        pipeline_type=checkpoint.get("pipeline_type"),
        approval_profile=checkpoint.get("approval_profile"),
    )
    return approved_path


def _supersede_post_approval_rerun_checkpoints(
    pipeline_dir: Path,
    project_id: str,
    *,
    approved_stage: str,
    pipeline_type: Optional[str],
    approval_profile: Optional[str],
) -> list[str]:
    """Route the deterministic resume loop into the profile's paid re-run.

    A profile such as ``preview_then_avatar`` completes cheap placeholder
    passes of ``assets``/``edit`` before the gated ``compose`` preview. Once
    the human approves that preview, those placeholder checkpoints must stop
    counting as done — otherwise ``get_next_stage`` resumes at the approved
    stage and re-renders the placeholder instead of running the paid pass.
    Each superseded checkpoint is archived to ``history/`` first, then removed,
    so the same governed runner re-executes the stages listed in the profile's
    ``post_approval_rerun``. The approved awaiting checkpoint itself is kept:
    it carries the resume token the paid adapter verifies before spend.
    """
    if not approval_profile or not pipeline_type or pipeline_type == "unknown":
        return []
    from lib.pipeline_loader import load_pipeline_readonly
    try:
        manifest = load_pipeline_readonly(pipeline_type)
    except Exception as exc:
        raise CheckpointValidationError(
            f"Cannot resolve approval_profile {approval_profile!r} for the "
            f"post-approval transition of pipeline {pipeline_type!r}"
        ) from exc
    profile = _resolve_approval_profile(manifest, pipeline_type, approval_profile)
    superseded: list[str] = []
    for prior_stage in profile.get("post_approval_rerun", []):
        if prior_stage == approved_stage:
            continue
        path = _checkpoint_path(pipeline_dir, project_id, prior_stage)
        if not path.exists():
            continue
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if existing.get("status") != "completed":
            continue
        _archive_superseded_checkpoint(path, prior_stage)
        path.unlink()
        superseded.append(prior_stage)
    return superseded


def assert_checkpoint_approved_for_resume(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    *,
    expected_resume_token: str,
    expected_decision: str,
) -> dict[str, Any]:
    """Verify the recorded decision immediately before a gated operation.

    This is deliberately separate from ``record_checkpoint_approval`` so a
    caller cannot treat a successful write as authorization forever.  Paid
    adapters should call it at the last possible moment before provider spend.
    It is tamper-evident state, not a security boundary against a process that
    can rewrite the whole workspace.
    """
    checkpoint = read_checkpoint(pipeline_dir, project_id, stage)
    if checkpoint is None or checkpoint.get("status") != "awaiting_human":
        raise CheckpointValidationError(
            f"Stage {stage!r} is not awaiting an approved resume"
        )
    if checkpoint.get("human_approved") is not True:
        raise CheckpointValidationError(
            f"Stage {stage!r} has no recorded human approval"
        )
    metadata = checkpoint.get("metadata") or {}
    if metadata.get("approved_resume_token") != expected_resume_token:
        raise CheckpointValidationError(
            "Approved resume token does not match the requested checkpoint"
        )
    evidence = metadata.get("approval_evidence")
    if not isinstance(evidence, dict):
        raise CheckpointValidationError("Approved checkpoint has no approval_evidence")
    required_evidence = ("decision", "source_message_id", "timestamp")
    if any(not isinstance(evidence.get(key), str) or not evidence[key].strip()
           for key in required_evidence):
        raise CheckpointValidationError(
            "Approved checkpoint evidence is incomplete"
        )
    if evidence["decision"] != expected_decision:
        raise CheckpointValidationError(
            f"Approved decision {evidence['decision']!r} does not match "
            f"required decision {expected_decision!r}"
        )
    try:
        approval_time = datetime.fromisoformat(evidence["timestamp"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckpointValidationError("Approved timestamp is not ISO-8601") from exc
    if approval_time.tzinfo is None:
        raise CheckpointValidationError("Approved timestamp has no timezone")

    original_found = False
    history_dir = pipeline_dir / project_id / HISTORY_DIRNAME
    for path in history_dir.glob(f"checkpoint_{stage}_*.json"):
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            original.get("status") == "awaiting_human"
            and original.get("human_approved") is not True
            and checkpoint_resume_token(original) == expected_resume_token
        ):
            original_found = True
            break
    if not original_found:
        raise CheckpointValidationError(
            "Approved resume token is not bound to an original awaiting checkpoint"
        )
    return dict(evidence)


def read_checkpoint(
    pipeline_dir: Path, project_id: str, stage: str
) -> Optional[dict[str, Any]]:
    """Read a checkpoint file. Returns None if not found."""
    path = _checkpoint_path(pipeline_dir, project_id, stage)
    if not path.exists():
        return None
    with open(path) as f:
        checkpoint = json.load(f)
    validate_checkpoint(checkpoint)
    return checkpoint


def get_latest_checkpoint(
    pipeline_dir: Path, project_id: str
) -> Optional[dict[str, Any]]:
    """Find the most recent checkpoint for a project (by file mtime)."""
    project_dir = pipeline_dir / project_id
    if not project_dir.exists():
        return None

    checkpoints = sorted(
        project_dir.glob("checkpoint_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not checkpoints:
        return None

    with open(checkpoints[0]) as f:
        checkpoint = json.load(f)
    validate_checkpoint(checkpoint)
    return checkpoint


def get_completed_stages(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> list[str]:
    """Return list of stages that have a completed checkpoint.

    When pipeline_type is provided, only checks stages defined in that
    pipeline's manifest — preventing false positives from leftover
    checkpoints of a different pipeline type.
    """
    stages_to_check = get_pipeline_stages(pipeline_type)
    completed = []
    for stage in stages_to_check:
        cp = read_checkpoint(pipeline_dir, project_id, stage)
        if cp and cp.get("status") == "completed":
            completed.append(stage)
    return completed


def get_next_stage(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> Optional[str]:
    """Determine the next stage to run based on completed checkpoints.

    Uses pipeline-specific stage order so that pipelines with different
    stage sequences (e.g. cinematic vs explainer) progress correctly.
    """
    stages = get_pipeline_stages(pipeline_type) if pipeline_type else STAGES
    completed = set(get_completed_stages(pipeline_dir, project_id, pipeline_type))
    for stage in stages:
        if stage not in completed:
            return stage
    return None
