"""Thin hosted job runner for the standalone Ray deployment."""

from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import requests

from backlot import storage
from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint


DEFAULT_VIDEO_MODEL = "grok-imagine-video"
DEFAULT_SCENE_SECONDS = 15
MAX_DURATION_SECONDS = 180
MAX_SCENE_COUNT = 12
SUPPORTED_ASPECTS = {"16:9", "9:16", "1:1", "4:3", "3:4"}
FINAL_WIDTH = 1080
FINAL_HEIGHT = 1920
FINAL_FPS = 24
TRANSITION_SECONDS = 0.375
END_CARD_SECONDS = 3.5
VISUAL_PROMPT_BANNED_WORDS = ("vignette", "matte", "frame", "border")
DEFAULT_END_CARD_TAGLINE = "Handcrafted. Heirloom. Yours."
DEFAULT_END_CARD_CTA = "Enquire now"
ASPECT_RATIO_TOLERANCE = 0.025
VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "grok-imagine-video": {
        "id": "grok-imagine-video",
        "label": "Grok Imagine",
        "provider": "grok",
        "tool_name": "grok_video",
        "provider_label": "fal.ai / xAI",
        "model_variant": "grok-imagine-video",
        "max_scene_seconds": 15,
        "min_scene_seconds": 1,
        "aspects": SUPPORTED_ASPECTS,
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY", "XAI_API_KEY"),
        "resolution": "720p",
        "priority": 1,
        "default": True,
    },
    "kling-v3": {
        "id": "kling-v3",
        "label": "Kling 3",
        "provider": "kling",
        "tool_name": "kling_video",
        "provider_label": "fal.ai",
        "model_variant": "v3/standard",
        "max_scene_seconds": 10,
        "min_scene_seconds": 5,
        "aspects": {"16:9", "9:16", "1:1"},
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY"),
        "resolution": "720p",
        "priority": 0,
        "reference_mode_note": "Prepared start-frame image_to_video with optional element references in this hosted adapter.",
    },
    "veo3.1": {
        "id": "veo3.1",
        "label": "Veo 3.1",
        "provider": "veo",
        "tool_name": "veo_video",
        "provider_label": "fal.ai",
        "model_variant": "veo3.1",
        "max_scene_seconds": 8,
        "min_scene_seconds": 4,
        "aspects": {"16:9", "9:16"},
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY"),
        "resolution": "720p",
        "priority": 2,
    },
    "veo3.1-fast": {
        "id": "veo3.1-fast",
        "label": "Veo 3.1 Fast",
        "provider": "veo",
        "tool_name": "veo_video",
        "provider_label": "fal.ai",
        "model_variant": "veo3.1/fast",
        "max_scene_seconds": 8,
        "min_scene_seconds": 4,
        "aspects": {"16:9", "9:16"},
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY"),
        "resolution": "720p",
        "priority": 3,
    },
    "seedance-standard": {
        "id": "seedance-standard",
        "label": "Seedance 2.0 Standard",
        "provider": "seedance",
        "tool_name": "seedance_video",
        "provider_label": "fal.ai",
        "model_variant": "standard",
        "max_scene_seconds": 15,
        "min_scene_seconds": 4,
        "aspects": SUPPORTED_ASPECTS,
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY"),
        "resolution": "720p",
        "priority": 90,
        "requires_explicit_paid_approval": True,
    },
    "seedance-fast": {
        "id": "seedance-fast",
        "label": "Seedance 2.0 Fast",
        "provider": "seedance",
        "tool_name": "seedance_video",
        "provider_label": "fal.ai",
        "model_variant": "fast",
        "max_scene_seconds": 15,
        "min_scene_seconds": 4,
        "aspects": SUPPORTED_ASPECTS,
        "requires_any_env": ("FAL_KEY", "FAL_AI_API_KEY"),
        "resolution": "720p",
        "priority": 91,
        "requires_explicit_paid_approval": True,
    },
}


class JobError(RuntimeError):
    pass


class JobAwaitingHuman(JobError):
    pass


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:64] or "ray-job"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_optional_budget_cap(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        cap = float(value)
    except (TypeError, ValueError):
        raise JobError("Budget cap must be a number.")
    if cap < 0:
        raise JobError("Budget cap cannot be negative.")
    return round(cap, 2)


def video_model_options() -> list[dict[str, Any]]:
    options = []
    for config in sorted(VIDEO_MODELS.values(), key=lambda item: int(item.get("priority", 50))):
        options.append({
            "id": config["id"],
            "label": config["label"],
            "provider": config["provider"],
            "model_variant": config["model_variant"],
            "max_scene_seconds": config["max_scene_seconds"],
            "supported_aspects": sorted(config["aspects"]),
            "available": _has_any_env(config["requires_any_env"]),
            "requires_any_env": list(config["requires_any_env"]),
            "is_default": config["id"] == DEFAULT_VIDEO_MODEL,
            "requires_explicit_paid_approval": bool(config.get("requires_explicit_paid_approval")),
            **({"reference_mode_note": config["reference_mode_note"]} if config.get("reference_mode_note") else {}),
        })
    return options


def create_job(payload: dict[str, Any], user: dict[str, Any] | None = None) -> dict[str, Any]:
    title = str(payload.get("title") or "Untitled Ray Job").strip()[:120]
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise JobError("Prompt is required.")

    video_model = _normalize_video_model(payload.get("video_model") or payload.get("model_variant"))
    model_config = _video_model_config(video_model)
    if not _has_any_env(model_config["requires_any_env"]):
        keys = " or ".join(model_config["requires_any_env"])
        raise JobError(f"{model_config['label']} requires {keys}. Choose another video model or configure the key.")

    aspect_ratio = str(payload.get("aspect_ratio") or "16:9")
    if aspect_ratio not in SUPPORTED_ASPECTS:
        aspect_ratio = "16:9"
    if aspect_ratio not in model_config["aspects"]:
        supported = ", ".join(sorted(model_config["aspects"]))
        raise JobError(f"{model_config['label']} supports {supported} in this hosted build.")
    try:
        duration = int(payload.get("duration_seconds") or 15)
    except (TypeError, ValueError):
        raise JobError("Duration must be a number of seconds.")
    if duration < 5 or duration > MAX_DURATION_SECONDS:
        raise JobError(f"Duration must be between 5 and {MAX_DURATION_SECONDS} seconds.")

    model_max_duration = min(MAX_DURATION_SECONDS, model_config["max_scene_seconds"] * MAX_SCENE_COUNT)
    if duration > model_max_duration:
        raise JobError(
            f"{model_config['label']} supports up to {model_max_duration} seconds in this hosted build. "
            "Choose a longer-clip model or a shorter duration."
        )

    default_scene_count = _recommended_scene_count(duration, model_config)
    try:
        scene_count = int(payload.get("scene_count") or default_scene_count)
    except (TypeError, ValueError):
        raise JobError("Scene count must be a number.")
    scene_count = max(scene_count, default_scene_count)
    if scene_count < 1 or scene_count > MAX_SCENE_COUNT:
        raise JobError(f"Scene count must be between 1 and {MAX_SCENE_COUNT}.")

    base_slug = slugify(title)
    project_id = f"{base_slug}-{int(time.time())}"
    project_dir = init_project(project_id, title=title, pipeline_type="cinematic")
    budget_cap = _coerce_optional_budget_cap(payload.get("budget_cap_usd"))
    request_data = {
        "version": "1.0",
        "project_id": project_id,
        "title": title,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration,
        "scene_count": scene_count,
        "video_model": model_config["id"],
        "video_model_label": model_config["label"],
        "video_provider": model_config["provider"],
        "model_variant": model_config["model_variant"],
        "max_scene_seconds": model_config["max_scene_seconds"],
        "reference_assets": payload.get("reference_assets") or [],
        "chat_messages": payload.get("chat_messages") or [],
        "created_at": now_iso(),
        "created_by": (user or {}).get("sub"),
    }
    if budget_cap is not None:
        request_data["budget_cap_usd"] = budget_cap
    _write_json(project_dir / "artifacts" / "job_request.json", request_data)
    return {"project_id": project_id, "url": f"/p/{project_id}", "request": request_data}


def plan_job(project_id: str, force: bool = False) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    request_data = _read_json(project_dir / "artifacts" / "job_request.json")
    current_stage = "proposal"
    try:
        proposal_path = project_dir / "artifacts" / "proposal_packet.json"
        script_path = project_dir / "artifacts" / "script.json"
        scene_plan_path = project_dir / "artifacts" / "scene_plan.json"
        if not force and proposal_path.is_file() and script_path.is_file() and scene_plan_path.is_file():
            return {"ok": True, "project_id": project_id, "status": "planned"}

        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "proposal",
            "in_progress",
            {},
            pipeline_type="cinematic",
            metadata={"source": "hosted_ui", "mode": "safe_plan"},
        )

        plan = _plan_with_llm(request_data)
        script, scene_plan = _artifacts_from_plan(request_data, plan)
        proposal_packet, decision_log = _proposal_from_plan(project_id, request_data, script, scene_plan)

        _write_json(proposal_path, proposal_packet)
        _write_json(project_dir / "artifacts" / "decision_log.json", decision_log)
        _write_json(script_path, script)
        _write_json(scene_plan_path, scene_plan)

        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "proposal",
            "awaiting_human",
            {"proposal_packet": proposal_packet, "decision_log": decision_log},
            pipeline_type="cinematic",
            cost_snapshot=_proposal_cost_snapshot(proposal_packet),
            metadata={
                "source": "hosted_ui",
                "mode": "safe_plan",
                "approval_note": "No provider video generation has run. Approve paid generation to continue.",
            },
        )
        status = "blocked_reference_assets" if _is_reference_blocked(proposal_packet) else "awaiting_approval"
        return {"ok": True, "project_id": project_id, "status": status}
    except Exception as exc:
        _write_json(project_dir / "artifacts" / "job_error.json", {
            "version": "1.0",
            "error": str(exc),
            "failed_at": now_iso(),
        })
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            current_stage,
            "failed",
            {},
            pipeline_type="cinematic",
            error=str(exc),
            metadata={"source": "hosted_ui", "mode": "safe_plan"},
        )
        raise


