from __future__ import annotations

import json
import os
import re
import secrets
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# This folder lives at <OpenMontage>/gpt_gateway.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.checkpoint import (  # noqa: E402
    get_latest_checkpoint,
    get_next_stage,
    init_project,
    write_checkpoint,
)
from lib.paths import PROJECTS_DIR  # noqa: E402
from lib.pipeline_loader import (  # noqa: E402
    get_stage_order,
    get_stage_skill,
    list_pipelines,
    load_pipeline_readonly,
)
from tools.tool_registry import registry  # noqa: E402

app = FastAPI(
    title="OpenMontage GPT Gateway",
    version="0.1.0",
    description=(
        "Authenticated API for a Custom GPT to drive OpenMontage through its "
        "native pipeline manifests, stage skills, tool registry, checkpoints "
        "and render outputs."
    ),
)

PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
ARTIFACT_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


class ProjectCreate(BaseModel):
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    title: str = Field(min_length=1, max_length=200)
    pipeline_type: str
    style_playbook: str | None = None


class ToolRequest(BaseModel):
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    inputs: dict[str, Any] = Field(default_factory=dict)
    allow_paid: bool = False
    allow_side_effects: bool = False


class CheckpointRequest(BaseModel):
    stage: str
    status: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    pipeline_type: str | None = None
    style_playbook: str | None = None
    checkpoint_policy: str = "guided"
    human_approval_required: bool = False
    human_approved: bool = False
    review: dict[str, Any] | None = None
    cost_snapshot: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("GPT_GATEWAY_API_KEY")
    if not expected:
        raise HTTPException(500, "GPT_GATEWAY_API_KEY is not configured on the server")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")


def ensure_project_id(project_id: str) -> str:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise HTTPException(400, "Invalid project_id")
    return project_id


def project_dir(project_id: str) -> Path:
    ensure_project_id(project_id)
    path = (PROJECTS_DIR / project_id).resolve()
    base = PROJECTS_DIR.resolve()
    if base not in path.parents and path != base:
        raise HTTPException(400, "Invalid project path")
    return path


def require_project(project_id: str) -> Path:
    path = project_dir(project_id)
    if not path.exists() or not (path / "project.json").exists():
        raise HTTPException(404, "Project not found")
    return path


def serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    return value


def read_text(path: Path, max_chars: int = 120_000) -> str:
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"File not found: {path.name}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars]


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "openmontage-gpt-gateway", "version": "0.1.0"}


@app.get("/api/v1/instructions/core", dependencies=[Depends(require_api_key)])
def core_instructions() -> dict[str, Any]:
    return {
        "agent_guide": read_text(ROOT / "AGENT_GUIDE.md"),
        "project_context": read_text(ROOT / "PROJECT_CONTEXT.md"),
    }


@app.get("/api/v1/pipelines", dependencies=[Depends(require_api_key)])
def pipelines() -> dict[str, Any]:
    return {"pipelines": sorted(list_pipelines())}


@app.get("/api/v1/pipelines/{pipeline_name}", dependencies=[Depends(require_api_key)])
def pipeline_manifest(pipeline_name: str) -> dict[str, Any]:
    try:
        manifest = load_pipeline_readonly(pipeline_name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "name": pipeline_name,
        "stage_order": get_stage_order(manifest),
        "manifest": manifest,
    }


