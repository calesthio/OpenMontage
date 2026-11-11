"""Checkpoint writer/reader for pipeline state persistence.

Each stage writes a checkpoint after completion. The orchestrator uses
checkpoints to resume pipelines and to present state at human checkpoints.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from datetime import datetime, timezone
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

    Three cases, deliberately different:

    * no pipeline (``None``, or the ``"unknown"`` placeholder a legacy
      checkpoint carries): the canonical STAGES order, with a warning.
    * a name with no manifest: ``UnknownPipelineError``. A misspelled pipeline
      used to get the canonical list back in silence, which names stages the
      real pipeline does not have (``idea`` for a research-first pipeline) and
      drops the ones it adds — so resume pointed at the wrong stage.
    * a manifest that exists but cannot be loaded: the canonical order, with a
      warning that names the manifest and the error (same policy as
      ``_stage_requires_approval`` — a corrupt manifest must not strand a run,
      but the degradation has to be visible).
    """
    if pipeline_type is None or pipeline_type == "unknown":
        logging.getLogger(__name__).warning(
            "get_pipeline_stages called without pipeline_type — "
            "using canonical fallback order. Pass pipeline_type for correctness."
        )
        return list(STAGES)

    from lib.pipeline_loader import get_stage_order, list_pipelines, load_pipeline_readonly

    try:
        manifest = load_pipeline_readonly(pipeline_type)
    except FileNotFoundError as exc:
        raise UnknownPipelineError(
            f"Unknown pipeline_type {pipeline_type!r}: there is no "
            f"pipeline_defs/{pipeline_type}.yaml. Known pipelines: "
            f"{sorted(list_pipelines())}."
        ) from exc
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Pipeline manifest %r could not be loaded (%s) — falling back to "
            "the canonical stage order. Fix pipeline_defs/%s.yaml.",
            pipeline_type, exc, pipeline_type,
        )
        return list(STAGES)
    return get_stage_order(manifest)

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


class UnknownPipelineError(CheckpointValidationError):
    """Raised when a pipeline_type names no manifest in pipeline_defs/."""


def _stage_primary_artifact(pipeline_type: Optional[str], stage: str) -> Optional[str]:
    """The artifact a stage must hand over, canonical or manifest-declared.

    The nine canonical stages have a fixed artifact. A stage a manifest adds
    (character-animation's ``character_design`` / ``rig_plan``) has none in
    that table, so its contract is the first entry of its ``produces`` list —
    manifests list the stage's own artifact first and side products after it.
    Returns None when the stage declares nothing or the manifest is not known.
    """
    canonical = CANONICAL_STAGE_ARTIFACTS.get(stage)
    if canonical is not None:
        return canonical
    if not pipeline_type or pipeline_type == "unknown":
        return None
    try:
        from lib.pipeline_loader import load_pipeline_readonly

        manifest = load_pipeline_readonly(pipeline_type)
    except Exception:
        return None
    for stage_def in manifest.get("stages", []):
        if stage_def.get("name") == stage:
            produces = stage_def.get("produces") or []
            return produces[0] if produces and isinstance(produces[0], str) else None
    return None


def _validate_style_playbook(style_playbook: str | None) -> None:
    """Fail closed when a checkpoint names a visual identity that cannot load."""

    if style_playbook is None:
        return
    try:
        from styles.playbook_loader import list_playbooks, load_playbook

        load_playbook(style_playbook)
    except Exception as exc:
        try:
            available = list_playbooks()
        except Exception:
            available = []
        raise CheckpointValidationError(
            f"Unknown or invalid style_playbook {style_playbook!r}. "
            f"Available playbooks: {available}. Underlying error: {exc}"
        ) from exc