def revise_plan(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    req_path = project_dir / "artifacts" / "job_request.json"
    request_data = _read_json(req_path)

    proposal_checkpoint = project_dir / "checkpoint_proposal.json"
    if proposal_checkpoint.is_file():
        checkpoint = _read_json(proposal_checkpoint)
        if checkpoint.get("status") not in {"awaiting_human", "failed"}:
            raise JobError("Plan changes are only available while the proposal is waiting for review.")

    title = str(payload.get("title") or request_data.get("title") or "Untitled Ray Job").strip()[:120]
    prompt = str(payload.get("prompt") or request_data.get("prompt") or "").strip()
    if not prompt:
        raise JobError("Prompt is required.")

    video_model = _normalize_video_model(payload.get("video_model") or request_data.get("video_model"))
    model_config = _video_model_config(video_model)
    if not _has_any_env(model_config["requires_any_env"]):
        keys = " or ".join(model_config["requires_any_env"])
        raise JobError(f"{model_config['label']} requires {keys}. Choose another video model or configure the key.")

    aspect_ratio = str(payload.get("aspect_ratio") or request_data.get("aspect_ratio") or "16:9")
    if aspect_ratio not in SUPPORTED_ASPECTS:
        raise JobError(f"Aspect ratio must be one of {', '.join(sorted(SUPPORTED_ASPECTS))}.")
    if aspect_ratio not in model_config["aspects"]:
        supported = ", ".join(sorted(model_config["aspects"]))
        raise JobError(f"{model_config['label']} supports {supported} in this hosted build.")

    try:
        duration = int(payload.get("duration_seconds") or request_data.get("duration_seconds") or 15)
    except (TypeError, ValueError):
        raise JobError("Duration must be a number of seconds.")
    if duration < 5 or duration > MAX_DURATION_SECONDS:
        raise JobError(f"Duration must be between 5 and {MAX_DURATION_SECONDS} seconds.")

    model_max_duration = min(MAX_DURATION_SECONDS, model_config["max_scene_seconds"] * MAX_SCENE_COUNT)
    if duration > model_max_duration:
        raise JobError(f"{model_config['label']} supports up to {model_max_duration} seconds in this hosted build.")

    min_scene_count = _recommended_scene_count(duration, model_config)
    try:
        scene_count = int(payload.get("scene_count") or request_data.get("scene_count") or min_scene_count)
    except (TypeError, ValueError):
        raise JobError("Scene count must be a number.")
    if scene_count < min_scene_count:
        raise JobError(
            f"{duration}s with {model_config['label']} needs at least {min_scene_count} scene"
            f"{'' if min_scene_count == 1 else 's'}."
        )
    if scene_count > MAX_SCENE_COUNT:
        raise JobError(f"Scene count must be between {min_scene_count} and {MAX_SCENE_COUNT}.")

    request_data.update({
        "title": title,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration,
        "scene_count": scene_count,
        "video_model": model_config["id"],
        "video_model_label": model_config["label"],
        "video_provider": model_config["provider"],
        "model_variant": model_config["model_variant"],
        "max_scene_seconds": model_config["max_scene_seconds"],
        "revised_at": now_iso(),
    })
    if "budget_cap_usd" in payload:
        request_data["budget_cap_usd"] = _coerce_optional_budget_cap(payload.get("budget_cap_usd"))
    if isinstance(payload.get("reference_assets"), list):
        request_data["reference_assets"] = payload["reference_assets"]
    _write_json(req_path, request_data)
    marker_path = project_dir / "project.json"
    if marker_path.is_file():
        marker = _read_json(marker_path)
        marker["title"] = title
        _write_json(marker_path, marker)

    for filename in (
        "proposal_packet.json",
        "decision_log.json",
        "script.json",
        "scene_plan.json",
        "asset_manifest.json",
        "edit_decisions.json",
        "render_report.json",
    ):
        try:
            (project_dir / "artifacts" / filename).unlink()
        except FileNotFoundError:
            pass
    for filename in (
        "checkpoint_script.json",
        "checkpoint_scene_plan.json",
        "checkpoint_assets.json",
        "checkpoint_edit.json",
        "checkpoint_compose.json",
    ):
        try:
            (project_dir / filename).unlink()
        except FileNotFoundError:
            pass
    return plan_job(project_id, force=True)


def approve_paid_generation(
    project_id: str,
    override_no_references: bool = False,
    confirm_seedance_risk: bool = False,
) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    request_data = _read_json(project_dir / "artifacts" / "job_request.json")
    current_stage = "proposal"
    try:
        proposal_path = project_dir / "artifacts" / "proposal_packet.json"
        script_path = project_dir / "artifacts" / "script.json"
        scene_plan_path = project_dir / "artifacts" / "scene_plan.json"
        if not (proposal_path.is_file() and script_path.is_file() and scene_plan_path.is_file()):
            plan_job(project_id)

        proposal_packet = _read_json(proposal_path)
        decision_log = _read_json(project_dir / "artifacts" / "decision_log.json")
        script = _read_json(script_path)
        scene_plan = _read_json(scene_plan_path)
        validate_paid_generation_allowed(
            project_id,
            override_no_references=override_no_references,
            confirm_seedance_risk=confirm_seedance_risk,
        )
        proposal_packet = _read_json(proposal_path)

        model_config = _video_model_config_from_request(request_data)
        approved_budget = _budget_cap_from_request(request_data)
        proposal_packet["approval"] = {
            "status": "approved",
            "user_notes": "Approved in hosted Ray board.",
            "approved_budget_usd": (
                approved_budget
                if approved_budget is not None
                else float(proposal_packet.get("cost_estimate", {}).get("total_estimated_usd") or 0)
            ),
            **({"override_no_references": True} if override_no_references else {}),
            **({"confirm_seedance_risk": True} if _requires_explicit_paid_approval(model_config) else {}),
        }
        for decision in decision_log.get("decisions", []):
            decision["user_approved"] = True
        _write_json(proposal_path, proposal_packet)
        _write_json(project_dir / "artifacts" / "decision_log.json", decision_log)

        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "proposal",
            "completed",
            {"proposal_packet": proposal_packet, "decision_log": decision_log},
            pipeline_type="cinematic",
            human_approved=True,
            cost_snapshot=_proposal_cost_snapshot(proposal_packet),
            metadata={"source": "hosted_ui", "approval": "explicit_paid_generation_approval"},
        )

        current_stage = "script"
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "script",
            "completed",
            {"script": script},
            pipeline_type="cinematic",
            human_approved=True,
            metadata={"source": "hosted_ui", "approval": "explicit_paid_generation_approval"},
        )

        current_stage = "scene_plan"
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "scene_plan",
            "completed",
            {"scene_plan": scene_plan},
            pipeline_type="cinematic",
            human_approved=True,
            metadata={"source": "hosted_ui", "approval": "explicit_paid_generation_approval"},
        )

        current_stage = "assets"
        sample_first = _needs_reference_fidelity_review(request_data)
        asset_manifest = _generate_assets(project_id, project_dir, request_data, scene_plan, sample_only=sample_first)
        if sample_first:
            _mark_reference_review_required(asset_manifest, request_data, scene_plan, phase="sample")
            _write_json(project_dir / "artifacts" / "asset_manifest.json", asset_manifest)
            write_checkpoint(
                PROJECTS_DIR,
                project_id,
                "assets",
                "awaiting_human",
                {"asset_manifest": asset_manifest},
                pipeline_type="cinematic",
                human_approval_required=True,
                cost_snapshot=_cost_snapshot(asset_manifest),
                review={
                    "critical": 1,
                    "suggestions": 0,
                    "nitpicks": 0,
                    "summary": "Review reference fidelity before spending on the remaining clips.",
                },
                metadata={"source": "hosted_ui", "review_required": "reference_fidelity_sample"},
            )
            raise JobAwaitingHuman("Generated a reference-fidelity sample; waiting for explicit clip review before spending more.")
        _write_json(project_dir / "artifacts" / "asset_manifest.json", asset_manifest)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "assets",
            "completed",
            {"asset_manifest": asset_manifest},
            pipeline_type="cinematic",
            human_approved=True,
            cost_snapshot=_cost_snapshot(asset_manifest),
            metadata={"source": "hosted_ui", "approval": "explicit_paid_generation_approval"},
        )

        current_stage = "compose"
        edit_decisions, render_report = _compose(project_id, project_dir, asset_manifest, request_data, scene_plan)
        _write_json(project_dir / "artifacts" / "edit_decisions.json", edit_decisions)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "edit",
            "completed",
            {"edit_decisions": edit_decisions},
            pipeline_type="cinematic",
            metadata={"source": "hosted_ui"},
        )
        _write_json(project_dir / "artifacts" / "render_report.json", render_report)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "compose",
            "completed",
            {"render_report": render_report},
            pipeline_type="cinematic",
            metadata={"source": "hosted_ui"},
        )
        return {"ok": True, "project_id": project_id, "status": "completed"}
    except JobAwaitingHuman as exc:
        return {"ok": False, "project_id": project_id, "status": "awaiting_human", "error": str(exc)}
    except Exception as exc:
        _write_json(project_dir / "artifacts" / "job_error.json", {
            "version": "1.0",
            "error": str(exc),
            "failed_at": now_iso(),
        })
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            current_stage,
            "failed",
            {},
            pipeline_type="cinematic",
            error=str(exc),
            metadata={"source": "hosted_ui", "approval": "explicit_paid_generation_approval"},
        )
        raise


def approve_asset_review(project_id: str) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    request_data = _read_json(project_dir / "artifacts" / "job_request.json")
    scene_plan = _read_json(project_dir / "artifacts" / "scene_plan.json")
    manifest_path = project_dir / "artifacts" / "asset_manifest.json"
    if not manifest_path.is_file():
        raise JobError("No asset manifest is available for review.")
    asset_manifest = _read_json(manifest_path)
    review_required = (asset_manifest.get("metadata") or {}).get("review_required") or {}
    if review_required.get("type") != "reference_fidelity_review":
        raise JobError("This project is not waiting for reference-fidelity asset review.")

    generated_scene_ids = {str(asset.get("scene_id")) for asset in asset_manifest.get("assets") or []}
    expected_scene_ids = {str(scene.get("id")) for scene in scene_plan.get("scenes") or []}
    if generated_scene_ids != expected_scene_ids:
        _assert_budget_allows_remaining_batch(request_data, scene_plan, asset_manifest, generated_scene_ids)
        full_manifest = _generate_assets(project_id, project_dir, request_data, scene_plan, sample_only=False)
        _mark_reference_review_required(full_manifest, request_data, scene_plan, phase="full_batch")
        _write_json(manifest_path, full_manifest)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "assets",
            "awaiting_human",
            {"asset_manifest": full_manifest},
            pipeline_type="cinematic",
            human_approval_required=True,
            cost_snapshot=_cost_snapshot(full_manifest),
            review={
                "critical": 1,
                "suggestions": 0,
                "nitpicks": 0,
                "summary": "Review all generated clips for product/reference fidelity before compose.",
            },
            metadata={"source": "hosted_ui", "review_required": "reference_fidelity_full_batch"},
        )
        return {"ok": True, "project_id": project_id, "status": "full_batch_review_required"}

    asset_manifest.setdefault("metadata", {})["reference_fidelity_review"] = {
        "status": "approved",
        "approved_at": now_iso(),
    }
    asset_manifest["metadata"].pop("review_required", None)
    _write_json(manifest_path, asset_manifest)
    write_checkpoint(
        PROJECTS_DIR,
        project_id,
        "assets",
        "completed",
        {"asset_manifest": asset_manifest},
        pipeline_type="cinematic",
        human_approved=True,
        cost_snapshot=_cost_snapshot(asset_manifest),
        metadata={"source": "hosted_ui", "approval": "reference_fidelity_review_passed"},
    )
    edit_decisions, render_report = _compose(project_id, project_dir, asset_manifest, request_data, scene_plan)
    _write_json(project_dir / "artifacts" / "edit_decisions.json", edit_decisions)
    write_checkpoint(
        PROJECTS_DIR,
        project_id,
        "edit",
        "completed",
        {"edit_decisions": edit_decisions},
        pipeline_type="cinematic",
        metadata={"source": "hosted_ui"},
    )
    _write_json(project_dir / "artifacts" / "render_report.json", render_report)
    write_checkpoint(
        PROJECTS_DIR,
        project_id,
        "compose",
        "completed",
        {"render_report": render_report},
        pipeline_type="cinematic",
        metadata={"source": "hosted_ui"},
    )
    return {"ok": True, "project_id": project_id, "status": "completed"}


def validate_paid_generation_allowed(
    project_id: str,
    override_no_references: bool = False,
    confirm_seedance_risk: bool = False,
) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    request_data = _read_json(project_dir / "artifacts" / "job_request.json")
    proposal_path = project_dir / "artifacts" / "proposal_packet.json"
    if not proposal_path.is_file():
        plan_job(project_id)
    proposal_packet = _read_json(proposal_path)
    _refresh_reference_conditioning(proposal_packet, request_data)
    _write_json(proposal_path, proposal_packet)
    if _is_reference_blocked(proposal_packet) and not override_no_references:
        raise JobError(
            "This plan expects reference-conditioned generation but has zero usable reference images. "
            "Attach references first or pass override_no_references=true."
        )
    model_config = _video_model_config_from_request(request_data)
    if _requires_explicit_paid_approval(model_config) and not confirm_seedance_risk:
        raise JobError(
            "Seedance is not the Ray default and requires explicit Seedance risk approval before any paid call. "
            "Use Grok Imagine by default, or pass confirm_seedance_risk=true only after the user explicitly chooses Seedance."
        )
    _assert_budget_allows_paid_approval(request_data, proposal_packet)
    return proposal_packet


def retry_paid_generation(
    project_id: str,
    video_model: str,
    confirm_seedance_risk: bool = False,
) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    req_path = project_dir / "artifacts" / "job_request.json"
    request_data = _read_json(req_path)
    normalized = _normalize_video_model(video_model)
    model_config = _video_model_config(normalized)
    if not _has_any_env(model_config["requires_any_env"]):
        keys = " or ".join(model_config["requires_any_env"])
        raise JobError(f"{model_config['label']} requires {keys}. Choose another video model or configure the key.")
    aspect_ratio = str(request_data.get("aspect_ratio") or "16:9")
    if aspect_ratio not in model_config["aspects"]:
        supported = ", ".join(sorted(model_config["aspects"]))
        raise JobError(f"{model_config['label']} supports {supported} in this hosted build.")
    duration = int(request_data.get("duration_seconds") or 0)
    model_max_duration = min(MAX_DURATION_SECONDS, model_config["max_scene_seconds"] * MAX_SCENE_COUNT)
    if duration > model_max_duration:
        raise JobError(f"{model_config['label']} supports up to {model_max_duration} seconds in this hosted build.")

    request_data.update({
        "video_model": model_config["id"],
        "video_model_label": model_config["label"],
        "video_provider": model_config["provider"],
        "model_variant": model_config["model_variant"],
        "max_scene_seconds": model_config["max_scene_seconds"],
    })
    _write_json(req_path, request_data)
    scene_plan_path = project_dir / "artifacts" / "scene_plan.json"
    proposal_path = project_dir / "artifacts" / "proposal_packet.json"
    if scene_plan_path.is_file() and proposal_path.is_file():
        scene_plan = _read_json(scene_plan_path)
        proposal_packet = _read_json(proposal_path)
        proposal_packet["cost_estimate"] = _estimate_generation_cost(request_data, scene_plan)
        proposal_packet.setdefault("metadata", {})["video_model"] = model_config["id"]
        _refresh_reference_conditioning(proposal_packet, request_data)
        _write_json(proposal_path, proposal_packet)
    _append_provider_retry_decision(project_dir, project_id, model_config)
    return approve_paid_generation(project_id, confirm_seedance_risk=confirm_seedance_risk)


