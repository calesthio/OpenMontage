"""Approval-profile and resumable checkpoint contracts.

The generic avatar pipeline normally has several creative gates.  A client may
select an explicit manifest-defined profile that collapses the cheap planning
stages into one preview and keeps the paid avatar call gated.  The default
pipeline policy must remain unchanged for every other run.
"""

from __future__ import annotations

import json

import pytest

from lib.checkpoint import (
    _resolve_approval_profile,
    assert_checkpoint_approved_for_resume,
    CheckpointValidationError,
    checkpoint_resume_token,
    get_next_stage,
    init_project,
    read_checkpoint,
    record_checkpoint_approval,
    write_checkpoint,
)
from tests.contracts.test_phase0_contracts import sample_artifact
from schemas.artifacts import validate_artifact


PROFILE = "preview_then_avatar"


def _init_profiled_project(tmp_path):
    return init_project(
        "brand-short",
        title="Brand short",
        pipeline_type="avatar-spokesperson",
        pipeline_dir=tmp_path,
        style_playbook="client-playbook",
        approval_profile=PROFILE,
    )


def test_profile_auto_completes_cheap_stages_without_weakening_default(tmp_path):
    project = _init_profiled_project(tmp_path)

    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "idea",
        "completed",
        {"brief": sample_artifact("brief")},
        pipeline_type="avatar-spokesperson",
        # A director following the unprofiled defaults may still pass this.
        # The explicitly selected profile remains the binding policy.
        human_approval_required=True,
    )

    checkpoint = json.loads(path.read_text())
    marker = json.loads((project / "project.json").read_text())
    assert checkpoint["approval_profile"] == PROFILE
    assert checkpoint["human_approval_required"] is False
    assert marker["approval_profile"] == PROFILE

    with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
        write_checkpoint(
            tmp_path,
            "default-short",
            "idea",
            "completed",
            {"brief": sample_artifact("brief")},
            pipeline_type="avatar-spokesperson",
        )


def test_profile_keeps_structure_preview_compose_stage_gated(tmp_path):
    _init_profiled_project(tmp_path)

    write_checkpoint(
        tmp_path,
        "brand-short",
        "assets",
        "completed",
        {"asset_manifest": sample_artifact("asset_manifest")},
        pipeline_type="avatar-spokesperson",
    )
    with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
        write_checkpoint(
            tmp_path,
            "brand-short",
            "compose",
            "completed",
            {"render_report": sample_artifact("render_report")},
            pipeline_type="avatar-spokesperson",
        )


def test_unknown_profile_fails_closed(tmp_path):
    with pytest.raises(CheckpointValidationError, match="Unknown approval_profile"):
        init_project(
            "unknown-profile",
            title="Unknown",
            pipeline_type="avatar-spokesperson",
            pipeline_dir=tmp_path,
            approval_profile="does-not-exist",
        )
    assert not (tmp_path / "unknown-profile").exists()


def test_resume_token_binds_explicit_human_approval_to_awaiting_checkpoint(tmp_path):
    _init_profiled_project(tmp_path)
    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
        metadata={"preview_path": "renders/structure.mp4"},
    )
    awaiting = json.loads(path.read_text())
    token = checkpoint_resume_token(awaiting)

    approved_path = record_checkpoint_approval(
        tmp_path,
        "brand-short",
        "compose",
        expected_resume_token=token,
        approval_evidence={
            "decision": "APROBAR AVATAR",
            "source": "whatsapp",
            "source_message_id": "wamid.test",
            "timestamp": "2026-07-16T01:00:00+00:00",
        },
    )

    approved = json.loads(approved_path.read_text())
    assert approved["status"] == "awaiting_human"
    assert approved["human_approved"] is True
    assert approved["artifacts"] == awaiting["artifacts"]
    assert approved["metadata"]["approval_evidence"]["decision"] == "APROBAR AVATAR"
    assert approved["metadata"]["approved_resume_token"] == token
    evidence = assert_checkpoint_approved_for_resume(
        tmp_path,
        "brand-short",
        "compose",
        expected_resume_token=token,
        expected_decision="APROBAR AVATAR",
    )
    assert evidence["source_message_id"] == "wamid.test"


def test_resume_rejects_stale_token(tmp_path):
    _init_profiled_project(tmp_path)
    write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
    )

    with pytest.raises(CheckpointValidationError, match="resume token"):
        record_checkpoint_approval(
            tmp_path,
            "brand-short",
            "compose",
            expected_resume_token="stale-token",
            approval_evidence={
                "decision": "APROBAR AVATAR",
                "source_message_id": "wamid.stale",
                "timestamp": "2026-07-16T01:00:00+00:00",
            },
        )


