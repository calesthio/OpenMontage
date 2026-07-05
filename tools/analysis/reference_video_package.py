"""Build a human-editable reference video replication package."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-video"


def _scene_speech(scene: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    if scene.get("speech"):
        return str(scene["speech"])
    start = float(scene.get("start", 0.0))
    end = float(scene.get("end", start))
    texts = [
        str(segment.get("text", "")).strip()
        for segment in segments
        if float(segment.get("end", 0.0)) > start
        and float(segment.get("start", 0.0)) < end
    ]
    return " ".join(text for text in texts if text).strip()


def _recommend_mode(scenes: list[dict[str, Any]], transcript_status: str) -> tuple[str, str]:
    has_speech = transcript_status == "ok" and any(
        str(scene.get("speech", "")).strip() for scene in scenes
    )
    if has_speech:
        return "seedance", "reference-video v1 统一走 Seedance 重制；口播文案、提示词和授权素材需人工确认后再生成。"
    return "seedance", "未获得可用口播转写，优先基于画面结构和人工确认提示词走 Seedance 重制。"


def _seedance_prompt(scene: dict[str, Any]) -> str:
    visual = str(scene.get("visual_summary", "")).strip()
    speech = str(scene.get("speech", "")).strip()
    camera_motion = str(scene.get("camera_motion", "")).strip()
    parts = [
        "Create a 4-15 second creator-video clip based on this approved scene.",
    ]
    if visual:
        parts.append(f"Visual: {visual}.")
    if speech:
        parts.append(f"On-screen spoken/script content: {speech}")
    if camera_motion:
        parts.append(f"Camera/motion: {camera_motion}.")
    parts.append("Use only team-approved uploaded assets for face, product, and brand references.")
    return " ".join(parts)


def _asset_slots(scene_id: str) -> list[dict[str, Any]]:
    return [
        {
            "slot": "subject_or_face_reference",
            "type": "image",
            "scene_id": scene_id,
            "required": False,
            "description": "Team-approved face, presenter, or subject reference image.",
        },
        {
            "slot": "product_or_brand_reference",
            "type": "image",
            "scene_id": scene_id,
            "required": False,
            "description": "Product, logo, packaging, or brand visual reference.",
        },
        {
            "slot": "background_or_motion_reference",
            "type": "image_or_video",
            "scene_id": scene_id,
            "required": False,
            "description": "Optional background, location, motion, or style reference.",
        },
    ]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, package: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    transcript = package["transcript"]
    lines = [
        "# Reference Video Replication Package",
        "",
        "## Source",
        "",
        f"- Input type: `{package['source'].get('input_type', 'unknown')}`",
        f"- Input: `{package['source'].get('input', '')}`",
        f"- Local video: `{package['source'].get('local_video_path', '')}`",
        f"- Duration: `{package['source'].get('duration_seconds', '')}` seconds",
        "",
        "## Raw Transcript",
        "",
    ]
    if transcript.get("status") == "pending_transcription":
        lines.extend(
            [
                f"Transcript pending: `{transcript.get('reason', 'unknown')}`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                transcript.get("raw_text", ""),
                "",
            ]
        )
    lines.extend(
        [
            "## Rewrite Draft",
            "",
            package["rewrite_draft"].get("text", ""),
            "",
            "## Scenes",
            "",
            "| Scene | Time | Visual | Speech | Production Hint |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for scene in package["scenes"]:
        lines.append(
            "| {scene_id} | {start:.2f}-{end:.2f}s | {visual} | {speech} | {hint} |".format(
                scene_id=scene.get("scene_id", ""),
                start=float(scene.get("start", 0.0)),
                end=float(scene.get("end", 0.0)),
                visual=str(scene.get("visual_summary", "")).replace("|", "\\|"),
                speech=str(scene.get("speech", "")).replace("|", "\\|"),
                hint=str(scene.get("production_hint", "")).replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## Editable Production Inputs",
            "",
            "- Script, Seedance prompts, and uploaded assets are editable before production.",
            "- Use only team-authorized face/presenter/product assets.",
            "",
            "| Scene | Editable Script | Seedance Prompt | Uploaded Assets |",
            "| --- | --- | --- | --- |",
        ]
    )
    custom_assets = package["editable_inputs"].get("custom_assets", [])
    for scene in package["scenes"]:
        production_inputs = scene.get("production_inputs", {})
        scene_assets = [
            str(asset.get("id") or asset.get("path", ""))
            for asset in custom_assets
            if asset.get("scene_id") in (None, "", scene.get("scene_id"))
        ]
        lines.append(
            "| {scene_id} | {script} | {prompt} | {assets} |".format(
                scene_id=scene.get("scene_id", ""),
                script=str(production_inputs.get("script_text", "")).replace("|", "\\|"),
                prompt=str(production_inputs.get("seedance_prompt", "")).replace("|", "\\|"),
                assets=", ".join(asset for asset in scene_assets if asset).replace("|", "\\|"),
            )
        )
    strategy = package["replication_strategy"]
    lines.extend(
        [
            "",
            "## Replication Strategy",
            "",
            f"- Recommended mode: `{strategy['recommended_mode']}`",
            f"- Reason: {strategy['reason']}",
            f"- Alternatives: `{', '.join(strategy['alternatives'])}`",
            "",
            "## Approval",
            "",
            f"- Status: `{package['approval']['status']}`",
            "- Production requires human review and team-authorized face/presenter assets.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


class ReferenceVideoPackage(BaseTool):
    name = "reference_video_package"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "reference_analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies."
    capabilities = [
        "replication_package",
        "reference_review_markdown",
        "strategy_recommendation",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=50,
        network_required=False,
    )
    idempotency_key_fields = [
        "reference_source",
        "reference_analysis",
        "reference_transcript",
    ]
    side_effects = ["writes replication package JSON and Markdown files"]

    input_schema = {
        "type": "object",
        "required": [
            "project_dir",
            "reference_source",
            "reference_analysis",
            "reference_transcript",
        ],
        "properties": {
            "project_dir": {"type": "string"},
            "reference_source": {"type": "object"},
            "reference_analysis": {"type": "object"},
            "reference_transcript": {"type": "object"},
            "custom_assets": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional user-uploaded or imported assets available for manual scene binding.",
            },
            "output_dir": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        project_dir = Path(inputs["project_dir"])
        source = dict(inputs["reference_source"])
        analysis = inputs.get("reference_analysis") or {}
        transcript_input = inputs.get("reference_transcript") or {}
        custom_assets = inputs.get("custom_assets") or []
        transcript_status = transcript_input.get("status", "ok")
        segments = transcript_input.get("segments") or []

        scenes: list[dict[str, Any]] = []
        for index, scene in enumerate(analysis.get("scenes") or [], start=1):
            start = float(scene.get("start", 0.0))
            scene_id = scene.get("scene_id") or f"s{index}"
            normalized = {
                "scene_id": scene_id,
                "start": start,
                "end": float(scene.get("end", start)),
                "visual_summary": scene.get("visual_summary", ""),
                "speech": _scene_speech(scene, segments),
                "camera_motion": scene.get("camera_motion", ""),
                "pacing": scene.get("pacing", "unknown"),
                "keyframes": scene.get("keyframes", []),
                "production_hint": scene.get(
                    "production_hint",
                    "seedance_remake",
                ),
            }
            normalized["production_inputs"] = {
                "status": "needs_human_edit",
                "script_text": normalized["speech"],
                "seedance_prompt": _seedance_prompt(normalized),
                "asset_slots": _asset_slots(scene_id),
                "selected_assets": [
                    asset
                    for asset in custom_assets
                    if asset.get("scene_id") in (None, "", scene_id)
                ],
            }
            scenes.append(normalized)

        recommended_mode, reason = _recommend_mode(scenes, transcript_status)
        raw_text = (
            transcript_input.get("raw_text", "")
            if transcript_status != "pending_transcription"
            else ""
        )
        package = {
            "version": "1.0",
            "source": source,
            "transcript": {
                "status": transcript_status,
                "raw_text": raw_text,
                "segments": segments,
            },
            "rewrite_draft": {
                "status": "needs_human_edit",
                "text": raw_text,
            },
            "editable_inputs": {
                "status": "needs_human_edit",
                "editable_fields": [
                    "rewrite_draft.text",
                    "scenes[].production_inputs.script_text",
                    "scenes[].production_inputs.seedance_prompt",
                    "scenes[].production_inputs.selected_assets",
                ],
                "custom_assets": custom_assets,
                "notes": [
                    "Images and prompt text can be edited before production.",
                    "Production requires team-authorized uploaded assets.",
                ],
            },
            "scenes": scenes,
            "replication_strategy": {
                "recommended_mode": recommended_mode,
                "alternatives": ["seedance"],
                "reason": reason,
            },
            "approval": {
                "status": "pending_human_review",
                "required_before_production": True,
                "requires_team_authorized_face_or_avatar": True,
            },
        }
        if transcript_status == "pending_transcription":
            package["transcript"]["reason"] = transcript_input.get(
                "reason",
                "transcription_unavailable",
            )

        output_dir = Path(
            inputs.get("output_dir")
            or project_dir / "artifacts" / "reference-video-analysis"
        )
        source_name = _safe_slug(
            Path(str(source.get("local_video_path") or source.get("input") or "reference")).stem
        )
        json_path = output_dir / f"{source_name}-replication-package.json"
        markdown_path = output_dir / f"{source_name}-replication-review.md"

        _write_json(json_path, package)
        _write_markdown(markdown_path, package)

        return ToolResult(
            success=True,
            data={
                "replication_package": package,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
            artifacts=[str(json_path), str(markdown_path)],
        )