def _append_provider_retry_decision(project_dir: Path, project_id: str, model_config: dict[str, Any]) -> None:
    path = project_dir / "artifacts" / "decision_log.json"
    try:
        decision_log = _read_json(path)
    except Exception:
        decision_log = {"version": "1.0", "project_id": project_id, "decisions": []}
    selected = model_config["id"]
    options = []
    for config in sorted(VIDEO_MODELS.values(), key=lambda item: int(item.get("priority", 50))):
        options.append({
            "option_id": config["id"],
            "label": config["label"],
            "score": 0.9 if config["id"] == selected else 0.55,
            "reason": (
                "Selected for this explicit paid retry."
                if config["id"] == selected
                else "Available but not selected for this retry."
            ),
            **({} if config["id"] == selected else {"rejected_because": "User selected a different retry provider."}),
        })
    decision_log.setdefault("version", "1.0")
    decision_log.setdefault("project_id", project_id)
    decision_log.setdefault("decisions", []).append({
        "decision_id": f"d-retry-{int(time.time())}",
        "stage": "assets",
        "category": "provider_selection",
        "subject": "Video generation provider preference",
        "options_considered": options,
        "selected": selected,
        "reason": f"Retrying paid generation with {model_config['label']} after a provider output failure.",
        "user_visible": True,
        "user_approved": True,
        "confidence": 0.8,
    })
    _write_json(path, decision_log)


def run_job(project_id: str) -> None:
    approve_paid_generation(project_id)


def _legacy_run_job(project_id: str) -> None:
    project_dir = PROJECTS_DIR / project_id
    request_data = _read_json(project_dir / "artifacts" / "job_request.json")
    current_stage = "script"
    try:
        script_path = project_dir / "artifacts" / "script.json"
        scene_plan_path = project_dir / "artifacts" / "scene_plan.json"
        if script_path.is_file() and scene_plan_path.is_file():
            script = _read_json(script_path)
            scene_plan = _read_json(scene_plan_path)
        else:
            plan = _plan_with_llm(request_data)
            script, scene_plan = _artifacts_from_plan(request_data, plan)

            _write_json(script_path, script)
            write_checkpoint(
                PROJECTS_DIR,
                project_id,
                "script",
                "completed",
                {"script": script},
                pipeline_type="cinematic",
                human_approved=True,
                metadata={"auto_approved": True, "source": "hosted_ui"},
            )

            current_stage = "scene_plan"
            _write_json(scene_plan_path, scene_plan)
            write_checkpoint(
                PROJECTS_DIR,
                project_id,
                "scene_plan",
                "completed",
                {"scene_plan": scene_plan},
                pipeline_type="cinematic",
                human_approved=True,
                metadata={"auto_approved": True, "source": "hosted_ui"},
            )

        current_stage = "assets"
        asset_manifest = _generate_assets(project_id, project_dir, request_data, scene_plan)
        _write_json(project_dir / "artifacts" / "asset_manifest.json", asset_manifest)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "assets",
            "completed",
            {"asset_manifest": asset_manifest},
            pipeline_type="cinematic",
            human_approved=True,
            cost_snapshot=_cost_snapshot(asset_manifest),
            metadata={"auto_approved": True, "source": "hosted_ui"},
        )

        current_stage = "compose"
        edit_decisions, render_report = _compose(project_id, project_dir, asset_manifest, request_data, scene_plan)
        _write_json(project_dir / "artifacts" / "edit_decisions.json", edit_decisions)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "edit",
            "completed",
            {"edit_decisions": edit_decisions},
            pipeline_type="cinematic",
            metadata={"source": "hosted_ui"},
        )
        _write_json(project_dir / "artifacts" / "render_report.json", render_report)
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "compose",
            "completed",
            {"render_report": render_report},
            pipeline_type="cinematic",
            metadata={"source": "hosted_ui"},
        )
    except Exception as exc:
        _write_json(project_dir / "artifacts" / "job_error.json", {
            "version": "1.0",
            "error": str(exc),
            "failed_at": now_iso(),
        })
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            current_stage,
            "failed",
            {},
            pipeline_type="cinematic",
            error=str(exc),
            metadata={"source": "hosted_ui"},
        )


def _plan_with_llm(request_data: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("OPENROUTER_API_KEY"):
        return _chat_json(
            "https://openrouter.ai/api/v1/chat/completions",
            os.environ["OPENROUTER_API_KEY"],
            os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            request_data,
            extra_headers={
                "HTTP-Referer": os.environ.get("RAY_PUBLIC_URL", "https://ikawn-ray.fly.dev"),
                "X-Title": "iKawn Ray",
            },
        )
    if os.environ.get("OPENAI_API_KEY"):
        return _chat_json(
            "https://api.openai.com/v1/chat/completions",
            os.environ["OPENAI_API_KEY"],
            os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            request_data,
        )
    raise JobError("No LLM key configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY.")


def _chat_json(url: str, api_key: str, model: str, request_data: dict[str, Any], extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    scene_count = request_data["scene_count"]
    duration = request_data["duration_seconds"]
    model_config = _video_model_config_from_request(request_data)
    prompt = (
        "Return only JSON for a short cinematic video plan. "
        "Schema: {title:string, scenes:[{id:string,narration:string,visual_prompt:string,description:string,start_seconds:number,end_seconds:number}]}. "
        f"Create exactly {scene_count} scenes covering {duration} seconds. "
        f"Each scene may be up to {model_config['max_scene_seconds']} seconds. Prefer fewer longer scenes over many unrelated clips. "
        "Each scene must be one single continuous shot with one framing intent: no internal cuts, no montage inside a clip, no reframing drift. "
        "For product ads, scene 1 must open on the strongest product-detail hook, usually a macro fabric/detail shot, not a wide establishing shot. "
        "Do not use these visual words in any prompt: vignette, matte, frame, border. If you need softness, say shallow depth of field and edges softly falling out of focus. "
        "If slow motion is desired, describe graceful movement only; retiming happens in compose, not in the video-generation prompt. "
        "If reference_assets are present, plan a continuous reference-conditioned video: keep the same product, wardrobe, character/model, fabric, color palette, and brand world across every scene. "
        f"Each visual_prompt should be provider-ready for {model_config['label']} video generation, cinematic, concrete, and safe for commercial use. "
        "Do not include markdown."
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    response = requests.post(
        url,
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(request_data, ensure_ascii=True)},
            ],
            "temperature": 0.7,
        },
        timeout=90,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise JobError("LLM response did not contain JSON.")
    data = json.loads(content[start:end + 1])
    if not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise JobError("LLM plan did not include scenes.")
    return data


def _artifacts_from_plan(request_data: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    scenes = []
    sections = []
    for idx, scene in enumerate(plan["scenes"], start=1):
        sid = str(scene.get("id") or f"sc{idx}")
        start = float(scene.get("start_seconds", (idx - 1) * 5))
        end = float(scene.get("end_seconds", start + 5))
        narration = str(scene.get("narration") or scene.get("description") or "").strip()
        visual = _sanitize_visual_prompt(str(scene.get("visual_prompt") or scene.get("description") or request_data["prompt"]).strip())
        description = _sanitize_visual_prompt(str(scene.get("description") or visual))
        sections.append({
            "id": f"s{idx}",
            "label": f"Scene {idx}",
            "text": narration or visual,
            "start_seconds": start,
            "end_seconds": end,
        })
        scenes.append({
            "id": sid,
            "type": "generated",
            "description": description,
            "start_seconds": start,
            "end_seconds": end,
            "script_section_id": f"s{idx}",
            "required_assets": [{"type": "video", "description": visual, "source": "generate"}],
            "shot_intent": narration or visual,
            "narrative_role": "deliver_payload",
            "hero_moment": idx == min(len(plan["scenes"]), 2),
            "sequence_index": idx,
        })
    total = max(section["end_seconds"] for section in sections)
    return (
        {
            "version": "1.0",
            "title": str(plan.get("title") or request_data["title"]),
            "total_duration_seconds": total,
            "sections": sections,
            "metadata": {"source": "hosted_ui_llm"},
        },
        {
            "version": "1.0",
            "style_playbook": "clean-professional",
            "scenes": scenes,
            "metadata": {"source": "hosted_ui_llm"},
        },
    )


def _proposal_from_plan(
    project_id: str,
    request_data: dict[str, Any],
    script: dict[str, Any],
    scene_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_config = _video_model_config_from_request(request_data)
    estimate = _estimate_generation_cost(request_data, scene_plan)
    title = request_data["title"]
    duration = float(script.get("total_duration_seconds") or request_data["duration_seconds"])
    platform = "instagram" if request_data.get("aspect_ratio") == "9:16" else "youtube"
    refs_expected = _reference_conditioning_expected(request_data)
    reference_count = _reference_asset_count(request_data)
    conditioning_mode = _conditioning_mode(request_data)
    concept_grounding = ["hosted user brief", "uploaded references"] if refs_expected else ["hosted user brief"]
    visual_approach = (
        "Reference-conditioned cinematic product film with fewer, longer clips and stable visual anchors."
        if refs_expected
        else "Cinematic product film from the written brief with fewer, longer clips and stable visual direction."
    )
    key_reference_point = (
        "Use uploaded references as the visual source of truth."
        if refs_expected
        else "Use the approved written brief as the visual source of truth."
    )
    concepts = [
        {
            "id": "c1",
            "title": title,
            "hook": _short_hook(request_data["prompt"]),
            "narrative_structure": "story",
            "visual_approach": visual_approach,
            "suggested_playbook": "clean-professional",
            "target_audience": "Client-ready social and YouTube viewers",
            "target_platform": platform,
            "target_duration_seconds": duration,
            "key_points": [
                key_reference_point,
                "Keep the same product, character, wardrobe, and brand world across scenes.",
            ],
            "core_message": "A polished video should preserve the supplied visual identity instead of drifting scene by scene.",
            "cta": "Use as a reviewed campaign draft after asset approval.",
            "tone": "premium, coherent, cinematic",
            "grounded_in": concept_grounding,
            "why_this_works": "It minimizes clip count and treats references as production anchors, reducing the chance of disconnected generations.",
        },
        {
            "id": "c2",
            "title": f"{title} - direct product cut",
            "hook": "Show the product clearly before adding mood.",
            "narrative_structure": "problem_solution",
            "visual_approach": "Direct ad structure: establish product, show detail, show use context, land on CTA.",
            "suggested_playbook": "premium-minimalist",
            "target_audience": "Prospects evaluating the product visually",
            "target_platform": platform,
            "target_duration_seconds": duration,
            "key_points": ["Lead with clarity.", "Use references as consistency anchors."],
            "core_message": "The product remains the hero throughout the video.",
            "cta": "Review the generated clips before final compose.",
            "tone": "clear, controlled, commercial",
            "grounded_in": ["hosted user brief"],
            "why_this_works": "It favors product legibility and reduces creative randomness.",
        },
        {
            "id": "c3",
            "title": f"{title} - cinematic mood cut",
            "hook": "Make the brand feel premium before making the offer.",
            "narrative_structure": "journey",
            "visual_approach": "Mood-led sequence with slow camera movement, tactile details, and a restrained closing beat.",
            "suggested_playbook": "clean-professional",
            "target_audience": "Brand-conscious social viewers",
            "target_platform": platform,
            "target_duration_seconds": duration,
            "key_points": ["Build mood through motion.", "Keep references consistent across shots."],
            "core_message": "The brand feels cohesive and premium.",
            "cta": "Approve only after reviewing the storyboard and cost.",
            "tone": "cinematic, elegant, polished",
            "grounded_in": ["hosted user brief"],
            "why_this_works": "It can look more premium, but it needs careful clip review to avoid style drift.",
        },
    ]
    proposal_packet = {
        "version": "1.0",
        "concept_options": concepts,
        "selected_concept": {
            "concept_id": "c1",
            "rationale": "Best fit for uploaded-reference jobs where identity and product consistency matter more than raw prompt variety.",
        },
        "production_plan": {
            "pipeline": "cinematic",
            "playbook": "clean-professional",
            "stages": [
                {
                    "stage": "proposal",
                    "tools": [],
                    "approach": "Generate a safe plan, cost estimate, and approval gate before any provider video call.",
                },
                {
                    "stage": "script",
                    "tools": [{"tool_name": "openrouter_chat", "role": "Draft timed sections", "provider": "openrouter", "available": bool(os.environ.get("OPENROUTER_API_KEY")), "estimated_cost_usd": 0.0, "why_this_provider": "Already configured for planning."}],
                    "approach": "Create a timestamped script from the user brief.",
                },
                {
                    "stage": "scene_plan",
                    "tools": [{"tool_name": "openrouter_chat", "role": "Draft scene plan", "provider": "openrouter", "available": bool(os.environ.get("OPENROUTER_API_KEY")), "estimated_cost_usd": 0.0, "why_this_provider": "Used only for planning, not video generation."}],
                    "approach": "Create a storyboard with one generated video asset request per scene.",
                },
                {
                    "stage": "assets",
                    "tools": [{
                        "tool_name": model_config["tool_name"],
                        "role": "Generate reference-conditioned video clips after explicit approval",
                        "provider": model_config["provider_label"],
                        "available": _has_any_env(model_config["requires_any_env"]),
                        "estimated_cost_usd": estimate["total_estimated_usd"],
                        "why_this_provider": "Selected by the user or hosted default; actual generation waits for approval.",
                    }],
                    "approach": "Generate clips only after the user approves the plan and budget.",
                    "fallback_if_unavailable": "Stop and ask for a different provider or missing API key.",
                },
                {
                    "stage": "compose",
                    "tools": [{"tool_name": "ffmpeg", "role": "Post-compose approved clips with crossfades, music bed, end card, loudness normalization, and 1080x1920 output", "provider": "local", "available": True, "estimated_cost_usd": 0.0, "why_this_provider": "Local post composition does not spend API credits."}],
                    "approach": "Finish generated clips locally with real post-production and upload final output to R2.",
                },
            ],
            "quality_tradeoffs": [
                {
                    "tradeoff": "Fewer longer clips reduce API calls and improve continuity, but each generated clip still needs human review.",
                    "recommendation": "Approve only if the storyboard and budget look acceptable.",
                    "quality_impact": "Lower risk of fragmented videos than many short clips.",
                }
            ],
            "alternative_paths": [
                {"description": "Grok Imagine reference-conditioned clips via fal.ai", "total_cost_usd": round(duration * 0.07, 2), "quality_level": "standard", "what_changes": "Uses the configured Fal key for xAI Grok Imagine endpoints."},
                {"description": "Kling 3 via Fal", "total_cost_usd": round((duration / 5) * 0.10, 2), "quality_level": "standard", "what_changes": "Uses single-image image-to-video when references exist; not multi-reference conditioning."},
                {"description": "Veo 3.1 reference-conditioned clips", "total_cost_usd": estimate["total_estimated_usd"], "quality_level": "standard", "what_changes": "Uses existing Fal setup with explicit approval gate."},
                {"description": "Plan only", "total_cost_usd": 0.0, "quality_level": "free", "what_changes": "No video clips are generated."},
                {"description": "Seedance 2.0 opt-in only", "total_cost_usd": estimate["total_estimated_usd"], "quality_level": "standard", "what_changes": "Requires separate Seedance risk approval before any paid call."},
            ],
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "source_required": refs_expected,
                "tone_mode": "cinematic commercial",
                "quality_floor": "presentable",
                "approved_fallback": None,
            },
            "renderer_family": "cinematic-trailer",
            "render_runtime": "ffmpeg",
            "music_source": {
                "source_type": "ai_generated",
                "provider": "local_ffmpeg",
                "mood_direction": "Sparse drone and subtle pulse generated locally, then loudness-normalized in compose.",
                "estimated_cost_usd": 0,
            },
        },
        "cost_estimate": estimate,
        "approval": {"status": "pending"},
        "metadata": {
            "source": "hosted_ray_safe_plan",
            "video_model": request_data.get("video_model"),
            "fal_spend_before_approval_usd": 0,
            "reference_conditioning_expected": refs_expected,
            "reference_asset_count": reference_count,
            "conditioning_mode": conditioning_mode,
        },
    }
    _refresh_reference_conditioning(proposal_packet, request_data)
    decision_log = _decision_log_from_request(project_id, request_data, model_config, estimate)
    return proposal_packet, decision_log


def _decision_log_from_request(
    project_id: str,
    request_data: dict[str, Any],
    model_config: dict[str, Any],
    estimate: dict[str, Any],
) -> dict[str, Any]:
    selected = model_config["id"]
    options = []
    for config in sorted(VIDEO_MODELS.values(), key=lambda item: int(item.get("priority", 50))):
        selected_config = config["id"] == selected
        seedance_ack = bool(config.get("requires_explicit_paid_approval"))
        options.append({
            "option_id": config["id"],
            "label": config["label"],
            "score": 0.9 if selected_config else max(0.45, 0.8 - (int(config.get("priority", 50)) * 0.04)),
            "reason": (
                "Selected for this run; this is Ray's hosted default."
                if selected_config and config["id"] == DEFAULT_VIDEO_MODEL
                else "Selected for this run."
                if selected_config
                else "Available as an alternate provider preference."
            ),
            **(
                {"rejected_because": "Required API key is not configured."}
                if not _has_any_env(config["requires_any_env"])
                else {"rejected_because": "Seedance requires explicit provider-risk approval before paid generation."}
                if seedance_ack and not selected_config
                else {}
            ),
        })
    return {
        "version": "1.0",
        "project_id": project_id,
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "proposal",
                "category": "provider_selection",
                "subject": "Video generation provider preference",
                "options_considered": options,
                "selected": selected,
                "reason": f"{model_config['label']} is the selected provider preference; no paid calls run before approval.",
                "user_visible": True,
                "user_approved": False,
                "confidence": 0.8,
            },
            {
                "decision_id": "d-002",
                "stage": "proposal",
                "category": "budget_tradeoff",
                "subject": "Paid generation approval gate",
                "options_considered": [
                    {"option_id": "safe_plan", "label": "Plan only", "score": 1.0, "reason": "Costs no Fal credits before approval."},
                    {"option_id": "paid_generation", "label": "Generate clips now", "score": 0.2, "reason": "Would spend provider credits before review.", "rejected_because": "Requires explicit user approval."},
                ],
                "selected": "safe_plan",
                "reason": f"Estimated video generation cost is {estimate['total_estimated_usd']:.2f} USD, so the hosted app pauses first.",
                "user_visible": True,
                "user_approved": False,
                "confidence": 1.0,
            },
            {
                "decision_id": "d-003",
                "stage": "proposal",
                "category": "render_runtime_selection",
                "subject": "Initial hosted composition runtime",
                "options_considered": [
                    {"option_id": "ffmpeg", "label": "FFmpeg post-compose", "score": 0.82, "reason": "Local, no API spend, supports clip trims, crossfades, synthetic music, end card, and 1080x1920 output."},
                    {"option_id": "remotion", "label": "Remotion", "score": 0.6, "reason": "Better composition path, pending adapter integration."},
                    {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.55, "reason": "Good for bespoke motion, pending adapter integration."},
                ],
                "selected": "ffmpeg",
                "reason": "This hosted path spends only on explicitly approved generation while still doing real local post-production.",
                "user_visible": True,
                "user_approved": False,
                "confidence": 0.65,
            },
        ],
    }