def test_approval_evidence_requires_message_identity_and_timestamp(tmp_path):
    _init_profiled_project(tmp_path)
    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
    )
    token = checkpoint_resume_token(json.loads(path.read_text()))

    with pytest.raises(CheckpointValidationError, match="source_message_id"):
        record_checkpoint_approval(
            tmp_path,
            "brand-short",
            "compose",
            expected_resume_token=token,
            approval_evidence={"decision": "APROBAR AVATAR"},
        )


def test_approval_evidence_rejects_invalid_timestamp(tmp_path):
    _init_profiled_project(tmp_path)
    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
    )
    token = checkpoint_resume_token(json.loads(path.read_text()))

    with pytest.raises(CheckpointValidationError, match="timestamp"):
        record_checkpoint_approval(
            tmp_path,
            "brand-short",
            "compose",
            expected_resume_token=token,
            approval_evidence={
                "decision": "APROBAR AVATAR",
                "source_message_id": "wamid.invalid-time",
                "timestamp": "yesterday",
            },
        )


def test_paid_resume_requires_the_exact_expected_decision(tmp_path):
    _init_profiled_project(tmp_path)
    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
    )
    token = checkpoint_resume_token(json.loads(path.read_text()))
    record_checkpoint_approval(
        tmp_path,
        "brand-short",
        "compose",
        expected_resume_token=token,
        approval_evidence={
            "decision": "OK",
            "source_message_id": "wamid.ambiguous",
            "timestamp": "2026-07-16T01:00:00+00:00",
        },
    )

    with pytest.raises(CheckpointValidationError, match="decision"):
        assert_checkpoint_approved_for_resume(
            tmp_path,
            "brand-short",
            "compose",
            expected_resume_token=token,
            expected_decision="APROBAR AVATAR",
        )


def test_write_checkpoint_rejects_profile_not_selected_by_project(tmp_path):
    """A per-call profile must not opt a default project out of its gates."""
    init_project(
        "default-avatar",
        title="Default avatar",
        pipeline_type="avatar-spokesperson",
        pipeline_dir=tmp_path,
    )

    with pytest.raises(CheckpointValidationError, match="cannot override"):
        write_checkpoint(
            tmp_path,
            "default-avatar",
            "idea",
            "completed",
            {"brief": sample_artifact("brief")},
            pipeline_type="avatar-spokesperson",
            approval_profile=PROFILE,
        )
    assert not (tmp_path / "default-avatar" / "checkpoint_idea.json").exists()

    # Same bypass without any project marker at all: also rejected.
    with pytest.raises(CheckpointValidationError, match="cannot override"):
        write_checkpoint(
            tmp_path,
            "no-marker",
            "idea",
            "completed",
            {"brief": sample_artifact("brief")},
            pipeline_type="avatar-spokesperson",
            approval_profile=PROFILE,
        )


def test_write_checkpoint_rejects_profile_differing_from_marker(tmp_path):
    _init_profiled_project(tmp_path)

    with pytest.raises(CheckpointValidationError, match="cannot override"):
        write_checkpoint(
            tmp_path,
            "brand-short",
            "idea",
            "completed",
            {"brief": sample_artifact("brief")},
            pipeline_type="avatar-spokesperson",
            approval_profile="some-other-profile",
        )


def test_write_checkpoint_accepts_explicit_profile_matching_marker(tmp_path):
    _init_profiled_project(tmp_path)

    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "idea",
        "completed",
        {"brief": sample_artifact("brief")},
        pipeline_type="avatar-spokesperson",
        approval_profile=PROFILE,
    )
    checkpoint = json.loads(path.read_text())
    assert checkpoint["approval_profile"] == PROFILE
    assert checkpoint["human_approval_required"] is False


def test_stage_override_typo_fails_closed():
    """A typo'd stage name would silently drop the gate it meant to set."""
    manifest = {
        "stages": [{"name": "idea"}, {"name": "compose"}],
        "approval_profiles": {
            "typo-profile": {
                "stage_overrides": {"idea": False, "comopse": True},
            },
        },
    }

    with pytest.raises(CheckpointValidationError, match="comopse"):
        _resolve_approval_profile(manifest, "avatar-spokesperson", "typo-profile")