@lru_cache(maxsize=1)
def _load_checkpoint_schema() -> dict[str, Any]:
    with open(CHECKPOINT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate_artifacts_for_stage(
    stage: str,
    status: str,
    artifacts: dict[str, Any],
    pipeline_type: Optional[str] = None,
) -> None:
    # Valid stages come from the pipeline manifest (get_pipeline_stages), which
    # can declare stages beyond the 9 canonical ones (e.g. character-animation's
    # `character_design`/`rig_plan`). Those are not in the canonical table, so
    # their required artifact comes from the manifest's `produces` instead — a
    # gated `character_design` could otherwise be presented for approval, and
    # approved, with nothing in it.
    required_artifact = _stage_primary_artifact(pipeline_type, stage)
    if (
        required_artifact is not None
        and status in {"completed", "awaiting_human"}
        and required_artifact not in artifacts
    ):
        kind = "canonical" if stage in CANONICAL_STAGE_ARTIFACTS else "manifest-declared"
        raise CheckpointValidationError(
            f"Stage {stage!r} with status {status!r} must include "
            f"{kind} artifact {required_artifact!r}"
        )

    # The proposal packet's schema keeps render_runtime optional while its
    # approval is pending, then requires it for approved packets. A proposal
    # checkpoint can only complete after the human approval gate, so keep the
    # checkpoint state and the embedded approval decision in sync as well.
    if stage == "proposal" and status == "completed":
        proposal = artifacts.get("proposal_packet")
        approval = proposal.get("approval") if isinstance(proposal, dict) else None
        approval_status = approval.get("status") if isinstance(approval, dict) else None
        if approval_status not in {"approved", "approved_with_changes"}:
            raise CheckpointValidationError(
                "A completed proposal checkpoint must include a proposal_packet "
                "with approval.status 'approved' or 'approved_with_changes'"
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

    try:
        valid_stages = (
            set(get_pipeline_stages(pipeline_type)) if pipeline_type
            else ALL_KNOWN_STAGES
        )
    except UnknownPipelineError as exc:
        # Reading must stay possible for a project whose pipeline was renamed
        # or removed: validate against every known stage, and say so. Writing
        # never gets here — write_checkpoint rejects the unknown name first.
        logging.getLogger(__name__).warning(
            "%s Validating this checkpoint against the canonical stages.", exc
        )
        valid_stages = ALL_KNOWN_STAGES

    if not isinstance(stage, str) or stage not in valid_stages:
        raise CheckpointValidationError(
            f"Invalid stage: {stage!r} for pipeline {pipeline_type!r}. "
            f"Valid stages: {sorted(valid_stages)}"
        )
    if not isinstance(status, str):
        raise CheckpointValidationError(f"Invalid status: {status!r}")
    if not isinstance(artifacts, dict):
        raise CheckpointValidationError("Checkpoint artifacts must be a dictionary")

    _validate_artifacts_for_stage(stage, status, artifacts, pipeline_type)

    try:
        jsonschema.validate(instance=checkpoint, schema=_load_checkpoint_schema())
    except jsonschema.ValidationError as exc:
        raise CheckpointValidationError(f"Checkpoint failed schema validation: {exc.message}") from exc


def _checkpoint_path(pipeline_dir: Path, project_id: str, stage: str) -> Path:
    return pipeline_dir / project_id / f"checkpoint_{stage}.json"


def init_project(
    project_id: str,
    *,
    title: str,
    pipeline_type: str,
    pipeline_dir: Optional[Path] = None,
    style_playbook: Optional[str] = None,
    series: Optional[str] = None,
) -> Path:
    """Initialize a project workspace with the canonical layout + marker file.

    Creates projects/<project_id>/ with the standard subdirectories and writes
    project.json — the marker the Backlot board uses to render a project's
    identity and stage rail before the first checkpoint exists.

    ``series`` optionally groups several projects (episodes of one show) into
    a single section of the Backlot library. Projects stay flat on disk.

    Idempotent: re-running preserves the original created_at and merges fields.
    Returns the project directory.
    """
    _validate_style_playbook(style_playbook)
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
            with open(marker_path, encoding="utf-8") as f:
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
    if series is not None:
        marker["series"] = series

    with open(marker_path, "w", encoding="utf-8") as f:
        json.dump(marker, f, indent=2)

    return project_dir


def _stage_requires_approval(pipeline_type: Optional[str], stage: str) -> Optional[bool]:
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
    return get_stage_human_approval_default(manifest, stage)


def _enforce_stage_prerequisites(
    pipeline_dir: Path,
    project_id: str,
    pipeline_type: str | None,
    stage: str,
    status: str,
) -> None:
    """Require completed, approved predecessors before advancing a stage.

    ``in_progress`` and failure heartbeats remain writable so an operator can
    inspect or resume a broken run. Only lifecycle advancement
    (``awaiting_human``/``completed``) is gated.
    """

    if status not in {"awaiting_human", "completed"}:
        return
    if not pipeline_type or pipeline_type == "unknown":
        return

    stages = get_pipeline_stages(pipeline_type)
    if stage not in stages:
        return

    incomplete: list[str] = []
    unapproved: list[str] = []
    for predecessor in stages[: stages.index(stage)]:
        path = _checkpoint_path(pipeline_dir, project_id, predecessor)
        if not path.exists():
            incomplete.append(predecessor)
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                checkpoint = json.load(handle)
            validate_checkpoint(checkpoint)
        except (OSError, json.JSONDecodeError, CheckpointValidationError):
            incomplete.append(predecessor)
            continue
        if (
            checkpoint.get("project_id") != project_id
            or checkpoint.get("pipeline_type") != pipeline_type
            or checkpoint.get("stage") != predecessor
        ):
            incomplete.append(predecessor)
            continue
        if checkpoint.get("status") != "completed":
            incomplete.append(predecessor)
            continue
        if _stage_requires_approval(pipeline_type, predecessor) and not checkpoint.get(
            "human_approved"
        ):
            unapproved.append(predecessor)

    if incomplete or unapproved:
        details = []
        if incomplete:
            details.append(f"incomplete or missing: {incomplete}")
        if unapproved:
            details.append(f"completed without required approval: {unapproved}")
        raise CheckpointValidationError(
            f"PREREQUISITE VIOLATION: stage {stage!r} cannot advance; "
            + "; ".join(details)
            + f". Pipeline order: {stages}."
        )


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
        with open(path, encoding="utf-8") as f:
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


# Every other artifact is saved under artifacts/, so agents keep saving a
# second decision log there and appending to it between checkpoints. It is
# not a source of truth: the project log above is. write_checkpoint folds
# anything that only exists in the stray copy into the project log.
STRAY_DECISION_LOG = Path("artifacts") / "decision_log.json"


def _read_decisions(path: Path) -> Optional[list[dict[str, Any]]]:
    """The decisions in a decision-log file; None if it is absent or unusable."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    decisions = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(decisions, list):
        return None
    return [d for d in decisions if isinstance(d, dict)]


def read_decision_log(pipeline_dir: Path, project_id: str) -> dict[str, Any]:
    """The project's decision log — the single source of truth for decisions.

    Read it through this function rather than opening a file: the log lives at
    ``<project>/decision_log.json``, not under ``artifacts/``.
    """
    decisions = _read_decisions(_decision_log_path(pipeline_dir, project_id))
    return {"version": "1.0", "project_id": project_id, "decisions": decisions or []}


def append_decisions(
    pipeline_dir: Path, project_id: str, decisions: list[dict[str, Any]]
) -> Path:
    """Record decisions made between checkpoints in the project decision log.

    The same append-only rules as a checkpoint's ``decision_log`` artifact
    apply (a re-used ``decision_id`` may not change ``selected``). Use this
    instead of hand-writing a decision_log.json file anywhere: a file the
    checkpoint writer does not know about is a second, drifting source.
    """
    log = {"version": "1.0", "project_id": project_id, "decisions": list(decisions)}
    try:
        validate_artifact("decision_log", log)
    except Exception as exc:
        raise CheckpointValidationError(
            f"Decision log entries failed schema validation: {exc}"
        ) from exc
    _merge_decision_log(pipeline_dir, project_id, log)
    return _decision_log_path(pipeline_dir, project_id)


def decision_log_drift(pipeline_dir: Path, project_id: str) -> dict[str, list[str]]:
    """Decisions that exist only in the stray ``artifacts/decision_log.json``.

    ``unlogged`` are decision ids the project log does not have; ``conflicting``
    are ids both files have with a different ``selected`` (an in-place edit of
    a logged decision, which the append-only rule forbids). Read-only.
    """
    stray = _read_decisions(pipeline_dir / project_id / STRAY_DECISION_LOG)
    if not stray:
        return {"unlogged": [], "conflicting": []}
    logged = {
        d.get("decision_id"): d
        for d in _read_decisions(_decision_log_path(pipeline_dir, project_id)) or []
    }
    unlogged, conflicting = [], []
    for decision in stray:
        decision_id = decision.get("decision_id")
        if not decision_id:
            continue
        if decision_id not in logged:
            unlogged.append(decision_id)
        elif logged[decision_id].get("selected") != decision.get("selected"):
            conflicting.append(decision_id)
    return {"unlogged": unlogged, "conflicting": conflicting}


def _ingest_stray_decision_log(pipeline_dir: Path, project_id: str) -> None:
    """Fold decisions that only exist in the stray copy into the project log.

    Runs on every checkpoint write, so a decision saved to
    ``artifacts/decision_log.json`` reaches the audit trail (and the board) at
    the next checkpoint instead of never. Never raises: the stray file is not
    an official input, so an entry that is malformed or that rewrites a logged
    choice is skipped with a warning rather than blocking the checkpoint.
    """
    log = logging.getLogger(__name__)
    drift = decision_log_drift(pipeline_dir, project_id)
    stray_path = pipeline_dir / project_id / STRAY_DECISION_LOG
    if drift["conflicting"]:
        log.warning(
            "%s changes the choice of already-logged decision(s) %s. The decision "
            "log is append-only: these edits are ignored. Re-log each change as a "
            "new decision_id with the same category and subject.",
            stray_path, drift["conflicting"],
        )
    if not drift["unlogged"]:
        return
    wanted = set(drift["unlogged"])
    accepted: list[dict[str, Any]] = []
    for decision in _read_decisions(stray_path) or []:
        if decision.get("decision_id") not in wanted:
            continue
        try:
            validate_artifact(
                "decision_log",
                {"version": "1.0", "project_id": project_id, "decisions": [decision]},
            )
        except Exception as exc:
            log.warning(
                "Decision %r in %s is not schema-valid and was not added to the "
                "project decision log: %s", decision.get("decision_id"), stray_path, exc,
            )
            continue
        accepted.append(decision)
    if not accepted:
        return
    try:
        _merge_decision_log(pipeline_dir, project_id, {"decisions": accepted})
    except CheckpointValidationError as exc:
        log.warning("Could not fold %s into the project decision log: %s", stray_path, exc)
        return
    log.warning(
        "Folded %d decision(s) from %s into the project decision log (%s). Log "
        "decisions through write_checkpoint(..., artifacts={'decision_log': ...}) "
        "or append_decisions(), not by writing that file.",
        len(accepted), stray_path, [d["decision_id"] for d in accepted],
    )


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
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            existing = None
            load_error: Exception | None = exc
        else:
            load_error = None
        if not isinstance(existing, dict) or not isinstance(
            existing.get("decisions"), list
        ):
            # The log is the run's audit trail: never overwrite an unreadable
            # one, and never let it surface as a bare JSONDecodeError either.
            raise CheckpointValidationError(
                f"Project decision log {path} is unreadable or malformed"
                + (f" ({load_error})" if load_error else "")
                + ". It is the run's audit trail, so it is not overwritten "
                "automatically: repair it or move it aside, then re-write "
                "this checkpoint."
            ) from load_error
    else:
        existing = {
            "version": "1.0",
            "project_id": project_id,
            "decisions": [],
        }

    decisions = existing["decisions"]
    index_by_id = {
        d["decision_id"]: i
        for i, d in enumerate(decisions)
        if isinstance(d, dict) and d.get("decision_id")
    }
    changed = not path.exists()
    for decision in new_log.get("decisions", []):
        decision_id = decision.get("decision_id")
        recorded_at = index_by_id.get(decision_id)
        if recorded_at is None:
            decisions.append(decision)
            index_by_id[decision_id] = len(decisions) - 1
            changed = True
            continue
        recorded = decisions[recorded_at]
        if recorded == decision:
            continue  # replay of an already-recorded decision
        if recorded.get("selected") != decision.get("selected"):
            # A changed CHOICE must be re-logged as a new entry (AGENT_GUIDE
            # "Re-log Changed Decisions"). Dropping it silently — the old
            # behaviour — left the audit trail and the board on the stale pick.
            raise CheckpointValidationError(
                f"DECISION LOG VIOLATION: decision_id {decision_id!r} is already "
                f"recorded with selected={recorded.get('selected')!r}, and this "
                f"write changes it to {decision.get('selected')!r}. The decision "
                f"log is append-only: keep the original entry and append a NEW "
                f"decision_id that reuses the same category "
                f"({recorded.get('category')!r}) and subject "
                f"({recorded.get('subject')!r}), with the superseded option in "
                f"options_considered and a rejected_because note."
            )
        # Same choice, refreshed details (user_approved, confidence, reason).
        decisions[recorded_at] = decision
        changed = True

    if not changed:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic swap: a crash mid-write must not truncate the audit trail (a torn
    # file would then block every later checkpoint that carries decisions).
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    os.replace(tmp_path, path)


# Strictest first. `manual_all` gates every stage; `guided` follows the
# manifest; `auto_noncreative` is recorded but cannot loosen a manifest gate
# (the manifest's human_approval_default is binding), so today it behaves as
# `guided`.
_POLICY_STRICTNESS = {"manual_all": 2, "guided": 1, "auto_noncreative": 0}

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@lru_cache(maxsize=4)
def _config_policy_cached(path: str, mtime_ns: int) -> Optional[str]:
    from lib.config_model import OpenMontageConfig

    return OpenMontageConfig.load(Path(path)).checkpoint.policy.value


def _configured_checkpoint_policy() -> Optional[str]:
    """``checkpoint.policy`` from config.yaml, or None when it cannot be read."""
    try:
        return _config_policy_cached(str(_CONFIG_PATH), _CONFIG_PATH.stat().st_mtime_ns)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "config.yaml checkpoint.policy could not be read (%s) — using the "
            "pipeline's default_checkpoint_policy.", exc,
        )
        return None


def resolve_checkpoint_policy(
    pipeline_type: Optional[str], explicit: Optional[str] = None
) -> str:
    """The checkpoint policy in force: the strictest of the three sources.

    Sources: the caller's argument, ``checkpoint.policy`` in config.yaml (the
    user's machine-wide choice) and the manifest's ``default_checkpoint_policy``.
    A stricter one always wins, so setting ``manual_all`` in config.yaml gates
    every stage of every pipeline and no caller can relax it.
    """
    candidates = [explicit, _configured_checkpoint_policy()]
    if pipeline_type and pipeline_type != "unknown":
        try:
            from lib.pipeline_loader import load_pipeline_readonly

            candidates.append(
                load_pipeline_readonly(pipeline_type).get("default_checkpoint_policy")
            )
        except Exception:
            pass
    known = [c for c in candidates if c in _POLICY_STRICTNESS]
    return max(known, key=_POLICY_STRICTNESS.__getitem__) if known else "guided"


def _carried_review(
    path: Path, stage: str, artifacts: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """The review of the checkpoint this write supersedes, if it still applies.

    The usual way a review went missing: the stage was reviewed and written
    ``awaiting_human``, the user approved, and the ``completed`` re-write did
    not pass ``review`` again. That review is still the stage's review, so it
    is carried over — marked as carried, and flagged when the artifact changed
    in between (a revision after feedback that was not reviewed again).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            previous = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(previous, dict) or previous.get("stage") != stage:
        return None
    review = previous.get("review")
    if not isinstance(review, dict) or not review:
        return None
    if previous.get("status") not in {"awaiting_human", "completed"}:
        return None
    carried = dict(review)
    carried.setdefault("carried_from", previous.get("timestamp"))
    current = {k: v for k, v in artifacts.items() if k != "decision_log"}
    if _stage_outputs(previous) != current:
        carried["artifact_changed_since_review"] = True
    return carried


def _auto_cost_snapshot(project_dir: Path, pipeline_type: Optional[str]) -> Optional[dict]:
    """Spend recorded for the project so far, when the caller passed none.

    Tool calls report their cost into events.jsonl on their own; this turns
    that into the checkpoint's cost_snapshot so the meter does not depend on
    an agent typing a number. Returns None when nothing was spent — the board
    then keeps falling back to the asset manifest's total. Never raises.
    """
    try:
        from tools.cost_tracker import project_cost_snapshot

        return project_cost_snapshot(project_dir, pipeline_type=pipeline_type)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Cost snapshot could not be derived for %s (%s) — checkpoint written "
            "without one.", project_dir, exc,
        )
        return None


def write_checkpoint(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    status: str,
    artifacts: dict[str, Any],
    *,
    pipeline_type: Optional[str] = None,
    style_playbook: Optional[str] = None,
    checkpoint_policy: Optional[str] = None,
    human_approval_required: bool = False,
    human_approved: bool = False,
    review: Optional[dict] = None,
    cost_snapshot: Optional[dict] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """Write a checkpoint file for a pipeline stage.

    Things this does so the agent does not have to remember them:

    * ``checkpoint_policy`` defaults to the strictest of config.yaml and the
      manifest (``resolve_checkpoint_policy``); ``manual_all`` gates every stage.
    * ``cost_snapshot`` defaults to the spend the tools recorded
      (``tools.cost_tracker.project_cost_snapshot``).
    * ``review`` defaults to the review of the ``awaiting_human`` checkpoint
      being approved; a stage finished with no review at all is logged.
    * decisions saved to ``artifacts/decision_log.json`` are folded into the
      project decision log.
    """
    # Backfill identity fields from the project marker so omitted kwargs
    # cannot bypass either gate enforcement or style validation.
    marker = None
    marker_path = pipeline_dir / project_id / PROJECT_MARKER_FILENAME
    if marker_path.exists() and (not pipeline_type or not style_playbook):
        try:
            with open(marker_path, encoding="utf-8") as f:
                marker = json.load(f)
        except (json.JSONDecodeError, OSError):
            marker = None
    if isinstance(marker, dict):
        if not pipeline_type and marker.get("pipeline_type"):
            pipeline_type = marker["pipeline_type"]
        if not style_playbook and marker.get("style_playbook"):
            style_playbook = marker["style_playbook"]
    _validate_style_playbook(style_playbook)

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
    # gates on human approval; a caller may gate MORE strictly (e.g. a
    # manual_all checkpoint policy) but never less. A gated stage can only be
    # written "completed" with explicit evidence of approval
    # (human_approved=True). Skipping a gate is a hard error.
    #
    # Enforcement happens at write time only: pre-existing checkpoints written
    # before gating (or by hand) still read as completed — deliberate
    # back-compat so in-flight and legacy projects keep resuming.
    manifest_gate = _stage_requires_approval(pipeline_type, stage)
    checkpoint_policy = resolve_checkpoint_policy(pipeline_type, checkpoint_policy)
    policy_gate = checkpoint_policy == "manual_all"
    gated = bool(manifest_gate) or human_approval_required or policy_gate
    if gated:
        if status == "completed" and not human_approved:
            gate_source = (
                f"human_approval_default: true in the {pipeline_type!r} manifest"
                if manifest_gate
                else "human_approval_required=True was passed by the caller"
                if human_approval_required
                else "checkpoint policy 'manual_all' gates every stage"
            )
            raise CheckpointValidationError(
                f"GATE VIOLATION: stage {stage!r} requires human approval "
                f"({gate_source}) but status='completed' was written without "
                f"human_approved=True. Correct protocol: write "
                f"status='awaiting_human', present the artifact summary to the "
                f"user, END YOUR TURN, and only after the user approves "
                f"re-write with status='completed', human_approved=True."
            )
        human_approval_required = True

    _enforce_stage_prerequisites(
        pipeline_dir,
        project_id,
        pipeline_type,
        stage,
        status,
    )

    path = _checkpoint_path(pipeline_dir, project_id, stage)
    if status in {"completed", "awaiting_human"}:
        if review is None:
            review = _carried_review(path, stage, artifacts)
        if review is None:
            # The reviewer is advisory, so this never blocks — but a stage that
            # reached a gate or finished with no review must leave a trace.
            logging.getLogger(__name__).warning(
                "Stage %r of project %r was written %r without a review. Run "
                "skills/meta/reviewer.md and pass review={...}; the board marks "
                "the stage as unreviewed until then.", stage, project_id, status,
            )
    if cost_snapshot is None:
        cost_snapshot = _auto_cost_snapshot(pipeline_dir / project_id, pipeline_type)

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

    # Reject invalid stage/artifact payloads before persisting their decisions.
    if "decision_log" in artifacts and isinstance(artifacts["decision_log"], dict):
        _merge_decision_log(pipeline_dir, project_id, artifacts["decision_log"])
    _ingest_stray_decision_log(pipeline_dir, project_id)

    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize to a temp file first so a mid-write failure (disk full,
    # unserializable metadata) can never leave the stage with a truncated
    # current checkpoint; then archive the superseded file and swap in the
    # new one atomically.
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)
    # Preserve run history: a superseded completed/awaiting_human checkpoint
    # is copied to history/ (stage versioning, gate audit trail, replay).
    _archive_superseded_checkpoint(path, stage)
    os.replace(tmp_path, path)

    if style_playbook is not None:
        _record_marker_playbook(pipeline_dir / project_id, style_playbook)

    return path


def _record_marker_playbook(project_dir: Path, style_playbook: str) -> None:
    """Keep project.json's style_playbook in step with the latest checkpoint.

    The playbook is usually chosen at proposal, after init_project wrote the
    marker, and the Backlot board reads it from the marker.
    """
    marker_path = project_dir / PROJECT_MARKER_FILENAME
    if not marker_path.exists():
        return
    try:
        with open(marker_path, encoding="utf-8") as f:
            marker = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(marker, dict) or marker.get("style_playbook") == style_playbook:
        return
    marker["style_playbook"] = style_playbook
    tmp_path = marker_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(marker, f, indent=2)
    os.replace(tmp_path, marker_path)


def read_checkpoint(
    pipeline_dir: Path, project_id: str, stage: str
) -> Optional[dict[str, Any]]:
    """Read a checkpoint file. Returns None if not found."""
    path = _checkpoint_path(pipeline_dir, project_id, stage)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
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

    with open(checkpoints[0], encoding="utf-8") as f:
        checkpoint = json.load(f)
    validate_checkpoint(checkpoint)
    return checkpoint


def _marker_pipeline_type(pipeline_dir: Path, project_id: str) -> Optional[str]:
    """The pipeline a project was initialized with, per its project.json."""
    try:
        with open(
            pipeline_dir / project_id / PROJECT_MARKER_FILENAME, encoding="utf-8"
        ) as handle:
            marker = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    pipeline_type = marker.get("pipeline_type") if isinstance(marker, dict) else None
    return pipeline_type if isinstance(pipeline_type, str) and pipeline_type else None


def get_completed_stages(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> list[str]:
    """Return list of stages that have a completed checkpoint.

    When pipeline_type is provided, only checks stages defined in that
    pipeline's manifest and requires their recorded pipeline_type to match —
    preventing false positives from a previous pipeline's shared stages.
    When it is omitted, the project marker's pipeline_type is used; only a
    project with no marker falls back to the canonical stage list.
    """
    pipeline_type = pipeline_type or _marker_pipeline_type(pipeline_dir, project_id)
    stages_to_check = get_pipeline_stages(pipeline_type)
    completed = []
    for stage in stages_to_check:
        cp = read_checkpoint(pipeline_dir, project_id, stage)
        if (
            cp
            and cp.get("status") == "completed"
            and (pipeline_type is None or cp.get("pipeline_type") == pipeline_type)
        ):
            completed.append(stage)
    return completed


def get_next_stage(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> Optional[str]:
    """Determine the next stage to run based on completed checkpoints.

    Uses pipeline-specific stage order so that pipelines with different
    stage sequences (e.g. cinematic vs explainer) progress correctly. An
    omitted pipeline_type is read from the project marker: the canonical
    list names stages (`idea`) that a research-first pipeline does not have,
    so falling back to it sent a finished run to a stage that does not exist.
    """
    pipeline_type = pipeline_type or _marker_pipeline_type(pipeline_dir, project_id)
    stages = get_pipeline_stages(pipeline_type) if pipeline_type else STAGES
    completed = set(get_completed_stages(pipeline_dir, project_id, pipeline_type))
    for stage in stages:
        if stage not in completed:
            return stage
    return None


def get_unreviewed_stages(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> list[str]:
    """Stages that reached a gate or finished with no review on record.

    ``skills/meta/reviewer.md`` asks for a self-review after every stage. The
    reviewer is advisory, so nothing blocks a checkpoint without one — this is
    how a resuming agent (and the board) can still see that it was skipped. A
    stage counts as reviewed when its current checkpoint or any archived
    version of it carries a non-empty ``review``. Advisory and read-only.
    """
    pipeline_type = pipeline_type or _marker_pipeline_type(pipeline_dir, project_id)
    history_dir = pipeline_dir / project_id / HISTORY_DIRNAME
    unreviewed: list[str] = []
    for stage in get_pipeline_stages(pipeline_type):
        try:
            with open(_checkpoint_path(pipeline_dir, project_id, stage), encoding="utf-8") as handle:
                checkpoint = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(checkpoint, dict):
            continue
        if checkpoint.get("status") not in {"completed", "awaiting_human"}:
            continue
        if checkpoint.get("review"):
            continue
        reviewed_before = False
        for archived_path in history_dir.glob(f"checkpoint_{stage}_*.json"):
            try:
                with open(archived_path, encoding="utf-8") as handle:
                    archived = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(archived, dict) and archived.get("stage") == stage and archived.get("review"):
                reviewed_before = True
                break
        if not reviewed_before:
            unreviewed.append(stage)
    return unreviewed


def _parse_timestamp(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _stage_outputs(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """A checkpoint's artifacts minus the cumulative decision log.

    The decision log grows on every write, so it must not count as a change
    to what the stage produced.
    """
    artifacts = checkpoint.get("artifacts")
    if not isinstance(artifacts, dict):
        return {}
    return {k: v for k, v in artifacts.items() if k != "decision_log"}


def _stage_outputs_as_of(
    pipeline_dir: Path, project_id: str, stage: str, moment: datetime
) -> Optional[dict[str, Any]]:
    """Outputs of the newest archived completed ``stage`` written by ``moment``."""
    newest: Optional[tuple[datetime, dict[str, Any]]] = None
    history_dir = pipeline_dir / project_id / HISTORY_DIRNAME
    for path in history_dir.glob(f"checkpoint_{stage}_*.json"):
        try:
            with open(path, encoding="utf-8") as handle:
                archived = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            not isinstance(archived, dict)
            or archived.get("stage") != stage
            or archived.get("status") != "completed"
        ):
            continue
        written = _parse_timestamp(archived.get("timestamp"))
        if written is None or written > moment:
            continue
        if newest is None or written > newest[0]:
            newest = (written, _stage_outputs(archived))
    return newest[1] if newest else None


def get_stale_stages(
    pipeline_dir: Path, project_id: str, pipeline_type: str | None = None
) -> list[dict[str, str]]:
    """Completed stages that predate a later change to an earlier stage.

    ``get_next_stage`` only looks at completion, so re-running an upstream
    stage (a revised script after the assets were generated) leaves every
    downstream checkpoint reading ``completed`` although it was derived from
    the superseded artifact. This reports those stages so a resuming agent can
    tell the user and re-run or re-confirm them.

    Advisory and read-only: it never raises on unreadable checkpoints and it
    does not change what ``get_next_stage`` returns. A re-write of an upstream
    checkpoint whose outputs are byte-for-byte what the downstream stage was
    built from (a metadata-only refresh) is not reported.

    Returns ``[{"stage": <stale stage>, "superseded_by": <upstream stage>}]``
    in pipeline order.
    """
    pipeline_type = pipeline_type or _marker_pipeline_type(pipeline_dir, project_id)
    stale: list[dict[str, str]] = []
    upstream: list[tuple[str, datetime, dict[str, Any]]] = []
    for stage in get_pipeline_stages(pipeline_type):
        path = _checkpoint_path(pipeline_dir, project_id, stage)
        try:
            with open(path, encoding="utf-8") as handle:
                checkpoint = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(checkpoint, dict) or checkpoint.get("status") != "completed":
            continue
        if pipeline_type and checkpoint.get("pipeline_type") != pipeline_type:
            continue
        written = _parse_timestamp(checkpoint.get("timestamp"))
        if written is None:
            continue

        for name, upstream_written, upstream_outputs in upstream:
            if upstream_written <= written:
                continue
            built_from = _stage_outputs_as_of(pipeline_dir, project_id, name, written)
            if built_from is not None and built_from == upstream_outputs:
                continue  # upstream was re-written without changing its outputs
            stale.append({"stage": stage, "superseded_by": name})
            break
        upstream.append((stage, written, _stage_outputs(checkpoint)))
    return stale