def _estimate_generation_cost(request_data: dict[str, Any], scene_plan: dict[str, Any]) -> dict[str, Any]:
    model_config = _video_model_config_from_request(request_data)
    tool = _video_tool(model_config)
    reference_image_urls = _reference_image_urls(request_data, limit=_reference_limit(model_config))
    operation = _video_operation(model_config, reference_image_urls)
    conditioning_mode = "image_to_video" if reference_image_urls else "text_to_video"
    line_items = []
    total = 0.0
    scenes = scene_plan.get("scenes") or []
    for idx, scene in enumerate(scenes, start=1):
        duration = _scene_duration_seconds(scene, request_data, len(scenes), model_config)
        prompt = _video_prompt(request_data, scene, model_config, reference_image_urls, scene_index=idx)
        inputs = {
            "prompt": prompt,
            "operation": operation,
            "duration": _duration_value(model_config, duration),
            "aspect_ratio": request_data.get("aspect_ratio", "16:9"),
            "resolution": model_config["resolution"],
            "generate_audio": True,
        }
        if model_config["provider"] in {"seedance", "veo", "kling"}:
            inputs["model_variant"] = model_config["model_variant"]
        if model_config["provider"] == "grok":
            inputs["model"] = model_config["model_variant"]
        if reference_image_urls:
            if operation == "image_to_video":
                inputs["image_url"] = reference_image_urls[0]
            else:
                inputs["reference_image_urls"] = reference_image_urls
        cost = float(tool.estimate_cost(inputs) or 0)
        total += cost
        line_items.append({
            "scene_id": str(scene.get("id") or f"scene_{idx}"),
            "tool": model_config["tool_name"],
            "operation": f"{operation} scene {scene.get('id')}",
            "quantity": 1,
            "estimated_usd": round(cost, 2),
            "notes": f"{model_config['label']} {duration}s clip. Estimate only; no provider call has run.",
        })
    initial_estimate = round(line_items[0]["estimated_usd"], 2) if line_items and _reference_conditioning_expected(request_data) and len(reference_image_urls) else round(total, 2)
    sample_first = bool(line_items and _reference_conditioning_expected(request_data) and len(reference_image_urls))
    budget_cap = _budget_cap_from_request(request_data)
    budget_verdict = _budget_verdict(round(total, 2), initial_estimate, sample_first, budget_cap)
    return {
        "total_estimated_usd": round(total, 2),
        "initial_paid_generation_estimate_usd": initial_estimate,
        "sample_first": sample_first,
        "conditioning_mode": conditioning_mode,
        "reference_asset_count": len(reference_image_urls),
        "reference_conditioning_expected": _reference_conditioning_expected(request_data),
        "line_items": line_items,
        "budget_cap_usd": budget_cap,
        "budget_verdict": budget_verdict,
        "budget_remaining_usd": round(budget_cap - round(total, 2), 2) if budget_cap is not None else None,
        "savings_options": [
            "Shorten the duration.",
            "Use fewer scenes with longer clips where the provider supports it.",
            "Keep the run in plan-only mode until the storyboard is acceptable.",
        ],
    }


def _proposal_cost_snapshot(proposal_packet: dict[str, Any]) -> dict[str, Any]:
    estimate = float(proposal_packet.get("cost_estimate", {}).get("total_estimated_usd") or 0)
    cap = _coerce_optional_budget_cap((proposal_packet.get("cost_estimate") or {}).get("budget_cap_usd"))
    return {
        "total_spent_usd": 0,
        "total_reserved_usd": round(estimate, 2),
        "budget_remaining_usd": round(cap - estimate, 2) if cap is not None else 0,
    }


def _budget_cap_from_request(request_data: dict[str, Any]) -> float | None:
    return _coerce_optional_budget_cap(request_data.get("budget_cap_usd"))


def _budget_verdict(total: float, initial: float, sample_first: bool, cap: float | None) -> str:
    if cap is None:
        return "no_budget_set"
    if total <= cap:
        return "within_budget"
    if sample_first and initial <= cap:
        return "sample_within_budget_full_batch_exceeds"
    return "exceeds_budget"


def _assert_budget_allows_paid_approval(request_data: dict[str, Any], proposal_packet: dict[str, Any]) -> None:
    cap = _budget_cap_from_request(request_data)
    if cap is None:
        return
    estimate = proposal_packet.get("cost_estimate") or {}
    sample_first = estimate.get("sample_first") is True
    next_spend = float(
        estimate.get("initial_paid_generation_estimate_usd" if sample_first else "total_estimated_usd")
        or 0
    )
    if next_spend > cap:
        raise JobError(
            f"Budget cap would be exceeded before paid generation: next approved spend "
            f"${next_spend:.2f} > cap ${cap:.2f}."
        )


def _assert_budget_allows_projected_spend(request_data: dict[str, Any], projected_total: float) -> None:
    cap = _budget_cap_from_request(request_data)
    if cap is None:
        return
    if projected_total > cap:
        raise JobError(
            f"Budget cap would be exceeded before provider call: projected spend "
            f"${projected_total:.2f} > cap ${cap:.2f}."
        )


def _assert_budget_allows_remaining_batch(
    request_data: dict[str, Any],
    scene_plan: dict[str, Any],
    asset_manifest: dict[str, Any],
    generated_scene_ids: set[str],
) -> None:
    cap = _budget_cap_from_request(request_data)
    if cap is None:
        return
    estimate = _estimate_generation_cost(request_data, scene_plan)
    remaining_estimate = 0.0
    for item in estimate.get("line_items") or []:
        if str(item.get("scene_id") or "") not in generated_scene_ids:
            remaining_estimate += float(item.get("estimated_usd") or 0)
    spent = float(asset_manifest.get("total_cost_usd") or 0)
    _assert_budget_allows_projected_spend(request_data, spent + remaining_estimate)


def _reference_conditioning_expected(request_data: dict[str, Any]) -> bool:
    if request_data.get("reference_conditioning_expected") is True:
        return True
    if _reference_asset_count(request_data) > 0:
        return True
    prompt = str(request_data.get("prompt") or "").lower()
    patterns = (
        r"\battached\b",
        r"\buploaded\b",
        r"\breference(?:s| images?| stills?| photos?)?\b",
        r"\bprovided (?:images?|photos?|stills?)\b",
        r"\bfaithful to\b",
        r"\bactual product\b",
        r"\bclient'?s? (?:actual )?(?:product|saree|garment)\b",
        r"\bsame (?:product|saree|garment|fabric|model|person|wardrobe)\b",
        r"\bkeep (?:the )?(?:product|saree|garment|fabric|model|person|wardrobe) (?:same|consistent)\b",
    )
    return any(re.search(pattern, prompt) for pattern in patterns)


def _reference_asset_count(request_data: dict[str, Any]) -> int:
    return len(_reference_image_urls(request_data, limit=1000))


def _conditioning_mode(request_data: dict[str, Any]) -> str:
    return "image_to_video" if _reference_asset_count(request_data) > 0 else "text_to_video"


