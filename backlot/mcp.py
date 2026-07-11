"""Minimal Streamable HTTP MCP surface for hosted iKawn Ray."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlparse

from backlot import jobs, storage
from backlot.state import PROJECTS_DIR, load_board_state, summarize_project

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "ikawn-ray"
SERVER_VERSION = "0.7.1"
BRAND_NAME = "iKawn Ray"
BRAND_COLOR = "#f0a83c"
BRAND_BACKGROUND_COLOR = "#08090d"
BRAND_LOGO_PATH = "/ui/ikawn-ray.svg"
MAX_MCP_INLINE_UPLOAD_BYTES = 750_000
REFERENCE_UPLOAD_TTL_SECONDS = 15 * 60
MCP_VIDEO_PROVIDERS = ("kling-3", "grok-imagine", "veo-3.1", "happy-horse-1.0", "seedance-2.0")
MCP_PROVIDER_TO_MODEL = {
    "kling-3": "kling-v3",
    "grok-imagine": "grok-imagine-video",
    "veo-3.1": "veo3.1",
    "happy-horse-1.0": None,
    "seedance-2.0": "seedance-standard",
}

PublishHook = Callable[[str], None]


def public_url(base_url: str | None = None) -> str:
    return (base_url or os.environ.get("RAY_PUBLIC_URL") or "https://ikawn-ray.fly.dev").rstrip("/")


def brand_metadata(base_url: str | None = None) -> dict[str, Any]:
    base = public_url(base_url)
    logo_url = f"{base}{BRAND_LOGO_PATH}"
    return {
        "brand": {
            "name": BRAND_NAME,
            "color": BRAND_COLOR,
            "background_color": BRAND_BACKGROUND_COLOR,
            "logo_url": logo_url,
        },
        "brand_name": BRAND_NAME,
        "brandColor": BRAND_COLOR,
        "brand_color": BRAND_COLOR,
        "themeColor": BRAND_COLOR,
        "theme_color": BRAND_COLOR,
        "backgroundColor": BRAND_BACKGROUND_COLOR,
        "background_color": BRAND_BACKGROUND_COLOR,
        "logoUrl": logo_url,
        "logo_url": logo_url,
        "websiteUrl": base,
        "website_url": base,
    }


def _tool_meta() -> dict[str, Any]:
    meta = brand_metadata()
    meta.update({
        "openai/toolInvocation/invoking": "Running iKawn Ray",
        "openai/toolInvocation/invoked": "iKawn Ray finished",
        "openai/widgetAccessible": False,
    })
    return meta


def initialize_result() -> dict[str, Any]:
    meta = brand_metadata()
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": SERVER_NAME,
            "title": BRAND_NAME,
            "displayName": BRAND_NAME,
            "version": SERVER_VERSION,
            "brandColor": BRAND_COLOR,
            "logoUrl": meta["logo_url"],
            "websiteUrl": meta["website_url"],
        },
        "_meta": meta,
        "instructions": (
            "Use iKawn Ray to create, review, revise, and explicitly approve "
            "OpenMontage video-production jobs. Creating a plan does not spend "
            "video-generation credits. Paid generation requires an explicit "
            "ray_approve_paid_generation call with confirm_paid_generation=true. "
            "Grok Imagine is the hosted default. Seedance requires confirm_seedance_risk=true. "
            "Use ray_get_project_outputs to inspect every stage output, pending approval, progress, and final CDN MP4 URL."
        ),
    }


def tools() -> list[dict[str, Any]]:
    items = [
        {
            "name": "ray_create_video_plan",
            "title": "Create Ray video plan",
            "description": (
                "Create a Ray/OpenMontage video job and start the safe planning stage. "
                "This does not run paid video generation."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["prompt"],
                "properties": {
                    "prompt": {"type": "string", "description": "Plain-language video brief."},
                    "title": {"type": "string", "description": "Optional internal project title."},
                    "provider": {
                        "type": "string",
                        "enum": list(MCP_VIDEO_PROVIDERS),
                        "description": "Preferred video-generation provider. Defaults to Grok Imagine if omitted. Seedance is opt-in only.",
                    },
                    "duration_seconds": {"type": "integer", "minimum": 5, "maximum": jobs.MAX_DURATION_SECONDS, "default": 30},
                    "aspect_ratio": {"type": "string", "enum": sorted(jobs.SUPPORTED_ASPECTS), "default": "9:16"},
                    "budget_cap_usd": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum approved provider spend for this project. Paid calls block before exceeding it.",
                    },
                    "reference_urls": {
                        "type": "array",
                        "items": {"type": "string", "format": "uri"},
                        "description": "Publicly reachable image/file URLs to use as references.",
                    },
                    "reference_files": {
                        "type": "array",
                        "description": "Small uploaded reference files as base64 payloads.",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["filename", "base64_data"],
                            "properties": {
                                "filename": {"type": "string"},
                                "content_type": {"type": "string"},
                                "base64_data": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        {
            "name": "ray_list_projects",
            "title": "List Ray projects",
            "description": "List existing Ray/OpenMontage projects visible on the hosted board.",
            "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
        },
        {
            "name": "ray_get_project_state",
            "title": "Get Ray project state",
            "description": "Fetch current stage, summary, key artifacts, MCP workflow, pending approval, and final render URL for a project.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {"project_id": {"type": "string"}},
            },
        },
        {
            "name": "ray_get_project_outputs",
            "title": "Get Ray project outputs",
            "description": (
                "Fetch the MCP-native production workflow: progress for each stage, canonical artifacts, "
                "intermediate media URLs, pending approval action, and final CDN MP4 URL when available."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "include_raw_artifacts": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include full raw artifact JSON. Defaults false to keep MCP responses compact.",
                    },
                    "include_events": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include recent tool events for progress updates.",
                    },
                },
            },
        },
        {
            "name": "ray_request_reference_upload",
            "title": "Request reference upload URL",
            "description": (
                "Create a short-lived presigned PUT URL for uploading a reference image outside "
                "the MCP JSON payload. Use this for normal image attachments."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "filename": {"type": "string", "description": "Optional original filename. Defaults to reference.png."},
                    "content_type": {"type": "string", "default": "image/png"},
                },
            },
        },
        {
            "name": "ray_confirm_reference",
            "title": "Confirm uploaded reference",
            "description": (
                "Confirm a previously requested reference upload, attach it to the project, "
                "and queue a safe replan."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id", "asset_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "asset_id": {"type": "string"},
                },
            },
        },
        {
            "name": "ray_attach_references",
            "title": "Attach references to Ray project",
            "description": (
                "Attach reference URLs, small inline files, or confirmed upload asset IDs to an existing "
                "project and queue a safe replan."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "reference_urls": {"type": "array", "items": {"type": "string", "format": "uri"}},
                    "reference_asset_ids": {"type": "array", "items": {"type": "string"}},
                    "reference_files": {
                        "type": "array",
                        "description": "Tiny base64 fallback only. Use ray_request_reference_upload for normal images.",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["filename", "base64_data"],
                            "properties": {
                                "filename": {"type": "string"},
                                "content_type": {"type": "string"},
                                "base64_data": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        {
            "name": "ray_revise_plan",
            "title": "Revise Ray plan",
            "description": "Revise a proposal-stage plan. This does not run paid video generation.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "provider": {
                        "type": "string",
                        "enum": list(MCP_VIDEO_PROVIDERS),
                        "description": "Preferred video-generation provider for the revised plan. Seedance is opt-in only.",
                    },
                    "duration_seconds": {"type": "integer", "minimum": 5, "maximum": jobs.MAX_DURATION_SECONDS},
                    "aspect_ratio": {"type": "string", "enum": sorted(jobs.SUPPORTED_ASPECTS)},
                    "scene_count": {"type": "integer", "minimum": 1, "maximum": jobs.MAX_SCENE_COUNT},
                    "budget_cap_usd": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum approved provider spend for this project. Paid calls block before exceeding it.",
                    },
                    "reference_urls": {"type": "array", "items": {"type": "string", "format": "uri"}},
                    "reference_asset_ids": {"type": "array", "items": {"type": "string"}},
                    "reference_files": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
        {
            "name": "ray_approve_paid_generation",
            "title": "Approve paid generation",
            "description": (
                "Explicitly approve paid provider generation for a planned Ray project. "
                "Only call after the user has reviewed the proposal and confirmed spend."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id", "confirm_paid_generation"],
                "properties": {
                    "project_id": {"type": "string"},
                    "confirm_paid_generation": {"type": "boolean", "const": True},
                    "override_no_references": {
                        "type": "boolean",
                        "description": "Explicitly override a blocked reference-conditioned plan with zero references.",
                    },
                    "confirm_seedance_risk": {
                        "type": "boolean",
                        "description": "Required only when the plan uses Seedance. Confirms the user explicitly chose Seedance despite reference-fidelity risk.",
                    },
                },
            },
            "annotations": {"destructiveHint": True, "openWorldHint": True},
        },
        {
            "name": "ray_approve_asset_review",
            "title": "Approve reviewed Ray assets",
            "description": (
                "Continue only after the user has visually reviewed reference-conditioned generated clips. "
                "If only a sample exists, this may spend on the remaining clips; if all clips exist, it composes the final video."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id", "confirm_asset_review_passed"],
                "properties": {
                    "project_id": {"type": "string"},
                    "confirm_asset_review_passed": {"type": "boolean", "const": True},
                },
            },
            "annotations": {"destructiveHint": True, "openWorldHint": True},
        },
    ]
    for item in items:
        item.setdefault("_meta", {}).update(_tool_meta())
    return items


async def dispatch(
    message: dict[str, Any],
    *,
    base_url: str,
    session: dict[str, Any],
    publish_project: PublishHook | None = None,
) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}

    if msg_id is None:
        return None
    try:
        if method == "initialize":
            return _result(msg_id, initialize_result())
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            return _result(msg_id, {"tools": tools()})
        if method == "tools/call":
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            result = await call_tool(name, arguments, base_url=base_url, session=session, publish_project=publish_project)
            return _result(msg_id, result)
        if method == "resources/list":
            return _result(msg_id, {"resources": []})
        if method == "prompts/list":
            return _result(msg_id, {"prompts": []})
        return _error(msg_id, -32601, f"Unsupported MCP method: {method}")
    except Exception as exc:
        return _error(msg_id, -32000, str(exc))


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    base_url: str,
    session: dict[str, Any],
    publish_project: PublishHook | None = None,
) -> dict[str, Any]:
    if name == "ray_create_video_plan":
        data = await _create_video_plan(arguments, base_url, session, publish_project)
    elif name == "ray_list_projects":
        data = await asyncio.to_thread(_list_projects, base_url)
    elif name == "ray_get_project_state":
        data = await asyncio.to_thread(_get_project_state, str(arguments.get("project_id") or ""), base_url)
    elif name == "ray_get_project_outputs":
        data = await asyncio.to_thread(_get_project_outputs, arguments, base_url)
    elif name == "ray_request_reference_upload":
        data = await asyncio.to_thread(_request_reference_upload, arguments, base_url)
    elif name == "ray_confirm_reference":
        data = await _confirm_reference(arguments, base_url, publish_project)
    elif name == "ray_attach_references":
        data = await _attach_references_tool(arguments, base_url, publish_project)
    elif name == "ray_revise_plan":
        data = await _revise_plan(arguments, base_url, publish_project)
    elif name == "ray_approve_paid_generation":
        data = await _approve_paid_generation(arguments, base_url, publish_project)
    elif name == "ray_approve_asset_review":
        data = await _approve_asset_review(arguments, base_url, publish_project)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return {
        "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
        "structuredContent": data,
        "_meta": brand_metadata(base_url),
        "isError": False,
    }


async def _create_video_plan(
    args: dict[str, Any],
    base_url: str,
    session: dict[str, Any],
    publish_project: PublishHook | None,
) -> dict[str, Any]:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    reference_assets = _reference_assets_from_urls(args.get("reference_urls") or [])
    payload = {
        "title": str(args.get("title") or _title_from_prompt(prompt)),
        "prompt": prompt,
        "duration_seconds": int(args.get("duration_seconds") or 30),
        "aspect_ratio": str(args.get("aspect_ratio") or "9:16"),
        "reference_assets": reference_assets,
        "chat_messages": [{"role": "user", "text": prompt, "attachments": reference_assets}],
    }
    if "budget_cap_usd" in args:
        payload["budget_cap_usd"] = args.get("budget_cap_usd")
    video_model = _video_model_from_provider(args.get("provider") or args.get("video_model"))
    if video_model:
        payload["video_model"] = video_model
    job = await asyncio.to_thread(jobs.create_job, payload, session)
    project_id = job["project_id"]

    uploaded = await asyncio.to_thread(_save_reference_files, project_id, args.get("reference_files") or [])
    if uploaded:
        reference_assets.extend(uploaded)
        _update_job_request(project_id, {"reference_assets": reference_assets})

    if publish_project:
        publish_project(project_id)

    async def plan_and_publish() -> None:
        await asyncio.to_thread(jobs.plan_job, project_id)
        if publish_project:
            publish_project(project_id)

    asyncio.create_task(plan_and_publish())
    return {
        "ok": True,
        "status": "planning_queued",
        "project_id": project_id,
        "board_url": f"{base_url}/p/{project_id}",
        "monitor_tool": "ray_get_project_outputs",
        "monitor_arguments": {"project_id": project_id},
        "workflow": _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True),
        "paid_generation_started": False,
        "reference_asset_count": len(reference_assets),
        "provider": _provider_from_request(job.get("request") or {}),
        "video_model": (job.get("request") or {}).get("video_model"),
    }


def _list_projects(base_url: str) -> dict[str, Any]:
    if not PROJECTS_DIR.is_dir():
        return {"projects": []}
    projects = []
    for entry in sorted(PROJECTS_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith(("_", ".")):
            try:
                item = summarize_project(entry)
                item["board_url"] = f"{base_url}/p/{entry.name}"
                projects.append(item)
            except Exception:
                continue
    return {"projects": projects}


def _get_project_state(project_id: str, base_url: str) -> dict[str, Any]:
    project_dir = _safe_project_dir(project_id)
    state = load_board_state(project_dir)
    artifacts = state.get("artifacts") or {}
    workflow = _mcp_workflow(project_id, state, base_url, include_events=True)
    return {
        "project_id": project_id,
        "board_url": f"{base_url}/p/{project_id}",
        "summary": summarize_project(project_dir),
        "stages": state.get("stages") or [],
        "workflow": workflow,
        "pending_approval": workflow.get("pending_approval"),
        "final_render_url": (workflow.get("final_render") or {}).get("url"),
        "job_request": artifacts.get("job_request"),
        "proposal_packet": artifacts.get("proposal_packet"),
        "decision_log": artifacts.get("decision_log"),
        "render_report": artifacts.get("render_report"),
    }


def _get_project_outputs(args: dict[str, Any], base_url: str) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    project_dir = _safe_project_dir(project_id)
    state = load_board_state(project_dir)
    include_raw = args.get("include_raw_artifacts") is True
    include_events = args.get("include_events") is not False
    workflow = _mcp_workflow(project_id, state, base_url, include_events=include_events)
    result = {
        "project_id": project_id,
        "board_url": f"{base_url}/p/{project_id}",
        "summary": summarize_project(project_dir),
        "workflow": workflow,
        "stages": workflow["stages"],
        "pending_approval": workflow.get("pending_approval"),
        "final_render": workflow.get("final_render"),
        "final_render_url": (workflow.get("final_render") or {}).get("url"),
        "stage_outputs": workflow["stage_outputs"],
        "media_outputs": workflow["media_outputs"],
        "next_actions": workflow["next_actions"],
    }
    if include_raw:
        result["raw_artifacts"] = state.get("artifacts") or {}
    return result


def _mcp_workflow(project_id: str, state: dict[str, Any], base_url: str, *, include_events: bool) -> dict[str, Any]:
    artifacts = state.get("artifacts") or {}
    stages = state.get("stages") or []
    r2_urls = _r2_url_map(artifacts)
    stage_outputs = {
        "proposal": _proposal_output(artifacts),
        "script": _script_output(artifacts),
        "scene_plan": _scene_plan_output(artifacts),
        "assets": _assets_output(project_id, base_url, artifacts, r2_urls),
        "edit": _edit_output(artifacts),
        "compose": _compose_output(project_id, base_url, state, artifacts, r2_urls),
        "publish": _publish_output(artifacts),
    }
    stage_rows = []
    for stage in stages:
        name = str(stage.get("name") or "")
        outputs = stage_outputs.get(name) or {}
        stage_rows.append({
            "name": name,
            "status": stage.get("status") or "pending",
            "awaiting_human": stage.get("status") == "awaiting_human",
            "artifact_available": bool(outputs.get("artifact_available")),
            "artifact_key": outputs.get("artifact_key"),
            "output_summary": outputs.get("summary"),
            "media_count": len(outputs.get("media") or []),
            "progress": stage.get("partial_progress"),
            "cost_snapshot": stage.get("cost_snapshot"),
            "review": stage.get("review"),
            "error": stage.get("error"),
            "human_approved": stage.get("human_approved"),
        })
    final_render = _final_render(project_id, base_url, state, artifacts, r2_urls)
    pending_approval = _pending_approval(project_id, state, artifacts)
    completed = len([s for s in stage_rows if s["status"] == "completed"])
    actionable = next((s for s in stage_rows if s["status"] in {"awaiting_human", "failed", "in_progress"}), None)
    status = (
        "completed" if final_render and final_render.get("url")
        else "awaiting_approval" if pending_approval
        else actionable["status"] if actionable
        else "planning"
    )
    return {
        "status": status,
        "current_stage": actionable["name"] if actionable else None,
        "progress": {
            "completed_stages": completed,
            "total_stages": len(stage_rows),
            "percent": round((completed / len(stage_rows)) * 100, 1) if stage_rows else 0,
        },
        "stages": stage_rows,
        "stage_outputs": stage_outputs,
        "media_outputs": {
            "references": _reference_outputs(artifacts),
            "assets": stage_outputs["assets"].get("media") or [],
            "renders": stage_outputs["compose"].get("media") or [],
        },
        "pending_approval": pending_approval,
        "final_render": final_render,
        "next_actions": _next_actions(project_id, status, pending_approval, final_render),
        **({"events": _recent_events(state)} if include_events else {}),
    }


def _r2_url_map(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    manifest = artifacts.get("asset_manifest") or {}
    for item in ((manifest.get("metadata") or {}).get("r2_assets") or []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if path:
            out[path] = item
    render_report = artifacts.get("render_report") or {}
    r2_output = (render_report.get("metadata") or {}).get("r2_output") or {}
    if isinstance(r2_output, dict):
        path = str((render_report.get("outputs") or [{}])[0].get("path") or "renders/final.mp4")
        out[path] = r2_output
    return out


def _upload_url(upload: dict[str, Any] | None) -> str | None:
    if not isinstance(upload, dict):
        return None
    url = upload.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    key = upload.get("key")
    if isinstance(key, str) and key:
        return storage.public_url_for(key)
    return None


def _media_url(project_id: str, base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/media/{quote(project_id)}/{quote(path.lstrip('/'))}"


def _thumb_url(project_id: str, base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/thumb/{quote(project_id)}/{quote(path.lstrip('/'))}?w=640"


def _public_or_media_url(project_id: str, base_url: str, path: str, r2_urls: dict[str, dict[str, Any]]) -> tuple[str, str]:
    upload = r2_urls.get(path)
    public_url = _upload_url(upload)
    if public_url:
        return public_url, "cdn"
    return _media_url(project_id, base_url, path), "board_media"


def _proposal_output(artifacts: dict[str, Any]) -> dict[str, Any]:
    proposal = artifacts.get("proposal_packet") or {}
    estimate = proposal.get("cost_estimate") or {}
    approval = proposal.get("approval") or {}
    concepts = proposal.get("concept_options") or []
    return {
        "artifact_key": "proposal_packet",
        "artifact_available": bool(proposal),
        "summary": {
            "concept_count": len(concepts),
            "selected_concept": (proposal.get("selected_concept") or {}).get("concept_id"),
            "approval_status": approval.get("status"),
            "approval_reason": approval.get("reason"),
            "estimated_total_usd": estimate.get("total_estimated_usd"),
            "initial_paid_generation_estimate_usd": estimate.get("initial_paid_generation_estimate_usd"),
            "sample_first": estimate.get("sample_first"),
            "conditioning_mode": proposal.get("conditioning_mode") or estimate.get("conditioning_mode"),
            "reference_asset_count": proposal.get("reference_asset_count") or estimate.get("reference_asset_count"),
        },
    }


def _script_output(artifacts: dict[str, Any]) -> dict[str, Any]:
    script = artifacts.get("script") or {}
    sections = script.get("sections") or []
    return {
        "artifact_key": "script",
        "artifact_available": bool(script),
        "summary": {
            "title": script.get("title"),
            "total_duration_seconds": script.get("total_duration_seconds"),
            "section_count": len(sections),
            "sections": [
                {
                    "id": section.get("id"),
                    "label": section.get("label"),
                    "text": section.get("text"),
                    "start_seconds": section.get("start_seconds"),
                    "end_seconds": section.get("end_seconds"),
                }
                for section in sections
            ],
        },
    }


def _scene_plan_output(artifacts: dict[str, Any]) -> dict[str, Any]:
    scene_plan = artifacts.get("scene_plan") or {}
    scenes = scene_plan.get("scenes") or []
    return {
        "artifact_key": "scene_plan",
        "artifact_available": bool(scene_plan),
        "summary": {
            "scene_count": len(scenes),
            "style_playbook": scene_plan.get("style_playbook"),
            "scenes": [
                {
                    "id": scene.get("id"),
                    "description": scene.get("description"),
                    "shot_intent": scene.get("shot_intent"),
                    "start_seconds": scene.get("start_seconds"),
                    "end_seconds": scene.get("end_seconds"),
                    "required_assets": scene.get("required_assets") or [],
                }
                for scene in scenes
            ],
        },
    }


def _assets_output(
    project_id: str,
    base_url: str,
    artifacts: dict[str, Any],
    r2_urls: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest = artifacts.get("asset_manifest") or {}
    media = []
    for asset in manifest.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("path") or "")
        url, source = _public_or_media_url(project_id, base_url, path, r2_urls) if path else (None, None)
        media.append({
            "id": asset.get("id"),
            "type": asset.get("type"),
            "scene_id": asset.get("scene_id"),
            "path": path,
            "url": url,
            "url_source": source,
            "thumbnail_url": _thumb_url(project_id, base_url, path) if path else None,
            "provider": asset.get("provider"),
            "source_tool": asset.get("source_tool"),
            "model": asset.get("model"),
            "duration_seconds": asset.get("duration_seconds"),
            "cost_usd": asset.get("cost_usd"),
            "quality_score": asset.get("quality_score"),
            "prompt": asset.get("prompt"),
        })
    metadata = manifest.get("metadata") or {}
    return {
        "artifact_key": "asset_manifest",
        "artifact_available": bool(manifest),
        "summary": {
            "asset_count": len(media),
            "total_cost_usd": manifest.get("total_cost_usd"),
            "sample_only": metadata.get("sample_only"),
            "generated_scene_count": metadata.get("generated_scene_count"),
            "total_scene_count": metadata.get("total_scene_count"),
            "review_required": metadata.get("review_required"),
            "blocker": metadata.get("blocker"),
        },
        "media": media,
    }


def _edit_output(artifacts: dict[str, Any]) -> dict[str, Any]:
    edit = artifacts.get("edit_decisions") or {}
    cuts = edit.get("cuts") or []
    return {
        "artifact_key": "edit_decisions",
        "artifact_available": bool(edit),
        "summary": {
            "render_runtime": edit.get("render_runtime"),
            "cut_count": len(cuts),
            "cuts": cuts,
        },
    }


def _compose_output(
    project_id: str,
    base_url: str,
    state: dict[str, Any],
    artifacts: dict[str, Any],
    r2_urls: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    render_report = artifacts.get("render_report") or {}
    media = []
    for output in render_report.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        path = str(output.get("path") or "")
        url, source = _public_or_media_url(project_id, base_url, path, r2_urls) if path else (None, None)
        media.append({**output, "url": url, "url_source": source, "thumbnail_url": _thumb_url(project_id, base_url, path) if path else None})
    known_paths = {item.get("path") for item in media}
    for render in ((state.get("media") or {}).get("renders") or []):
        path = str(render.get("path") or "")
        if not path or path in known_paths:
            continue
        url, source = _public_or_media_url(project_id, base_url, path, r2_urls)
        media.append({**render, "url": url, "url_source": source, "thumbnail_url": _thumb_url(project_id, base_url, path)})
    return {
        "artifact_key": "render_report",
        "artifact_available": bool(render_report),
        "summary": {
            "render_count": len(media),
            "verification_notes": render_report.get("verification_notes") or [],
            "qa_gate_status": ((render_report.get("metadata") or {}).get("qa_gate_status")),
            "qa": ((render_report.get("metadata") or {}).get("qa")),
            "final_review_ref": render_report.get("final_review_ref"),
        },
        "media": media,
    }


def _publish_output(artifacts: dict[str, Any]) -> dict[str, Any]:
    publish = artifacts.get("publish_log") or {}
    return {
        "artifact_key": "publish_log",
        "artifact_available": bool(publish),
        "summary": publish or {},
    }


def _reference_outputs(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    request = artifacts.get("job_request") or {}
    refs = []
    for asset in request.get("reference_assets") or []:
        if not isinstance(asset, dict):
            continue
        refs.append({
            "asset_id": asset.get("asset_id"),
            "filename": asset.get("filename"),
            "path": asset.get("path"),
            "url": asset.get("url"),
            "content_type": asset.get("content_type"),
            "source": asset.get("source"),
            "size": asset.get("size"),
        })
    return refs


def _final_render(
    project_id: str,
    base_url: str,
    state: dict[str, Any],
    artifacts: dict[str, Any],
    r2_urls: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    render_report = artifacts.get("render_report") or {}
    outputs = render_report.get("outputs") or []
    if outputs:
        output = outputs[0]
        path = str(output.get("path") or "renders/final.mp4")
        url, source = _public_or_media_url(project_id, base_url, path, r2_urls)
        return {**output, "path": path, "url": url, "url_source": source, "thumbnail_url": _thumb_url(project_id, base_url, path)}
    renders = (state.get("media") or {}).get("renders") or []
    if renders:
        render = renders[0]
        path = str(render.get("path") or "")
        if path:
            url, source = _public_or_media_url(project_id, base_url, path, r2_urls)
            return {**render, "path": path, "url": url, "url_source": source, "thumbnail_url": _thumb_url(project_id, base_url, path)}
    return None


def _pending_approval(project_id: str, state: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any] | None:
    awaiting = next((stage for stage in state.get("stages") or [] if stage.get("status") == "awaiting_human"), None)
    if not awaiting:
        return None
    stage = str(awaiting.get("name") or "")
    if stage == "proposal":
        proposal = artifacts.get("proposal_packet") or {}
        approval = proposal.get("approval") or {}
        request = artifacts.get("job_request") or {}
        video_model = str(request.get("video_model") or "")
        args: dict[str, Any] = {"project_id": project_id, "confirm_paid_generation": True}
        if video_model.startswith("seedance"):
            args["confirm_seedance_risk"] = True
        blocked = approval.get("status") == "blocked"
        return {
            "stage": stage,
            "blocked": blocked,
            "reason": approval.get("reason"),
            "message": approval.get("message") or approval.get("provider_warning"),
            "review_artifact": "proposal_packet",
            "approval_tool": None if blocked else "ray_approve_paid_generation",
            "approval_arguments": None if blocked else args,
            "required_before_approval": (
                "Attach references with ray_request_reference_upload/ray_confirm_reference or ray_attach_references."
                if blocked and approval.get("reason") == "reference_conditioning_expected_but_no_assets"
                else None
            ),
        }
    if stage == "assets":
        manifest = artifacts.get("asset_manifest") or {}
        metadata = manifest.get("metadata") or {}
        review_required = metadata.get("review_required") or {}
        blocker = metadata.get("blocker") or {}
        return {
            "stage": stage,
            "blocked": bool(blocker),
            "reason": blocker.get("type") or review_required.get("type"),
            "message": blocker.get("message") or review_required.get("message"),
            "review_artifact": "asset_manifest",
            "review_required": review_required or None,
            "blocker": blocker or None,
            "approval_tool": "ray_approve_asset_review" if review_required and not blocker else None,
            "approval_arguments": {"project_id": project_id, "confirm_asset_review_passed": True} if review_required and not blocker else None,
        }
    return {
        "stage": stage,
        "blocked": False,
        "message": f"{stage} is awaiting human review.",
        "approval_tool": None,
        "approval_arguments": None,
    }


def _next_actions(
    project_id: str,
    status: str,
    pending_approval: dict[str, Any] | None,
    final_render: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if final_render and final_render.get("url"):
        return [{"type": "download_final_mp4", "url": final_render["url"], "label": "Final render MP4"}]
    if pending_approval:
        actions = [{
            "type": "review",
            "stage": pending_approval.get("stage"),
            "artifact": pending_approval.get("review_artifact"),
            "message": pending_approval.get("message"),
        }]
        if pending_approval.get("approval_tool"):
            actions.append({
                "type": "approve",
                "tool": pending_approval["approval_tool"],
                "arguments": pending_approval["approval_arguments"],
            })
        if pending_approval.get("required_before_approval"):
            actions.append({"type": "blocked", "message": pending_approval["required_before_approval"]})
        return actions
    return [{"type": "poll", "tool": "ray_get_project_outputs", "arguments": {"project_id": project_id}, "status": status}]


def _recent_events(state: dict[str, Any]) -> list[dict[str, Any]]:
    events = state.get("events") or []
    return [
        {
            "ts": event.get("ts"),
            "event": event.get("event"),
            "tool": event.get("tool"),
            "scene_id": event.get("scene_id"),
            "success": event.get("success"),
            "duration_s": event.get("duration_s"),
            "cost_usd": event.get("cost_usd"),
            "error": event.get("error"),
        }
        for event in events[-30:]
        if isinstance(event, dict)
    ]


async def _revise_plan(args: dict[str, Any], base_url: str, publish_project: PublishHook | None) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    _safe_project_dir(project_id)
    mcp_only = {"project_id", "provider", "reference_urls", "reference_asset_ids", "reference_files"}
    payload = {k: v for k, v in args.items() if k not in mcp_only and v is not None}
    video_model = _video_model_from_provider(args.get("provider") or args.get("video_model"))
    if video_model:
        payload["video_model"] = video_model
    reference_assets = _collect_reference_assets(project_id, args)
    if reference_assets:
        payload["reference_assets"] = _merged_reference_assets(project_id, reference_assets)

    async def revise_and_publish() -> None:
        await asyncio.to_thread(jobs.revise_plan, project_id, payload)
        if publish_project:
            publish_project(project_id)

    asyncio.create_task(revise_and_publish())
    return {
        "ok": True,
        "status": "revision_queued",
        "project_id": project_id,
        "board_url": f"{base_url}/p/{project_id}",
        "monitor_tool": "ray_get_project_outputs",
        "monitor_arguments": {"project_id": project_id},
        "workflow": _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True),
        **({"provider": args.get("provider"), "video_model": video_model} if video_model else {}),
    }


async def _approve_paid_generation(args: dict[str, Any], base_url: str, publish_project: PublishHook | None) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    _safe_project_dir(project_id)
    if args.get("confirm_paid_generation") is not True:
        raise ValueError("confirm_paid_generation=true is required")
    override_no_references = args.get("override_no_references") is True
    confirm_seedance_risk = args.get("confirm_seedance_risk") is True
    await asyncio.to_thread(
        jobs.validate_paid_generation_allowed,
        project_id,
        override_no_references,
        confirm_seedance_risk,
    )

    async def run_and_publish() -> None:
        await asyncio.to_thread(
            jobs.approve_paid_generation,
            project_id,
            override_no_references,
            confirm_seedance_risk,
        )
        if publish_project:
            publish_project(project_id)

    asyncio.create_task(run_and_publish())
    return {
        "ok": True,
        "status": "paid_generation_queued",
        "project_id": project_id,
        "board_url": f"{base_url}/p/{project_id}",
        "monitor_tool": "ray_get_project_outputs",
        "monitor_arguments": {"project_id": project_id},
        "workflow": _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True),
    }


async def _approve_asset_review(args: dict[str, Any], base_url: str, publish_project: PublishHook | None) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    _safe_project_dir(project_id)
    if args.get("confirm_asset_review_passed") is not True:
        raise ValueError("confirm_asset_review_passed=true is required")
    result = await asyncio.to_thread(jobs.approve_asset_review, project_id)
    if publish_project:
        publish_project(project_id)
    result["board_url"] = f"{base_url}/p/{project_id}"
    result["monitor_tool"] = "ray_get_project_outputs"
    result["monitor_arguments"] = {"project_id": project_id}
    result["workflow"] = _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True)
    result["final_render"] = result["workflow"].get("final_render")
    result["final_render_url"] = (result["workflow"].get("final_render") or {}).get("url")
    return result


def _request_reference_upload(args: dict[str, Any], base_url: str) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    _safe_project_dir(project_id)
    filename = _safe_filename(str(args.get("filename") or "reference.png"))
    content_type = str(args.get("content_type") or _guess_content_type(filename))
    asset_id = f"ref_{int(time.time())}_{re.sub(r'[^a-zA-Z0-9]+', '', filename)[:24]}"
    rel_path = f"uploads/mcp/{asset_id}-{filename}"
    signed = storage.presigned_put(project_id, rel_path, content_type, REFERENCE_UPLOAD_TTL_SECONDS)
    pending = _read_pending_uploads(project_id)
    pending[asset_id] = {
        "asset_id": asset_id,
        "project_id": project_id,
        "filename": filename,
        "path": rel_path,
        "key": signed["key"],
        "url": signed.get("url"),
        "content_type": content_type,
        "expires_at": signed["expires_at"],
        "created_at": int(time.time()),
    }
    _write_pending_uploads(project_id, pending)
    return {
        "ok": True,
        "project_id": project_id,
        "asset_id": asset_id,
        "put_url": signed["put_url"],
        "expires_at": signed["expires_at"],
        "required_headers": signed["required_headers"],
        "confirm_tool": "ray_confirm_reference",
        "board_url": f"{base_url}/p/{project_id}",
    }


async def _confirm_reference(args: dict[str, Any], base_url: str, publish_project: PublishHook | None) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    asset_id = str(args.get("asset_id") or "")
    asset = _confirmed_asset_from_pending(project_id, asset_id)
    updated = _attach_assets_to_request(project_id, [asset])
    if publish_project:
        publish_project(project_id)
    await _queue_replan(project_id, publish_project)
    return {
        "ok": True,
        "status": "reference_attached_replan_queued",
        "project_id": project_id,
        "asset_id": asset_id,
        "reference_asset_count": _usable_reference_count(updated),
        "conditioning_mode": "image_to_video" if _usable_reference_count(updated) else "text_to_video",
        "board_url": f"{base_url}/p/{project_id}",
        "monitor_tool": "ray_get_project_outputs",
        "monitor_arguments": {"project_id": project_id},
        "workflow": _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True),
    }


async def _attach_references_tool(args: dict[str, Any], base_url: str, publish_project: PublishHook | None) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    _safe_project_dir(project_id)
    assets = _collect_reference_assets(project_id, args)
    if not assets:
        raise ValueError("No references supplied. Use reference_urls, reference_files, or reference_asset_ids.")
    updated = _attach_assets_to_request(project_id, assets)
    if publish_project:
        publish_project(project_id)
    await _queue_replan(project_id, publish_project)
    return {
        "ok": True,
        "status": "references_attached_replan_queued",
        "project_id": project_id,
        "attached_count": len(assets),
        "reference_asset_count": _usable_reference_count(updated),
        "conditioning_mode": "image_to_video" if _usable_reference_count(updated) else "text_to_video",
        "board_url": f"{base_url}/p/{project_id}",
        "monitor_tool": "ray_get_project_outputs",
        "monitor_arguments": {"project_id": project_id},
        "workflow": _mcp_workflow(project_id, load_board_state(_safe_project_dir(project_id)), base_url, include_events=True),
    }


def _reference_assets_from_urls(urls: list[Any]) -> list[dict[str, Any]]:
    assets = []
    for raw in urls:
        url = str(raw or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        path = urlparse(url).path
        filename = Path(path).name or "reference"
        assets.append({"url": url, "filename": filename, "path": path, "content_type": _guess_content_type(filename), "source": "mcp"})
    return assets


def _video_model_from_provider(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw or "").strip()
    if not value:
        return None
    if value in jobs.VIDEO_MODELS:
        return value
    if value not in MCP_PROVIDER_TO_MODEL:
        try:
            return jobs._normalize_video_model(value)
        except jobs.JobError:
            pass
        allowed = ", ".join([*MCP_VIDEO_PROVIDERS, *jobs.VIDEO_MODELS.keys()])
        raise ValueError(f"provider must be one of: {allowed}")
    model = MCP_PROVIDER_TO_MODEL[value]
    if model is None:
        raise ValueError("Happy Horse 1.0 is not wired in this hosted Ray build yet; no adapter exists in this repo.")
    return model


def _provider_from_request(request_data: dict[str, Any]) -> str:
    video_model = str(request_data.get("video_model") or "")
    for provider, model in MCP_PROVIDER_TO_MODEL.items():
        if model == video_model:
            return provider
    return "grok-imagine"


def _save_reference_files(project_id: str, files: list[Any]) -> list[dict[str, Any]]:
    saved = []
    total = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "reference.bin")
        content_type = str(item.get("content_type") or _guess_content_type(filename))
        raw_b64 = str(item.get("base64_data") or "")
        content = base64.b64decode(raw_b64, validate=True)
        total += len(content)
        if total > MAX_MCP_INLINE_UPLOAD_BYTES:
            raise ValueError(
                "reference_files inline payload is too large. Use ray_request_reference_upload, "
                "PUT the file to put_url, then call ray_confirm_reference."
            )
        upload = jobs.save_upload(project_id, filename, content)
        upload["content_type"] = content_type
        upload["source"] = "mcp"
        saved.append(upload)
    return saved


def _collect_reference_assets(project_id: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    assets = []
    assets.extend(_reference_assets_from_urls(args.get("reference_urls") or []))
    assets.extend(_save_reference_files(project_id, args.get("reference_files") or []))
    for asset_id in args.get("reference_asset_ids") or []:
        assets.append(_confirmed_asset_from_pending(project_id, str(asset_id)))
    return assets


def _pending_uploads_path(project_id: str) -> Path:
    return _safe_project_dir(project_id) / "artifacts" / "reference_uploads.json"


def _read_pending_uploads(project_id: str) -> dict[str, Any]:
    path = _pending_uploads_path(project_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_pending_uploads(project_id: str, data: dict[str, Any]) -> None:
    path = _pending_uploads_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _confirmed_asset_from_pending(project_id: str, asset_id: str) -> dict[str, Any]:
    _safe_project_dir(project_id)
    pending = _read_pending_uploads(project_id)
    item = pending.get(asset_id)
    if not item:
        raise ValueError(f"Unknown reference upload asset_id: {asset_id}")
    if int(item.get("expires_at") or 0) < int(time.time()):
        raise ValueError("Reference upload URL expired; request a new upload URL.")
    info = storage.object_info(str(item["key"]))
    asset = {
        "asset_id": asset_id,
        "path": item["path"],
        "filename": item["filename"],
        "url": info.get("url") or item.get("url"),
        "content_type": info.get("content_type") or item.get("content_type"),
        "size": info.get("size"),
        "bucket": info.get("bucket"),
        "key": info.get("key"),
        "source": "mcp_presigned_upload",
        "confirmed_at": int(time.time()),
    }
    pending[asset_id] = {**item, "confirmed": True, "asset": asset}
    _write_pending_uploads(project_id, pending)
    return asset


def _attach_assets_to_request(project_id: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = _job_request(project_id).get("reference_assets") or []
    merged = _merge_assets(existing, assets)
    _update_job_request(project_id, {
        "reference_assets": merged,
        "reference_conditioning_expected": True,
        "reference_assets_updated_at": int(time.time()),
    })
    return merged


def _merged_reference_assets(project_id: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_assets(_job_request(project_id).get("reference_assets") or [], assets)


def _merge_assets(existing: list[Any], new_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset in [*existing, *new_assets]:
        if not isinstance(asset, dict):
            continue
        key = str(asset.get("asset_id") or asset.get("key") or asset.get("url") or asset.get("path") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(asset)
    return merged


async def _queue_replan(project_id: str, publish_project: PublishHook | None) -> None:
    async def replan() -> None:
        try:
            refs = _job_request(project_id).get("reference_assets") or []
            await asyncio.to_thread(jobs.revise_plan, project_id, {"reference_assets": refs})
        except Exception:
            return
        if publish_project:
            publish_project(project_id)

    asyncio.create_task(replan())


def _job_request(project_id: str) -> dict[str, Any]:
    path = _safe_project_dir(project_id) / "artifacts" / "job_request.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _usable_reference_count(assets: list[dict[str, Any]]) -> int:
    count = 0
    for asset in assets:
        path = str(asset.get("path") or asset.get("filename") or "").lower()
        content_type = str(asset.get("content_type") or "").lower()
        url = str(asset.get("url") or "")
        if url.startswith(("http://", "https://")) and (content_type.startswith("image/") or path.endswith((".png", ".jpg", ".jpeg", ".webp"))):
            count += 1
    return count


def _safe_filename(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return clean[:140] or "reference.png"


def _update_job_request(project_id: str, updates: dict[str, Any]) -> None:
    project_dir = _safe_project_dir(project_id)
    path = project_dir / "artifacts" / "job_request.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _safe_project_dir(project_id: str) -> Path:
    if any(c in project_id for c in "/\\:") or project_id in {"", ".", ".."}:
        raise ValueError("invalid project_id")
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise ValueError(f"unknown project: {project_id}")
    return project_dir


def _title_from_prompt(prompt: str) -> str:
    words = re.sub(r"\s+", " ", prompt.strip()).split(" ")[:8]
    return " ".join(words) or "Ray video"


def _guess_content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".mp4"):
        return "video/mp4"
    return "application/octet-stream"


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