@app.get(
    "/api/v1/pipelines/{pipeline_name}/stages/{stage_name}/instructions",
    dependencies=[Depends(require_api_key)],
)
def stage_instructions(pipeline_name: str, stage_name: str) -> dict[str, Any]:
    try:
        manifest = load_pipeline_readonly(pipeline_name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    skill = get_stage_skill(manifest, stage_name)
    if not skill:
        raise HTTPException(404, f"No stage skill declared for {pipeline_name}/{stage_name}")

    skill_path = (ROOT / skill).resolve()
    root = ROOT.resolve()
    if root not in skill_path.parents:
        raise HTTPException(400, "Invalid skill path")

    return {
        "pipeline": pipeline_name,
        "stage": stage_name,
        "skill_path": skill,
        "instructions": read_text(skill_path),
    }


@app.get("/api/v1/capabilities/summary", dependencies=[Depends(require_api_key)])
def capabilities_summary() -> dict[str, Any]:
    registry.ensure_discovered()
    return serialize(registry.provider_menu_summary())


@app.get("/api/v1/tools/{tool_name}", dependencies=[Depends(require_api_key)])
def tool_info(tool_name: str) -> dict[str, Any]:
    registry.ensure_discovered()
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(404, f"Unknown tool: {tool_name}")
    return serialize(tool.get_info())


@app.post("/api/v1/projects", dependencies=[Depends(require_api_key)])
def create_project(req: ProjectCreate) -> dict[str, Any]:
    if req.pipeline_type not in list_pipelines():
        raise HTTPException(400, f"Unknown pipeline_type: {req.pipeline_type}")

    path = init_project(
        req.project_id,
        title=req.title,
        pipeline_type=req.pipeline_type,
        style_playbook=req.style_playbook,
    )
    return {
        "project_id": req.project_id,
        "project_dir": str(path),
        "pipeline_type": req.pipeline_type,
        "next_stage": get_next_stage(PROJECTS_DIR, req.project_id, req.pipeline_type),
    }


@app.get("/api/v1/projects/{project_id}/state", dependencies=[Depends(require_api_key)])
def project_state(project_id: str) -> dict[str, Any]:
    pdir = require_project(project_id)
    marker = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    pipeline_type = marker.get("pipeline_type")
    latest = get_latest_checkpoint(PROJECTS_DIR, project_id)
    final_render = pdir / "renders" / "final.mp4"
    return {
        "project": marker,
        "latest_checkpoint": latest,
        "next_stage": get_next_stage(PROJECTS_DIR, project_id, pipeline_type),
        "final_render_ready": final_render.exists(),
    }


@app.post("/api/v1/tools/{tool_name}/dry-run", dependencies=[Depends(require_api_key)])
def dry_run_tool(tool_name: str, req: ToolRequest) -> dict[str, Any]:
    registry.ensure_discovered()
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(404, f"Unknown tool: {tool_name}")

    pdir = require_project(req.project_id)
    inputs = dict(req.inputs)
    inputs.setdefault("project_dir", str(pdir))
    return serialize(tool.dry_run(inputs))


@app.post("/api/v1/tools/{tool_name}/execute", dependencies=[Depends(require_api_key)])
def execute_tool(tool_name: str, req: ToolRequest) -> dict[str, Any]:
    registry.ensure_discovered()
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(404, f"Unknown tool: {tool_name}")

    pdir = require_project(req.project_id)
    inputs = dict(req.inputs)
    inputs.setdefault("project_dir", str(pdir))

    dry = tool.dry_run(inputs)
    estimated_cost = float(dry.get("estimated_cost_usd", 0.0) or 0.0)
    side_effects = list(getattr(tool, "side_effects", []) or [])

    if estimated_cost > 0 and not req.allow_paid:
        raise HTTPException(
            409,
            detail={
                "approval_required": "paid_tool",
                "estimated_cost_usd": estimated_cost,
                "message": "Ask the user for approval, then retry with allow_paid=true.",
            },
        )

    if side_effects and not req.allow_side_effects:
        raise HTTPException(
            409,
            detail={
                "approval_required": "side_effects",
                "side_effects": side_effects,
                "message": "Ask the user for approval, then retry with allow_side_effects=true.",
            },
        )

    try:
        result = tool.execute(inputs)
    except Exception as exc:
        raise HTTPException(500, f"Tool execution failed: {exc}") from exc
    return serialize(result)


@app.post("/api/v1/projects/{project_id}/checkpoint", dependencies=[Depends(require_api_key)])
def checkpoint(project_id: str, req: CheckpointRequest) -> dict[str, Any]:
    pdir = require_project(project_id)
    marker = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    pipeline_type = req.pipeline_type or marker.get("pipeline_type")

    try:
        path = write_checkpoint(
            PROJECTS_DIR,
            project_id,
            req.stage,
            req.status,
            req.artifacts,
            pipeline_type=pipeline_type,
            style_playbook=req.style_playbook,
            checkpoint_policy=req.checkpoint_policy,
            human_approval_required=req.human_approval_required,
            human_approved=req.human_approved,
            review=req.review,
            cost_snapshot=req.cost_snapshot,
            error=req.error,
            metadata=req.metadata,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "checkpoint_path": str(path),
        "next_stage": get_next_stage(PROJECTS_DIR, project_id, pipeline_type),
    }


@app.get(
    "/api/v1/projects/{project_id}/artifacts/{artifact_name}",
    dependencies=[Depends(require_api_key)],
)
def artifact(project_id: str, artifact_name: str) -> dict[str, Any]:
    if not ARTIFACT_NAME_RE.fullmatch(artifact_name):
        raise HTTPException(400, "Invalid artifact name")

    pdir = require_project(project_id)
    candidates = [
        pdir / "artifacts" / artifact_name,
        pdir / "artifacts" / f"{artifact_name}.json",
    ]

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        if path.suffix.lower() == ".json":
            return {
                "artifact": artifact_name,
                "data": json.loads(path.read_text(encoding="utf-8")),
            }
        return {"artifact": artifact_name, "text": read_text(path)}

    raise HTTPException(404, "Artifact not found")


@app.get("/api/v1/projects/{project_id}/render", dependencies=[Depends(require_api_key)])
def final_render(project_id: str):
    path = require_project(project_id) / "renders" / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "Final render is not ready")
    return FileResponse(path, media_type="video/mp4", filename=f"{project_id}.mp4")