def _refresh_reference_conditioning(proposal_packet: dict[str, Any], request_data: dict[str, Any]) -> None:
    expected = _reference_conditioning_expected(request_data)
    count = _reference_asset_count(request_data)
    mode = "image_to_video" if count else "text_to_video"
    model_config = _video_model_config_from_request(request_data)
    seedance_requires_ack = _requires_explicit_paid_approval(model_config)
    proposal_packet["reference_asset_count"] = count
    proposal_packet["conditioning_mode"] = mode
    proposal_packet["reference_conditioning_expected"] = expected
    proposal_packet.setdefault("metadata", {})["reference_asset_count"] = count
    proposal_packet["metadata"]["conditioning_mode"] = mode
    proposal_packet["metadata"]["reference_conditioning_expected"] = expected
    proposal_packet["metadata"]["default_video_model"] = DEFAULT_VIDEO_MODEL
    proposal_packet["metadata"]["requires_explicit_seedance_approval"] = seedance_requires_ack
    proposal_packet.setdefault("production_plan", {}).setdefault("delivery_promise", {})["source_required"] = expected
    cost_estimate = proposal_packet.setdefault("cost_estimate", {})
    cost_estimate["reference_asset_count"] = count
    cost_estimate["conditioning_mode"] = mode
    cost_estimate["reference_conditioning_expected"] = expected

    approval = proposal_packet.setdefault("approval", {})
    approval["requires_explicit_seedance_approval"] = seedance_requires_ack
    if seedance_requires_ack:
        approval["provider_warning"] = (
            "Seedance is opt-in only in this hosted Ray build after the failed reference-fidelity run. "
            "Paid generation requires confirm_seedance_risk=true."
        )
    else:
        approval.pop("provider_warning", None)
    if expected and count == 0:
        approval["status"] = "blocked"
        approval["reason"] = "reference_conditioning_expected_but_no_assets"
        approval["message"] = (
            "This brief expects reference-conditioned video, but no usable reference images are attached. "
            "Attach references before approving paid generation, or explicitly override."
        )
    elif approval.get("status") == "blocked" and approval.get("reason") == "reference_conditioning_expected_but_no_assets":
        approval["status"] = "pending"
        approval.pop("reason", None)
        approval.pop("message", None)


def _is_reference_blocked(proposal_packet: dict[str, Any]) -> bool:
    approval = proposal_packet.get("approval") or {}
    return approval.get("status") == "blocked" and approval.get("reason") == "reference_conditioning_expected_but_no_assets"


def _requires_explicit_paid_approval(model_config: dict[str, Any]) -> bool:
    return bool(model_config.get("requires_explicit_paid_approval"))


def _short_hook(prompt: str) -> str:
    first = re.sub(r"\s+", " ", prompt).strip().splitlines()[0]
    return first[:96] or "A concise visual story built from the supplied brief."


def _provider_error_type(result: Any) -> str | None:
    data = getattr(result, "data", None)
    if isinstance(data, dict) and data.get("provider_error_type"):
        return str(data["provider_error_type"])
    error = str(getattr(result, "error", "") or "")
    if "no_media_generated" in error:
        return "no_media_generated"
    return None


def _is_no_media_generated(result: Any) -> bool:
    return _provider_error_type(result) == "no_media_generated"


def _blocked_asset_manifest(
    request_data: dict[str, Any],
    model_config: dict[str, Any],
    scene: dict[str, Any],
    prompt: str,
    result: Any,
    assets: list[dict[str, Any]],
    r2_assets: list[dict[str, Any]],
    total_cost: float,
) -> dict[str, Any]:
    result_data = getattr(result, "data", None)
    provider_error = result_data.get("provider_error") if isinstance(result_data, dict) else None
    return {
        "version": "1.0",
        "assets": assets,
        "total_cost_usd": round(total_cost, 2),
        "metadata": {
            "r2_assets": r2_assets,
            "blocked": True,
            "blocker": {
                "type": "provider_no_media_generated",
                "stage": "assets",
                "scene_id": scene["id"],
                "provider": model_config["provider_label"],
                "model": model_config["model_variant"],
                "video_model": request_data.get("video_model"),
                "message": getattr(result, "error", None) or "Provider returned no media.",
                "recommendation": (
                    "Switch this run to Grok Imagine via Fal or revise the prompt/reference set before spending more."
                ),
                "retry_options": [
                    {
                        "video_model": "kling-v3",
                        "label": "Retry with Kling 3 via Fal",
                        "why": "Higher priority option, but this hosted adapter uses only one reference image.",
                    },
                    {
                        "video_model": "grok-imagine-video",
                        "label": "Retry with Grok Imagine via Fal",
                        "why": "Fal-backed xAI reference-to-video is a better fit for product and wardrobe consistency.",
                    },
                    {
                        "video_model": "veo3.1-fast",
                        "label": "Retry Veo with safer prompt",
                        "why": "Uses the corrected Veo reference prompt, but Veo may reject the same inputs again.",
                    },
                ],
                "prompt": prompt,
                "provider_error": provider_error,
            },
        },
    }


def _blocked_asset_manifest_from_qa(
    request_data: dict[str, Any],
    model_config: dict[str, Any],
    scene: dict[str, Any],
    prompt: str,
    qa_checks: dict[str, Any],
    result: Any,
    generation_inputs: dict[str, Any],
    assets: list[dict[str, Any]],
    r2_assets: list[dict[str, Any]],
    total_cost: float,
) -> dict[str, Any]:
    result_data = getattr(result, "data", None)
    return {
        "version": "1.0",
        "assets": assets,
        "total_cost_usd": round(total_cost, 2),
        "metadata": {
            "r2_assets": r2_assets,
            "blocked": True,
            "blocker": {
                "type": "asset_qa_dimension_mismatch",
                "stage": "assets",
                "scene_id": scene["id"],
                "provider": model_config["provider_label"],
                "model": model_config["model_variant"],
                "video_model": request_data.get("video_model"),
                "message": (
                    "Generated clip dimensions do not match the planned aspect ratio. "
                    "The clip was not accepted into the asset manifest."
                ),
                "qa_checks": qa_checks,
                "prompt": prompt,
                "generation_inputs": {
                    key: generation_inputs.get(key)
                    for key in (
                        "operation",
                        "preferred_provider",
                        "duration",
                        "aspect_ratio",
                        "resolution",
                        "reference_frame_preprocess",
                        "original_reference_image_url",
                    )
                    if generation_inputs.get(key) is not None
                },
                "result": result_data if isinstance(result_data, dict) else {},
                "recommendation": (
                    "Regenerate after fixing start-frame aspect handling, or switch to a provider that preserves "
                    "the required vertical output for this product."
                ),
            },
        },
    }


def _aspect_ratio_value(aspect_ratio: Any) -> float | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$", str(aspect_ratio or ""))
    if not match:
        return None
    width = float(match.group(1))
    height = float(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return width / height


def _target_dimensions_for_aspect(aspect_ratio: Any) -> tuple[int, int] | None:
    value = str(aspect_ratio or "").strip()
    presets = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }
    if value in presets:
        return presets[value]
    ratio = _aspect_ratio_value(value)
    if not ratio:
        return None
    height = 1080
    return max(1, round(height * ratio)), height


def _prepare_kling_reference_frame(
    project_dir: Path,
    scene_id: str,
    image_url: str,
    aspect_ratio: str,
) -> Path:
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except Exception as exc:
        raise JobError(f"Pillow is required to prepare Kling reference frames: {exc}") from exc

    target = _target_dimensions_for_aspect(aspect_ratio)
    if not target:
        raise JobError(f"Cannot prepare Kling reference frame for unsupported aspect ratio: {aspect_ratio}")

    try:
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as exc:
        raise JobError(f"Failed to load Kling reference image before paid generation: {exc}") from exc

    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    background = ImageOps.fit(image, target, method=resampling)
    background = background.filter(ImageFilter.GaussianBlur(radius=max(target) / 32))
    background = ImageEnhance.Brightness(background).enhance(0.92)

    foreground = image.copy()
    foreground.thumbnail(target, resampling)
    x = (target[0] - foreground.width) // 2
    y = (target[1] - foreground.height) // 2
    background.paste(foreground, (x, y))

    output = project_dir / "assets" / "references" / f"{scene_id}_kling_{str(aspect_ratio).replace(':', 'x')}_start.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    background.save(output, "PNG", optimize=True)
    return output


def _apply_model_specific_generation_inputs(
    generation_inputs: dict[str, Any],
    model_config: dict[str, Any],
    request_data: dict[str, Any],
    project_dir: Path,
    scene_id: str,
    all_reference_image_urls: list[str],
    previous_last_frame_path: Path | None,
) -> None:
    if model_config["provider"] != "kling":
        return

    generation_inputs["negative_prompt"] = (
        "generic floral print, plain fabric, changed saree, changed blouse, redesigned motifs, "
        "watercolor smudge, blurry print, low detail, text, logo, caption, extra person"
    )
    generation_inputs["cfg_scale"] = 0.75
    if all_reference_image_urls:
        generation_inputs["elements"] = [{
            "frontal_image_url": all_reference_image_urls[0],
            "reference_image_urls": all_reference_image_urls[1:4],
        }]

    if (
        generation_inputs.get("operation") == "image_to_video"
        and generation_inputs.get("image_url")
        and not previous_last_frame_path
    ):
        original_url = str(generation_inputs["image_url"])
        prepared = _prepare_kling_reference_frame(
            project_dir,
            scene_id,
            original_url,
            str(generation_inputs.get("aspect_ratio") or request_data.get("aspect_ratio") or "16:9"),
        )
        generation_inputs["reference_image_path"] = str(prepared)
        generation_inputs["original_reference_image_url"] = original_url
        generation_inputs["reference_frame_preprocess"] = {
            "provider": "kling",
            "version": "kling-start-frame-aspect-pad-v1",
            "source_url": original_url,
            "prepared_path": str(prepared.relative_to(project_dir)),
            "target_aspect_ratio": generation_inputs.get("aspect_ratio") or request_data.get("aspect_ratio"),
            "strategy": "blurred-cover-background-with-contained-reference",
        }
        generation_inputs.pop("image_url", None)
        generation_inputs.pop("reference_image_url", None)