def test_post_approval_rerun_typo_fails_closed():
    manifest = {
        "stages": [{"name": "assets"}, {"name": "compose"}],
        "approval_profiles": {
            "typo-profile": {
                "stage_overrides": {"compose": True},
                "post_approval_rerun": ["asets", "compose"],
            },
        },
    }

    with pytest.raises(CheckpointValidationError, match="asets"):
        _resolve_approval_profile(manifest, "avatar-spokesperson", "typo-profile")


def test_all_manifest_approval_profiles_reference_declared_stages():
    import jsonschema

    from lib.pipeline_loader import list_pipelines, load_pipeline

    for name in list_pipelines():
        try:
            manifest = load_pipeline(name)
        except jsonschema.ValidationError:
            # Generic manifest validity is covered by the manifest contract
            # suite; this test only guards profile/stage consistency.
            continue
        for profile_name in (manifest.get("approval_profiles") or {}):
            _resolve_approval_profile(manifest, name, profile_name)


def test_post_approval_transition_reruns_placeholder_stages(tmp_path):
    """After approval, the deterministic loop must reach the paid avatar pass.

    The cheap run leaves assets/edit completed with placeholder content and
    compose awaiting approval. Recording the approval must supersede those
    placeholder checkpoints so get_next_stage routes back to assets, instead
    of re-rendering the placeholder at compose forever.
    """
    _init_profiled_project(tmp_path)

    def _artifact(name):
        artifact = sample_artifact(name)
        if name == "edit_decisions":
            artifact["render_runtime"] = "ffmpeg"
        return artifact

    cheap_pass = [
        ("idea", "brief"),
        ("script", "script"),
        ("scene_plan", "scene_plan"),
        ("assets", "asset_manifest"),
        ("edit", "edit_decisions"),
    ]
    for stage, artifact in cheap_pass:
        write_checkpoint(
            tmp_path,
            "brand-short",
            stage,
            "completed",
            {artifact: _artifact(artifact)},
            pipeline_type="avatar-spokesperson",
        )
    path = write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "awaiting_human",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
        metadata={"preview_path": "renders/structure.mp4"},
    )
    token = checkpoint_resume_token(json.loads(path.read_text()))
    assert get_next_stage(tmp_path, "brand-short", "avatar-spokesperson") == "compose"

    record_checkpoint_approval(
        tmp_path,
        "brand-short",
        "compose",
        expected_resume_token=token,
        approval_evidence={
            "decision": "APROBAR AVATAR",
            "source_message_id": "wamid.rerun",
            "timestamp": "2026-07-16T01:00:00+00:00",
        },
    )

    # Placeholder checkpoints are superseded (archived, not destroyed) ...
    assert get_next_stage(tmp_path, "brand-short", "avatar-spokesperson") == "assets"
    assert read_checkpoint(tmp_path, "brand-short", "assets") is None
    assert read_checkpoint(tmp_path, "brand-short", "edit") is None
    history = tmp_path / "brand-short" / "history"
    assert list(history.glob("checkpoint_assets_*.json"))
    assert list(history.glob("checkpoint_edit_*.json"))

    # ... while the approved compose checkpoint keeps the resume token the
    # paid adapter verifies immediately before spend.
    compose = read_checkpoint(tmp_path, "brand-short", "compose")
    assert compose["status"] == "awaiting_human"
    assert_checkpoint_approved_for_resume(
        tmp_path,
        "brand-short",
        "compose",
        expected_resume_token=token,
        expected_decision="APROBAR AVATAR",
    )

    # The governed runner re-runs assets -> edit -> compose with the real
    # avatar; the approved evidence authorizes the final compose write.
    for stage, artifact in (("assets", "asset_manifest"), ("edit", "edit_decisions")):
        write_checkpoint(
            tmp_path,
            "brand-short",
            stage,
            "completed",
            {artifact: _artifact(artifact)},
            pipeline_type="avatar-spokesperson",
        )
    write_checkpoint(
        tmp_path,
        "brand-short",
        "compose",
        "completed",
        {"render_report": sample_artifact("render_report")},
        pipeline_type="avatar-spokesperson",
        human_approved=True,
    )
    assert get_next_stage(tmp_path, "brand-short", "avatar-spokesperson") == "publish"


def test_render_report_accepts_a_content_bound_output_hash():
    report = sample_artifact("render_report")
    report["outputs"][0]["sha256"] = "a" * 64

    validate_artifact("render_report", report)


def test_render_report_rejects_a_malformed_output_hash():
    report = sample_artifact("render_report")
    report["outputs"][0]["sha256"] = "not-a-sha256"

    with pytest.raises(Exception):
        validate_artifact("render_report", report)
