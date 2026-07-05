"""Reverse-engineer editable Seedance prompts from reference-video keyframes."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from tools.analysis.doubao_vision_understand import DoubaoVisionUnderstand
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


APPROVED_STATUSES = {"approved", "approved_with_changes"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-prompts"


def _load_package(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("replication_package"):
        return copy.deepcopy(inputs["replication_package"])
    package_path = inputs.get("replication_package_path")
    if not package_path:
        raise ValueError("replication_package or replication_package_path is required")
    return json.loads(Path(package_path).read_text(encoding="utf-8"))


def _resolve_path(project_dir: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    project_candidate = project_dir / path
    if project_candidate.exists():
        return str(project_candidate)
    return str(path)


def _scene_prompt(scene: dict[str, Any], package: dict[str, Any]) -> str:
    production_inputs = scene.get("production_inputs") or {}
    speech = (
        production_inputs.get("script_text")
        or scene.get("speech")
        or (package.get("rewrite_draft") or {}).get("text")
        or ""
    )
    return (
        "你是短视频视觉分析和 Seedance 2.0 提示词专家。"
        "请根据给定参考视频关键帧和口播文本，反推出可编辑的生成提示词。"
        "直接返回一个简短 JSON 对象，不要解释、不要 Markdown、不要代码块。字段："
        "visual_summary, camera_motion, pacing, seedance_prompt, notes。"
        "要求 seedance_prompt 使用中文，描述主体、场景、构图、镜头运动、光线、节奏、产品/人物一致性；"
        "不要包含侵犯肖像权或平台水印复刻要求。"
        f"\n场景 ID: {scene.get('scene_id', '')}"
        f"\n原始视觉摘要: {scene.get('visual_summary', '')}"
        f"\n口播/脚本: {speech}"
    )


class ReferencePromptReverse(BaseTool):
    name = "reference_prompt_reverse"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "reference_analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = (
        "Configure a vision provider. For Doubao: set DOUBAO_VISION_API_KEY or ARK_API_KEY, "
        "and optionally DOUBAO_VISION_MODEL."
    )
    agent_skills = ["video-understand", "ai-video-gen"]
    capabilities = [
        "reference_keyframe_prompt_reverse",
        "seedance_prompt_enrichment",
        "scene_visual_summary_enrichment",
    ]
    supports = {
        "providers": ["doubao"],
        "paid_generation": False,
        "vision_api_call": True,
        "mutates_approved_package": False,
    }
    best_for = [
        "using a vision model to turn keyframes and transcript into better Seedance prompts",
        "improving reference-video replication packages before human approval",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=20,
        network_required=True,
    )
    idempotency_key_fields = ["replication_package", "replication_package_path", "provider"]
    side_effects = ["writes prompt-reversed replication package JSON"]
    user_visible_verification = [
        "Review every reversed Seedance prompt before approving production",
    ]

    input_schema = {
        "type": "object",
        "required": ["project_dir"],
        "properties": {
            "project_dir": {"type": "string"},
            "replication_package": {"type": "object"},
            "replication_package_path": {"type": "string"},
            "provider": {"type": "string", "enum": ["doubao"], "default": "doubao"},
            "model": {"type": "string"},
            "max_keyframes_per_scene": {"type": "integer", "default": 3},
            "max_tokens": {"type": "integer", "default": 4096},
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "replication_package": {"type": "object"},
            "json_path": {"type": "string"},
            "scene_results": {"type": "array"},
        },
    }

    def __init__(self, vision_tool: Any | None = None) -> None:
        self._vision_tool = vision_tool

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def _provider_tool(self, provider: str) -> Any:
        if self._vision_tool is not None:
            return self._vision_tool
        if provider == "doubao":
            return DoubaoVisionUnderstand()
        raise ValueError(f"Unsupported vision provider: {provider}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            package = _load_package(inputs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))

        approval_status = str((package.get("approval") or {}).get("status", ""))
        if approval_status in APPROVED_STATUSES:
            return ToolResult(
                success=False,
                error="Cannot reverse prompts for an already approved package; edit the pending package instead.",
            )

        provider = str(inputs.get("provider", "doubao"))
        try:
            vision_tool = self._provider_tool(provider)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        project_dir = Path(inputs["project_dir"])
        max_keyframes = int(inputs.get("max_keyframes_per_scene", 3))
        updated = copy.deepcopy(package)
        scene_results: list[dict[str, Any]] = []

        for scene in updated.get("scenes") or []:
            keyframes = [
                _resolve_path(project_dir, str(path))
                for path in (scene.get("keyframes") or [])[:max_keyframes]
            ]
            if not keyframes:
                scene_results.append(
                    {
                        "scene_id": scene.get("scene_id", ""),
                        "status": "skipped",
                        "reason": "no_keyframes",
                    }
                )
                continue

            vision_inputs = {
                "image_paths": keyframes,
                "prompt": _scene_prompt(scene, updated),
                "response_format": "json",
                "max_tokens": int(inputs.get("max_tokens", 4096)),
                **({"model": inputs["model"]} if inputs.get("model") else {}),
            }
            vision_result = vision_tool.execute(vision_inputs)
            if not vision_result.success:
                return ToolResult(
                    success=False,
                    error=(
                        f"Vision prompt reverse failed for {scene.get('scene_id', '')}: "
                        f"{vision_result.error}"
                    ),
                    cost_usd=vision_result.cost_usd,
                    model=vision_result.model,
                )

            parsed = vision_result.data.get("parsed") or {}
            self._apply_scene_result(scene, parsed)
            scene_results.append(
                {
                    "scene_id": scene.get("scene_id", ""),
                    "status": "updated",
                    "provider": provider,
                    "model": vision_result.model or vision_result.data.get("model"),
                    "keyframes": keyframes,
                    "parsed": parsed,
                }
            )

        editable_inputs = updated.setdefault("editable_inputs", {})
        editable_inputs["status"] = "needs_human_edit"
        approval = updated.setdefault("approval", {})
        approval["status"] = "pending_human_review"
        approval["required_before_production"] = True
        approval["paid_generation_started"] = False
        updated.setdefault("edit_history", []).append(
            {
                "tool": self.name,
                "provider": provider,
                "updated_scene_count": len(
                    [result for result in scene_results if result.get("status") == "updated"]
                ),
            }
        )

        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts" / "reference-prompts")
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = _safe_slug(
            Path(
                str(
                    (updated.get("source") or {}).get("local_video_path")
                    or (updated.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-prompts-reversed-package.json"
        json_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "replication_package": updated,
                "json_path": str(json_path),
                "scene_results": scene_results,
            },
            artifacts=[str(json_path)],
        )

    def _apply_scene_result(self, scene: dict[str, Any], parsed: dict[str, Any]) -> None:
        if str(parsed.get("visual_summary", "")).strip():
            scene["visual_summary"] = str(parsed["visual_summary"]).strip()
        if str(parsed.get("camera_motion", "")).strip():
            scene["camera_motion"] = str(parsed["camera_motion"]).strip()
        if str(parsed.get("pacing", "")).strip():
            scene["pacing"] = str(parsed["pacing"]).strip()

        prompt = str(parsed.get("seedance_prompt", "")).strip()
        if prompt:
            production_inputs = scene.setdefault("production_inputs", {})
            production_inputs["status"] = "needs_human_edit"
            production_inputs["seedance_prompt"] = prompt