def _generate_assets(
    project_id: str,
    project_dir: Path,
    request_data: dict[str, Any],
    scene_plan: dict[str, Any],
    *,
    sample_only: bool = False,
) -> dict[str, Any]:
    model_config = _video_model_config_from_request(request_data)
    from tools.video.video_selector import VideoSelector

    selector = VideoSelector()
    assets: list[dict[str, Any]] = []
    r2_assets: list[dict[str, Any]] = []
    generation_runs: list[dict[str, Any]] = []
    chain_frames: list[dict[str, Any]] = []
    total_cost = 0.0
    scenes = scene_plan["scenes"]
    scenes_to_generate = scenes[:1] if sample_only and scenes else scenes
    reference_limit = _reference_limit(model_config)
    all_reference_image_urls = _reference_image_urls(request_data, limit=max(7, reference_limit))
    reference_image_urls = all_reference_image_urls[:reference_limit]
    previous_last_frame_path: Path | None = None
    write_checkpoint(PROJECTS_DIR, project_id, "assets", "in_progress", {}, pipeline_type="cinematic")
    for idx, scene in enumerate(scenes_to_generate, start=1):
        rel = f"assets/video/{scene['id']}.mp4"
        out = project_dir / rel
        chain_source_for_scene = previous_last_frame_path
        operation = _video_operation_for_scene(model_config, reference_image_urls, chain_source_for_scene, idx)
        duration = _scene_duration_seconds(scene, request_data, len(scenes), model_config)
        prompt = _video_prompt(request_data, scene, model_config, reference_image_urls, scene_index=idx)
        duration_value = _duration_value(model_config, duration)
        generation_signature = _generation_signature(
            prompt=prompt,
            operation=operation,
            request_data=request_data,
            duration=duration,
            video_model=model_config["id"],
            reference_image_urls=reference_image_urls,
        )
        generation_signature["chain_source_hash"] = _file_sha1(chain_source_for_scene) if chain_source_for_scene else ""
        if model_config["provider"] == "kling":
            generation_signature["all_reference_hash"] = hashlib.sha1(
                "\n".join(all_reference_image_urls).encode("utf-8")
            ).hexdigest()
            generation_signature["reference_frame_preprocess_version"] = "kling-start-frame-aspect-pad-v1"
        reused = out.is_file() and out.stat().st_size > 0 and _clip_metadata_matches(out, generation_signature)
        result = None
        generation_inputs: dict[str, Any] = {}
        reused_cost = _event_cost_for_scene(project_dir, scene["id"]) if reused else 0.0
        if not reused:
            generation_inputs = {
                "prompt": prompt,
                "operation": operation,
                "preferred_provider": model_config["provider"],
                "allowed_providers": [model_config["provider"]],
                "duration": duration_value,
                "aspect_ratio": request_data.get("aspect_ratio", "16:9"),
                "resolution": model_config["resolution"],
                "generate_audio": True,
                "output_path": str(out),
                "project_dir": str(project_dir),
                "scene_id": scene["id"],
            }
            if model_config["provider"] == "seedance":
                generation_inputs["model_variant"] = model_config["model_variant"]
            elif model_config["provider"] == "veo":
                generation_inputs["model_variant"] = model_config["model_variant"]
                generation_inputs["auto_fix"] = True
                generation_inputs["safety_tolerance"] = "4"
            elif model_config["provider"] == "kling":
                generation_inputs["model_variant"] = model_config["model_variant"]
            elif model_config["provider"] == "grok":
                generation_inputs["model"] = model_config["model_variant"]
            _apply_reference_and_chain_inputs(
                generation_inputs,
                model_config,
                reference_image_urls,
                chain_source_for_scene,
                scene_index=idx,
            )
            estimated_scene_cost = float(_video_tool(model_config).estimate_cost(generation_inputs) or 0)
            _assert_budget_allows_projected_spend(request_data, total_cost + estimated_scene_cost)
            _apply_model_specific_generation_inputs(
                generation_inputs,
                model_config,
                request_data,
                project_dir,
                scene["id"],
                all_reference_image_urls,
                chain_source_for_scene,
            )
            result = selector.execute(generation_inputs)
            if not result.success:
                if _is_no_media_generated(result):
                    asset_manifest = _blocked_asset_manifest(
                        request_data,
                        model_config,
                        scene,
                        prompt,
                        result,
                        assets,
                        r2_assets,
                        total_cost,
                    )
                    _write_json(project_dir / "artifacts" / "asset_manifest.json", asset_manifest)
                    write_checkpoint(
                        PROJECTS_DIR,
                        project_id,
                        "assets",
                        "awaiting_human",
                        {"asset_manifest": asset_manifest},
                        pipeline_type="cinematic",
                        cost_snapshot=_cost_snapshot(asset_manifest),
                        error=result.error or f"Video generation produced no media for {scene['id']}",
                        metadata={"source": "hosted_ui", "blocker": "provider_no_media_generated"},
                    )
                    raise JobAwaitingHuman(
                        f"{model_config['label']} produced no media for {scene['id']}; waiting for an explicit retry choice."
                    )
                raise JobError(result.error or f"Video generation failed for {scene['id']}")
            _write_json(_clip_metadata_path(out), {
                "version": "1.0",
                "generated_at": now_iso(),
                **generation_signature,
            })
        scene_cost = float((result.cost_usd if result else reused_cost) or 0)
        qa_checks = _qa_video_clip(
            out,
            duration,
            expected_aspect_ratio=request_data.get("aspect_ratio", "16:9"),
        )
        if not qa_checks.get("dimensions_ok", True):
            asset_manifest = _blocked_asset_manifest_from_qa(
                request_data,
                model_config,
                scene,
                prompt,
                qa_checks,
                result,
                generation_inputs,
                assets,
                r2_assets,
                total_cost + scene_cost,
            )
            _write_json(project_dir / "artifacts" / "asset_manifest.json", asset_manifest)
            write_checkpoint(
                PROJECTS_DIR,
                project_id,
                "assets",
                "awaiting_human",
                {"asset_manifest": asset_manifest},
                pipeline_type="cinematic",
                cost_snapshot=_cost_snapshot(asset_manifest),
                error=f"Generated clip dimensions do not match planned aspect ratio for {scene['id']}",
                metadata={"source": "hosted_ui", "blocker": "asset_qa_dimension_mismatch"},
            )
            raise JobAwaitingHuman(
                f"Generated clip dimensions do not match planned aspect ratio for {scene['id']}; "
                "asset manifest acceptance is blocked."
            )
        frame_rel = f"assets/chaining/{scene['id']}_last.jpg"
        frame_path = project_dir / frame_rel
        if _extract_last_frame(out, frame_path):
            previous_last_frame_path = frame_path
            chain_upload = storage.upload_file(frame_path, project_id, frame_rel)
            chain_frames.append({
                "scene_id": scene["id"],
                "path": frame_rel,
                **chain_upload,
            })
        else:
            previous_last_frame_path = None
        upload = storage.upload_file(out, project_id, rel)
        r2_assets.append({"path": rel, **upload})
        total_cost += scene_cost
        result_data = result.data if result is not None and isinstance(result.data, dict) else {}
        generation_runs.append({
            "scene_id": scene["id"],
            "selector": "video_selector",
            "selected_tool": result_data.get("selected_tool") or model_config["tool_name"],
            "selected_provider": result_data.get("selected_provider") or model_config["provider"],
            "operation": operation,
            "chaining_mode": _chaining_mode_for_scene(model_config, chain_source_for_scene, idx),
            "chain_source_used": bool(idx > 1 and chain_source_for_scene),
            "output_path": rel,
            "cost_usd": scene_cost,
            "qa_checks": qa_checks,
            **(
                {"reference_frame_preprocess": generation_inputs.get("reference_frame_preprocess")}
                if generation_inputs.get("reference_frame_preprocess")
                else {}
            ),
        })
        assets.append({
            "id": f"vid_{scene['id']}",
            "type": "video",
            "path": rel,
            "source_tool": result_data.get("selected_tool") or "video_selector",
            "scene_id": scene["id"],
            "prompt": prompt,
            "model": (result.model if result else None) or result_data.get("model") or model_config["model_variant"],
            "cost_usd": scene_cost,
            "duration_seconds": float((result.data.get("duration_seconds") if result else 0) or duration),
            "resolution": (result.data.get("resolution") if result else None) or model_config["resolution"],
            "format": "mp4",
            "provider": result_data.get("selected_provider") or model_config["provider_label"],
            "quality_score": 0.8,
            "qa_checks": qa_checks,
            "generation_summary": (
                "Reused an existing generated clip from this Ray run."
                if reused else
                f"Generated through OpenMontage video_selector using {model_config['label']} {operation.replace('_', '-')}."
            ),
        })
        partial = {
            "completed_scene_ids": [a["scene_id"] for a in assets],
            "r2_assets": r2_assets,
            "chain_frames": chain_frames,
            "generation_runs": generation_runs,
        }
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            "assets",
            "in_progress",
            {},
            pipeline_type="cinematic",
            metadata={"partial_progress": partial},
            cost_snapshot=_cost_snapshot({"total_cost_usd": total_cost}),
        )
    return {
        "version": "1.0",
        "assets": assets,
        "total_cost_usd": round(total_cost, 2),
        "metadata": {
            "r2_assets": r2_assets,
            "chain_frames": chain_frames,
            "generation_runs": generation_runs,
            "generation_adapter": "hosted_pipeline.video_selector_sequence",
            "generated_scene_count": len(assets),
            "total_scene_count": len(scenes),
            "sample_only": bool(sample_only),
            "qa_summary": _asset_qa_summary(assets),
        },
    }


def _needs_reference_fidelity_review(request_data: dict[str, Any]) -> bool:
    return _reference_conditioning_expected(request_data) and _reference_asset_count(request_data) > 0


def _mark_reference_review_required(
    asset_manifest: dict[str, Any],
    request_data: dict[str, Any],
    scene_plan: dict[str, Any],
    *,
    phase: str,
) -> None:
    generated_scene_ids = [str(asset.get("scene_id")) for asset in asset_manifest.get("assets") or []]
    expected_scene_ids = [str(scene.get("id")) for scene in scene_plan.get("scenes") or []]
    metadata = asset_manifest.setdefault("metadata", {})
    metadata["review_required"] = {
        "type": "reference_fidelity_review",
        "phase": phase,
        "status": "awaiting_human",
        "provider": request_data.get("video_model_label") or request_data.get("video_model"),
        "video_model": request_data.get("video_model"),
        "conditioning_mode": "image_to_video",
        "reference_asset_count": _reference_asset_count(request_data),
        "generated_scene_ids": generated_scene_ids,
        "expected_scene_ids": expected_scene_ids,
        "message": (
            "Reference-conditioned generation requires human visual review before the run spends on more clips "
            "or composes a final video. Reject if the product, garment, fabric, model, or palette drifts from references."
        ),
        "acceptance_criteria": [
            "The generated clip clearly uses the supplied product/reference images.",
            "Garment category, fabric, print, palette, and styling are recognizably faithful.",
            "The model/person and setting do not drift into an unrelated look.",
            "QA warnings such as possible black vignette/matte or duration mismatch are resolved or explicitly accepted.",
            "No final compose runs until these clips are explicitly accepted.",
        ],
        "next_action": (
            "approve_asset_review_to_generate_remaining_clips"
            if set(generated_scene_ids) != set(expected_scene_ids)
            else "approve_asset_review_to_compose"
        ),
    }


def _sanitize_visual_prompt(text: str) -> str:
    value = text or ""
    replacements = {
        "vignette": "shallow depth of field with edges softly falling out of focus",
        "matte": "soft natural falloff",
        "frame": "composition",
        "border": "edge detail",
    }
    for banned, replacement in replacements.items():
        value = re.sub(rf"\b{re.escape(banned)}\b", replacement, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def _single_shot_instruction(scene: dict[str, Any], scene_index: int | None = None) -> str:
    idx = scene_index or int(scene.get("sequence_index") or 0)
    hook = ""
    if idx == 1:
        hook = (
            " Opening hook rule: begin on the strongest product detail, macro textile/fabric/motif view, "
            "not a wide establishing shot."
        )
    return (
        " SINGLE continuous shot only. One framing intent for the entire clip. "
        "No internal cuts, no jump cuts, no shot changes, no reframing drift, no montage inside the clip. "
        "Camera motion is limited to a slow push-in, gentle pan, or locked-off hold."
        f"{hook}"
    )


def _negative_visual_prompt() -> str:
    return (
        " Negative: text overlays, logos, captions, 3D, cartoon, VFX aesthetic, extra people, new garment, "
        "changed product color, internal cuts, jump cuts, montage, reframing, vignette, matte, frame, border."
    )


def _probe_duration_seconds(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


def _probe_video_dimensions(path: Path) -> tuple[int, int] | None:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    match = re.search(r"(\d+)x(\d+)", proc.stdout.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _volumedetect(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = f"{proc.stdout}\n{proc.stderr}"
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
    result: dict[str, Any] = {
        "mean_volume_db": float(mean_match.group(1)) if mean_match else None,
        "max_volume_db": float(max_match.group(1)) if max_match else None,
    }
    result["effectively_silent"] = (
        result["mean_volume_db"] is None
        or result["mean_volume_db"] < -35
        or (result["max_volume_db"] is not None and result["max_volume_db"] < -20)
    )
    return result


def _black_edge_warning(video_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
    except Exception:
        return {"checked": False, "warning": False, "reason": "Pillow unavailable"}

    duration = _probe_duration_seconds(video_path)
    seek = max(0.25, duration / 2 if duration else 1.0)
    frame_path = video_path.with_suffix(video_path.suffix + ".qa.jpg")
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{seek:.2f}", "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(frame_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0 or not frame_path.is_file():
            return {"checked": False, "warning": False, "reason": "frame extraction failed"}
        image = Image.open(frame_path).convert("L")
        width, height = image.size
        corner = max(16, min(width, height) // 8)
        center_box = (
            width // 2 - corner,
            height // 2 - corner,
            width // 2 + corner,
            height // 2 + corner,
        )
        corners = [
            image.crop((0, 0, corner, corner)),
            image.crop((width - corner, 0, width, corner)),
            image.crop((0, height - corner, corner, height)),
            image.crop((width - corner, height - corner, width, height)),
        ]
        corner_mean = sum(ImageStat.Stat(crop).mean[0] for crop in corners) / len(corners)
        center_mean = ImageStat.Stat(image.crop(center_box)).mean[0]
        warning = corner_mean < 22 and center_mean > 45 and (center_mean - corner_mean) > 35
        return {
            "checked": True,
            "warning": bool(warning),
            "corner_luma_mean": round(corner_mean, 2),
            "center_luma_mean": round(center_mean, 2),
            "reason": "possible hard black vignette/matte" if warning else "no hard black edge detected",
        }
    except Exception as exc:
        return {"checked": False, "warning": False, "reason": str(exc)[:160]}
    finally:
        try:
            frame_path.unlink()
        except FileNotFoundError:
            pass


def _qa_video_clip(
    video_path: Path,
    expected_duration: float,
    *,
    expected_aspect_ratio: str | None = None,
) -> dict[str, Any]:
    actual_duration = _probe_duration_seconds(video_path)
    duration_delta = actual_duration - float(expected_duration or 0)
    dimensions = _probe_video_dimensions(video_path)
    expected_ratio = _aspect_ratio_value(expected_aspect_ratio)
    actual_ratio = None
    aspect_ratio_delta = None
    dimensions_ok = True
    if dimensions:
        actual_ratio = dimensions[0] / dimensions[1] if dimensions[1] else None
    if expected_ratio and actual_ratio:
        aspect_ratio_delta = actual_ratio - expected_ratio
        dimensions_ok = abs(aspect_ratio_delta) <= ASPECT_RATIO_TOLERANCE
    elif expected_ratio:
        dimensions_ok = False
    audio = _volumedetect(video_path)
    edge = _black_edge_warning(video_path)
    warnings = []
    if expected_duration and abs(duration_delta) > 1.0:
        warnings.append("duration_vs_plan_mismatch")
    if not dimensions_ok:
        warnings.append("dimensions_vs_plan_mismatch")
    if edge.get("warning"):
        warnings.append("possible_black_vignette_or_matte")
    if audio.get("effectively_silent"):
        warnings.append("native_audio_effectively_silent")
    return {
        "duration_seconds": round(actual_duration, 3),
        "expected_duration_seconds": float(expected_duration or 0),
        "duration_delta_seconds": round(duration_delta, 3),
        "duration_ok": not expected_duration or abs(duration_delta) <= 1.0,
        "width": dimensions[0] if dimensions else None,
        "height": dimensions[1] if dimensions else None,
        "expected_aspect_ratio": expected_aspect_ratio,
        "actual_aspect_ratio": round(actual_ratio, 6) if actual_ratio else None,
        "aspect_ratio_delta": round(aspect_ratio_delta, 6) if aspect_ratio_delta is not None else None,
        "dimensions_ok": dimensions_ok,
        "audio": audio,
        "black_edge": edge,
        "warnings": warnings,
    }


def _asset_qa_summary(assets: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    for asset in assets:
        qa = asset.get("qa_checks") or {}
        for warning in qa.get("warnings") or []:
            warnings.append({
                "asset_id": asset.get("id"),
                "scene_id": asset.get("scene_id"),
                "warning": warning,
            })
    return {
        "checked_asset_count": len(assets),
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def _video_prompt(
    request_data: dict[str, Any],
    scene: dict[str, Any],
    model_config: dict[str, Any],
    reference_image_urls: list[str],
    scene_index: int | None = None,
) -> str:
    ref_note = ""
    description = _sanitize_visual_prompt(str(scene.get("description") or ""))
    shot_intent = _sanitize_visual_prompt(str(scene.get("shot_intent") or ""))
    shot_lock = _single_shot_instruction(scene, scene_index)
    negative = _negative_visual_prompt()
    if reference_image_urls:
        if model_config["provider"] == "veo":
            return (
                "Reference-to-video for Google Veo 3.1. Use the supplied image_urls as fixed visual references "
                "for consistent subject appearance. Animate the same person, product, garment, and fabric shown "
                f"in the references as one coherent vertical commercial shot. Action: {description}. "
                f"Narrative beat: {shot_intent}. Start from the reference look and keep the "
                "outfit, fabric, color palette, face, and setting stable. Camera motion: slow push-in or gentle "
                "pan. Motion: subtle fabric flow and natural body movement. Lighting: soft premium daylight. "
                f"{shot_lock} {negative}"
            )
        if model_config["provider"] == "grok":
            refs = ", ".join(f"@Image{idx}" for idx in range(1, len(reference_image_urls) + 1))
            ref_note = (
                f" Reference images are supplied as {refs}. Treat @Image1 as the primary identity and product anchor. "
                "Map all references explicitly: preserve the same person/product/garment identity, fabric texture, "
                "color palette, styling, jewelry family, and brand feel in motion."
            )
        elif model_config["provider"] == "kling":
            ref_note = (
                " A single reference image is supplied to Kling image-to-video. Treat it as the first-frame visual anchor: "
                "preserve the same product, garment, fabric texture, color palette, styling, and brand feel. "
                "Preserve exact textile motif geometry and block-print details; Warli figures, temples, suns, borders, "
                "and linework must not wash out into generic florals. Keep motion simple, with slow camera movement "
                "and no wardrobe/product redesign."
            )
        else:
            ref_note = (
                " Reference-to-video input is supplied. Use the supplied reference images as strict visual anchors "
                "for the same product, garment, fabric texture, color palette, styling, and brand feel. "
                "[identity_lock] Maintain exact appearance from the reference images across all shots; "
                "no drift, no deformation, no face morph, do not alter clothing category or primary color."
            )
    return (
        f"Montage, cinematic commercial, photorealistic, 35mm film quality, polished premium lighting, "
        f"sharp authentic fabric detail, no 3D, no cartoon, no VFX aesthetic. {description}. "
        f"Coherent motion, natural camera movement, no text overlays, no logos unless explicitly requested. "
        f"Narrative beat: {shot_intent}.{ref_note} {shot_lock} {negative}"
    )


def _reference_image_urls(request_data: dict[str, Any], limit: int = 9) -> list[str]:
    urls: list[str] = []
    for asset in request_data.get("reference_assets") or []:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("path") or asset.get("filename") or "").lower()
        content_type = str(asset.get("content_type") or "").lower()
        is_image = content_type.startswith("image/") or path.endswith((".png", ".jpg", ".jpeg", ".webp"))
        url = str(asset.get("url") or "")
        if is_image and url.startswith(("http://", "https://")):
            urls.append(url)
    return urls[:limit]


def _scene_duration_seconds(
    scene: dict[str, Any],
    request_data: dict[str, Any],
    scene_count: int,
    model_config: dict[str, Any],
) -> int:
    try:
        planned = float(scene.get("end_seconds", 0)) - float(scene.get("start_seconds", 0))
    except (TypeError, ValueError):
        planned = 0
    if planned <= 0:
        planned = float(request_data["duration_seconds"]) / max(scene_count, 1)
    seconds = max(model_config["min_scene_seconds"], min(model_config["max_scene_seconds"], round(planned)))
    if model_config["provider"] == "veo":
        if seconds <= 4:
            return 4
        if seconds <= 6:
            return 6
        return 8
    if model_config["provider"] == "kling":
        return 5 if seconds <= 5 else 10
    return int(seconds)


def _generation_signature(
    *,
    prompt: str,
    operation: str,
    request_data: dict[str, Any],
    duration: int,
    video_model: str,
    reference_image_urls: list[str],
) -> dict[str, Any]:
    return {
        "video_model": video_model,
        "operation": operation,
        "model_variant": request_data.get("model_variant"),
        "duration": str(duration),
        "aspect_ratio": request_data.get("aspect_ratio", "16:9"),
        "resolution": "720p",
        "reference_hash": hashlib.sha1("\n".join(reference_image_urls).encode("utf-8")).hexdigest(),
        "prompt_hash": hashlib.sha1(prompt.encode("utf-8")).hexdigest(),
    }


def _clip_metadata_path(video_path: Path) -> Path:
    return video_path.with_suffix(video_path.suffix + ".json")


def _clip_metadata_matches(video_path: Path, signature: dict[str, Any]) -> bool:
    metadata = _clip_metadata_path(video_path)
    if not metadata.is_file():
        return False
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return all(data.get(key) == value for key, value in signature.items())


def _file_sha1(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_last_frame(video_path: Path, output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-sseof",
                "-0.2",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return False
    return proc.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0


def _event_cost_for_scene(project_dir: Path, scene_id: str) -> float:
    events_path = project_dir / "events.jsonl"
    if not events_path.is_file():
        return 0.0
    cost = 0.0
    try:
        for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("scene_id") == scene_id and event.get("event") == "finish":
                cost = float(event.get("cost_usd") or cost)
    except OSError:
        return 0.0
    return cost


def _normalize_video_model(raw: Any) -> str:
    value = str(raw or "").strip()
    key = value.lower()
    aliases = {
        "": DEFAULT_VIDEO_MODEL,
        "kling": "kling-v3",
        "kling 3": "kling-v3",
        "kling-3": "kling-v3",
        "kling3": "kling-v3",
        "kling-v3": "kling-v3",
        "v3/standard": "kling-v3",
        "veo3.1/fast": "veo3.1-fast",
        "veo-3.1-fast": "veo3.1-fast",
        "veo3.1": "veo3.1",
        "veo-3.1": "veo3.1",
        "grok": "grok-imagine-video",
        "grok-imagine": "grok-imagine-video",
        "grok-imagine-video": "grok-imagine-video",
        "seedance": "seedance-standard",
        "seedance-2.0": "seedance-standard",
        "standard": "seedance-standard",
        "seedance-standard": "seedance-standard",
        "fast": "seedance-fast",
        "seedance-fast": "seedance-fast",
    }
    if key in {"happy horse", "happy-horse", "happy horse 1.0", "happy-horse-1.0"}:
        raise JobError("Happy Horse 1.0 is not wired in this hosted Ray build yet; no adapter exists in this repo.")
    if key in aliases:
        return aliases[key]
    if value in VIDEO_MODELS:
        return value
    raise JobError(f"Unknown video model: {value}. Choose one of: {', '.join(VIDEO_MODELS)}.")


def _video_model_config(video_model: str) -> dict[str, Any]:
    return VIDEO_MODELS.get(video_model, VIDEO_MODELS[DEFAULT_VIDEO_MODEL])


def _video_model_config_from_request(request_data: dict[str, Any]) -> dict[str, Any]:
    return _video_model_config(_normalize_video_model(request_data.get("video_model") or request_data.get("model_variant")))


def _has_any_env(names: tuple[str, ...]) -> bool:
    return any(os.environ.get(name) for name in names)


def _recommended_scene_count(duration_seconds: int, model_config: dict[str, Any]) -> int:
    max_scene = int(model_config["max_scene_seconds"])
    return max(1, min(MAX_SCENE_COUNT, (duration_seconds + max_scene - 1) // max_scene))


def _reference_limit(model_config: dict[str, Any]) -> int:
    if model_config["provider"] == "seedance":
        return 9
    if model_config["provider"] == "veo":
        return 4
    if model_config["provider"] == "grok":
        return 7
    if model_config["provider"] == "kling":
        return 1
    return 6


def _video_operation(model_config: dict[str, Any], reference_image_urls: list[str]) -> str:
    if not reference_image_urls:
        return "text_to_video"
    if model_config["provider"] == "kling":
        return "image_to_video"
    return "reference_to_video"


def _video_operation_for_scene(
    model_config: dict[str, Any],
    reference_image_urls: list[str],
    previous_last_frame_path: Path | None,
    scene_index: int,
) -> str:
    if scene_index > 1 and previous_last_frame_path and previous_last_frame_path.is_file():
        if model_config["provider"] == "veo" and reference_image_urls:
            return "first_last_frame_to_video"
        return "image_to_video"
    return _video_operation(model_config, reference_image_urls)


def _apply_reference_and_chain_inputs(
    generation_inputs: dict[str, Any],
    model_config: dict[str, Any],
    reference_image_urls: list[str],
    previous_last_frame_path: Path | None,
    *,
    scene_index: int,
) -> None:
    if scene_index > 1 and previous_last_frame_path and previous_last_frame_path.is_file():
        if model_config["provider"] == "veo" and reference_image_urls:
            generation_inputs["first_frame_path"] = str(previous_last_frame_path)
            generation_inputs["last_frame_url"] = reference_image_urls[(scene_index - 1) % len(reference_image_urls)]
            return
        generation_inputs["reference_image_path"] = str(previous_last_frame_path)
        generation_inputs["image_path"] = str(previous_last_frame_path)
        if model_config["provider"] == "seedance" and reference_image_urls:
            generation_inputs["end_image_url"] = reference_image_urls[(scene_index - 1) % len(reference_image_urls)]
        return

    if not reference_image_urls:
        return
    if generation_inputs.get("operation") == "image_to_video":
        generation_inputs["image_url"] = reference_image_urls[0]
        generation_inputs["reference_image_url"] = reference_image_urls[0]
    else:
        generation_inputs["reference_image_urls"] = reference_image_urls


def _chaining_mode_for_scene(
    model_config: dict[str, Any],
    previous_last_frame_path: Path | None,
    scene_index: int,
) -> str:
    if scene_index <= 1:
        return "none"
    if not previous_last_frame_path:
        return "missing_previous_last_frame"
    if model_config["provider"] == "veo":
        return "first_last_frame_to_video"
    if model_config["provider"] == "seedance":
        return "image_to_video_with_end_image_url"
    return "image_to_video_from_previous_last_frame"


def _duration_value(model_config: dict[str, Any], seconds: int) -> str | int:
    if model_config["provider"] == "veo":
        return f"{seconds}s"
    if model_config["provider"] == "grok":
        return seconds
    return str(seconds)


def _video_tool(model_config: dict[str, Any]) -> Any:
    if model_config["provider"] == "veo":
        from tools.video.veo_video import VeoVideo

        return VeoVideo()
    if model_config["provider"] == "grok":
        from tools.video.grok_video import GrokVideo

        return GrokVideo()
    if model_config["provider"] == "kling":
        from tools.video.kling_video import KlingVideo

        return KlingVideo()
    from tools.video.seedance_video import SeedanceVideo

    return SeedanceVideo()


def _post_edit_plan(
    video_assets: list[dict[str, Any]],
    planned_duration: float,
) -> dict[str, Any]:
    actuals = []
    for asset in video_assets:
        actuals.append(max(1.0, float(asset.get("duration_seconds") or 0)))
    if not actuals:
        return {"segments": [], "end_card_seconds": END_CARD_SECONDS, "transition_seconds": TRANSITION_SECONDS}
    end_card_seconds = min(4.0, max(3.0, END_CARD_SECONDS))
    target_duration = max(planned_duration or sum(actuals), end_card_seconds + 4.0)
    desired_clip_total = max(len(actuals) * 2.25, target_duration - end_card_seconds + TRANSITION_SECONDS * len(actuals))
    raw_total = sum(actuals) or 1.0
    rhythm = [0.96, 1.04, 0.9, 1.08, 0.95, 1.02, 0.92, 1.0]
    segments = []
    for idx, (asset, actual) in enumerate(zip(video_assets, actuals), start=1):
        prompt = str(asset.get("prompt") or "").lower()
        slow = any(term in prompt for term in ("slow-motion", "slow motion", "pallu turn", "graceful turn"))
        playback_rate = 0.5 if slow else 1.0
        target_output = max(2.25, desired_clip_total * (actual / raw_total) * rhythm[(idx - 1) % len(rhythm)])
        source_trim = min(actual, target_output * playback_rate)
        output_duration = source_trim / playback_rate
        segments.append({
            "asset": asset,
            "source_duration_seconds": round(actual, 3),
            "trim_seconds": round(source_trim, 3),
            "output_duration_seconds": round(output_duration, 3),
            "playback_rate": playback_rate,
            "retimed": playback_rate != 1.0,
        })

    current_total = sum(segment["output_duration_seconds"] for segment in segments)
    if current_total > desired_clip_total:
        extra = current_total - desired_clip_total
        flexible = [segment for segment in segments if segment["output_duration_seconds"] > 2.5]
        for segment in flexible:
            share = extra / max(len(flexible), 1)
            new_output = max(2.5, segment["output_duration_seconds"] - share)
            segment["output_duration_seconds"] = round(new_output, 3)
            segment["trim_seconds"] = round(min(segment["source_duration_seconds"], new_output * segment["playback_rate"]), 3)

    return {
        "segments": segments,
        "end_card_seconds": end_card_seconds,
        "transition_seconds": TRANSITION_SECONDS,
        "target_duration_seconds": target_duration,
    }


def _end_card_text(request_data: dict[str, Any] | None) -> dict[str, str]:
    request_data = request_data or {}
    brand = str(request_data.get("brand_name") or request_data.get("client_name") or "").strip()
    tagline = str(request_data.get("tagline") or DEFAULT_END_CARD_TAGLINE).strip()
    cta = str(request_data.get("cta") or DEFAULT_END_CARD_CTA).strip()
    return {"brand": brand, "tagline": tagline, "cta": cta}


def _load_font(size: int):
    try:
        from PIL import ImageFont

        for candidate in (
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ):
            if Path(candidate).is_file():
                return ImageFont.truetype(candidate, size=size)
        return ImageFont.load_default()
    except Exception:
        return None


def _create_end_card_clip(render_dir: Path, request_data: dict[str, Any] | None, duration: float) -> Path:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        raise JobError(f"Pillow is required for end-card rendering: {exc}")

    card = _end_card_text(request_data)
    image_path = render_dir / "end_card.png"
    video_path = render_dir / "end_card.mp4"
    image = Image.new("RGB", (FINAL_WIDTH, FINAL_HEIGHT), "#171411")
    draw = ImageDraw.Draw(image)
    cream = "#f2e9d5"
    amber = "#f0a83c"
    muted = "#b8aa91"
    title_font = _load_font(68)
    brand_font = _load_font(46)
    cta_font = _load_font(34)

    y = FINAL_HEIGHT // 2 - 170
    if card["brand"]:
        brand_text = card["brand"].upper()
        bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
        draw.text(((FINAL_WIDTH - (bbox[2] - bbox[0])) / 2, y), brand_text, fill=amber, font=brand_font)
        y += 96
    tagline = card["tagline"]
    bbox = draw.textbbox((0, 0), tagline, font=title_font)
    draw.text(((FINAL_WIDTH - (bbox[2] - bbox[0])) / 2, y), tagline, fill=cream, font=title_font)
    y += 120
    cta = card["cta"]
    if cta:
        bbox = draw.textbbox((0, 0), cta, font=cta_font)
        draw.text(((FINAL_WIDTH - (bbox[2] - bbox[0])) / 2, y), cta, fill=muted, font=cta_font)
    draw.line((FINAL_WIDTH * 0.35, y + 88, FINAL_WIDTH * 0.65, y + 88), fill=amber, width=3)
    image.save(image_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(FINAL_FPS),
        "-t",
        f"{duration:.3f}",
        "-i",
        str(image_path),
        "-vf",
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0, duration - 0.45):.3f}:d=0.45,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-r",
        str(FINAL_FPS),
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise JobError(f"End-card render failed: {proc.stderr[-500:]}")
    return video_path


def _render_video_with_crossfades(
    segments: list[dict[str, Any]],
    end_card_path: Path,
    end_card_seconds: float,
    output_path: Path,
) -> float:
    segment_count = len(segments) + 1
    inputs: list[str] = []
    for segment in segments:
        inputs.extend(["-i", str(segment["path"])])
    inputs.extend(["-i", str(end_card_path)])

    filters: list[str] = []
    durations: list[float] = []
    for idx, segment in enumerate(segments):
        trim = float(segment["trim_seconds"])
        playback_rate = float(segment["playback_rate"])
        output_duration = float(segment["output_duration_seconds"])
        retime_filter = f"setpts=(PTS-STARTPTS)/{playback_rate:.3f}"
        motion_filter = ",minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir" if playback_rate < 1.0 else ""
        filters.append(
            f"[{idx}:v]trim=start=0:duration={trim:.3f},{retime_filter},fps={FINAL_FPS}{motion_filter},"
            f"scale={FINAL_WIDTH}:{FINAL_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={FINAL_WIDTH}:{FINAL_HEIGHT},setsar=1,format=yuv420p[v{idx}]"
        )
        durations.append(output_duration)
    end_idx = segment_count - 1
    filters.append(
        f"[{end_idx}:v]trim=start=0:duration={end_card_seconds:.3f},setpts=PTS-STARTPTS,"
        f"fps={FINAL_FPS},scale={FINAL_WIDTH}:{FINAL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={FINAL_WIDTH}:{FINAL_HEIGHT},setsar=1,format=yuv420p[v{end_idx}]"
    )
    durations.append(end_card_seconds)

    current = "[v0]"
    elapsed = durations[0]
    for idx in range(1, segment_count):
        out_label = f"[x{idx}]"
        offset = max(0.1, elapsed - TRANSITION_SECONDS)
        filters.append(
            f"{current}[v{idx}]xfade=transition=fade:duration={TRANSITION_SECONDS:.3f}:offset={offset:.3f}{out_label}"
        )
        current = out_label
        elapsed += durations[idx] - TRANSITION_SECONDS

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        current,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-r",
        str(FINAL_FPS),
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if proc.returncode != 0:
        raise JobError(f"FFmpeg post compose failed: {proc.stderr[-800:]}")
    return _probe_duration_seconds(output_path)


def _create_music_bed(render_dir: Path, duration: float) -> Path:
    music_path = render_dir / "music_bed.wav"
    out_fade_start = max(0, duration - 1.5)
    pulse_start = max(0, duration - END_CARD_SECONDS)
    filter_complex = (
        "[0:a]volume=0.12[a0];"
        "[1:a]volume=0.045,tremolo=f=5:d=0.18[a1];"
        f"[2:a]volume=0.026,afade=t=in:st={pulse_start:.3f}:d={END_CARD_SECONDS:.3f}[a2];"
        f"[a0][a1][a2]amix=inputs=3:duration=longest,lowpass=f=2600,"
        f"afade=t=in:st=0:d=1,afade=t=out:st={out_fade_start:.3f}:d=1.5[a]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=146.83:sample_rate=48000:duration={duration:.3f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=220:sample_rate=48000:duration={duration:.3f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=58:sample_rate=48000:duration={duration:.3f}",
        "-filter_complex",
        filter_complex,
        "-map",
        "[a]",
        "-c:a",
        "pcm_s16le",
        str(music_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise JobError(f"Music bed generation failed: {proc.stderr[-500:]}")
    return music_path


def _mux_music(video_path: Path, music_path: Path, final_path: Path, duration: float) -> None:
    out_fade_start = max(0, duration - 1.5)
    audio_filter = f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={out_fade_start:.3f}:d=1.5"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(music_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        audio_filter,
        "-shortest",
        str(final_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise JobError(f"Audio mix failed: {proc.stderr[-500:]}")


def _render_qa(final_path: Path, planned_duration: float) -> dict[str, Any]:
    duration = _probe_duration_seconds(final_path)
    audio = _volumedetect(final_path)
    warnings = []
    if planned_duration and abs(duration - planned_duration) > 1.25:
        warnings.append("duration_vs_plan_mismatch")
    if audio.get("effectively_silent"):
        warnings.append("audio_effectively_silent")
    return {
        "duration_seconds": round(duration, 3),
        "planned_duration_seconds": round(float(planned_duration or 0), 3),
        "audio": audio,
        "warnings": warnings,
    }


def _compose(
    project_id: str,
    project_dir: Path,
    asset_manifest: dict[str, Any],
    request_data: dict[str, Any] | None = None,
    scene_plan: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    video_assets = [a for a in asset_manifest["assets"] if a["type"] == "video"]
    if not video_assets:
        raise JobError("No generated video assets to compose.")
    request_data = request_data or {}
    planned_duration = float(request_data.get("duration_seconds") or sum(float(a.get("duration_seconds") or 0) for a in video_assets))
    write_checkpoint(PROJECTS_DIR, project_id, "compose", "in_progress", {}, pipeline_type="cinematic")
    render_dir = project_dir / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    edit_plan = _post_edit_plan(video_assets, planned_duration)
    for segment in edit_plan["segments"]:
        segment["path"] = project_dir / segment["asset"]["path"]
    end_card = _create_end_card_clip(render_dir, request_data, float(edit_plan["end_card_seconds"]))
    silent_path = render_dir / "post_composed_silent.mp4"
    silent_duration = _render_video_with_crossfades(
        edit_plan["segments"],
        end_card,
        float(edit_plan["end_card_seconds"]),
        silent_path,
    )
    music_bed = _create_music_bed(render_dir, silent_duration)
    final_path = project_dir / "renders" / "final.mp4"
    _mux_music(silent_path, music_bed, final_path, silent_duration)
    render_qa = _render_qa(final_path, planned_duration)

    upload = storage.upload_file(final_path, project_id, "renders/final.mp4")
    transition_rows = []
    elapsed = 0.0
    for segment in edit_plan["segments"]:
        elapsed += float(segment["output_duration_seconds"])
        transition_rows.append({
            "type": "crossfade",
            "at_seconds": round(max(0, elapsed - TRANSITION_SECONDS), 3),
            "duration_seconds": TRANSITION_SECONDS,
        })
        elapsed -= TRANSITION_SECONDS
    edit_decisions = {
        "version": "1.0",
        "render_runtime": "ffmpeg",
        "cuts": [
            {
                "id": f"cut_{idx}",
                "source": segment["asset"]["id"],
                "in_seconds": 0,
                "out_seconds": float(segment["trim_seconds"]),
                "speed": float(segment["playback_rate"]),
                "transition_out": "crossfade",
                "transition_duration": TRANSITION_SECONDS,
                "reason": "Hosted Ray UI generated scene clip, trimmed for post rhythm.",
            }
            for idx, segment in enumerate(edit_plan["segments"], start=1)
        ],
        "transitions": transition_rows,
        "audio": {
            "music": {
                "asset_id": "renders/music_bed.wav",
                "volume": 1.0,
                "fade_in_seconds": 1.0,
                "fade_out_seconds": 1.5,
            }
        },
        "metadata": {
            "post_pipeline": "ffmpeg_post_compose",
            "music_source": {"source": "synthetic_ffmpeg_bed", "target_lufs": -14, "path": "renders/music_bed.wav"},
            "end_card": {"duration_seconds": edit_plan["end_card_seconds"], **_end_card_text(request_data)},
            "upscale": {"width": FINAL_WIDTH, "height": FINAL_HEIGHT, "method": "ffmpeg_scale_crop"},
            "retimed_cuts": [
                {"source": segment["asset"]["id"], "playback_rate": segment["playback_rate"]}
                for segment in edit_plan["segments"]
                if segment["retimed"]
            ],
        },
    }
    render_report = {
        "version": "1.0",
        "outputs": [{
            "path": "renders/final.mp4",
            "format": "mp4",
            "codec": "h264",
            "audio_codec": "aac",
            "resolution": "1080x1920",
            "duration_seconds": render_qa["duration_seconds"],
            "file_size_bytes": final_path.stat().st_size,
            "platform_target": "youtube",
        }],
        "render_time_seconds": 0,
        "verification_notes": [
            "Generated clips post-composed with FFmpeg crossfades.",
            "Synthetic music bed mixed and loudness-normalized toward -14 LUFS.",
            "End card rendered in post, not by the video model.",
            "Final output scaled/cropped to 1080x1920.",
        ],
        "metadata": {
            "r2_output": upload,
            "post_pipeline": {
                "crossfades": True,
                "music_bed": True,
                "loudness_target_lufs": -14,
                "end_card": True,
                "upscaled_to": [FINAL_WIDTH, FINAL_HEIGHT],
            },
            "qa": render_qa,
        },
    }
    return edit_decisions, render_report


def save_upload(project_id: str, filename: str, content: bytes) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project_id
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-") or "upload.bin"
    rel = f"uploads/{int(time.time())}-{safe}"
    path = project_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    upload = storage.upload_file(path, project_id, rel)
    return {"path": rel, "filename": safe, **upload}


def _cost_snapshot(asset_manifest: dict[str, Any]) -> dict[str, Any]:
    spent = float(asset_manifest.get("total_cost_usd") or 0)
    return {"total_spent_usd": round(spent, 2), "total_reserved_usd": 0, "budget_remaining_usd": 0}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_project_to_r2(project_id: str) -> list[dict[str, Any]]:
    project_dir = PROJECTS_DIR / project_id
    results = []
    for path in project_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(project_dir).as_posix()
            results.append(storage.upload_file(path, project_id, rel))
    return results
