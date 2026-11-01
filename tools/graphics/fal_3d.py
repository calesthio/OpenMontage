"""Text/image-to-3D and object reconstruction through fal.ai."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


_MODELS = {
    "text_to_3d": "fal-ai/hunyuan-3d/v3.1/rapid/text-to-3d",
    "image_to_3d": "fal-ai/hunyuan-3d/v3.1/rapid/image-to-3d",
    "reconstruct_objects": "fal-ai/sam-3/3d-objects",
}


def _api_key() -> str | None:
    return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")


def _download_file(file_info: dict[str, Any], destination: Path) -> Path:
    url = str(file_info["url"])
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".glb", ".gltf", ".obj", ".fbx", ".ply", ".zip"}:
        suffix = ".glb" if file_info.get("content_type") == "model/gltf-binary" else destination.suffix
    target = destination.with_suffix(suffix or ".glb")
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return target


class Fal3D(BaseTool):
    name = "fal_3d"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "3d_asset_generation"
    provider = "fal"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API
    dependencies = ["env:FAL_KEY"]
    install_instructions = "Set FAL_KEY (or FAL_AI_API_KEY). Create a key at https://fal.ai/dashboard/keys."
    agent_skills = ["3d-asset-generation", "threejs-loaders", "threejs-materials"]
    capabilities = ["text_to_3d", "image_to_3d", "multi_object_reconstruction", "textured_glb", "pbr_mesh"]
    supports = {
        "text_to_3d": True,
        "image_to_3d": True,
        "multi_object": True,
        "pbr": True,
        "glb": True,
        "seed": True,
    }
    best_for = [
        "Image-conditioned hero props whose silhouette must match concept art",
        "Extracting multiple textured GLBs and placements from a regional concept image",
        "Rapid textured environment assets",
    ]
    not_good_for = ["Rendering a complete cinematic world", "Large repeated scatter libraries"]
    input_schema = {
        "type": "object",
        "required": ["operation", "output_path"],
        "properties": {
            "operation": {"type": "string", "enum": list(_MODELS)},
            "prompt": {"type": "string"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "output_path": {"type": "string"},
            "enable_pbr": {"type": "boolean", "default": True},
            "seed": {"type": "integer"},
            "export_textured_glb": {"type": "boolean", "default": True},
            "detection_threshold": {"type": "number", "minimum": 0.1, "maximum": 1.0},
            "poll_timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 1800, "default": 900},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "3d_asset"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=2000, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["operation", "prompt", "image_url", "image_path", "enable_pbr", "seed"]
    side_effects = ["calls fal.ai", "may upload a local input image", "writes generated 3D assets and provenance"]
    user_visible_verification = ["Inspect silhouette, back-side completion, topology, texture seams, and material response"]
    quality_score = 0.88

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("operation") == "reconstruct_objects":
            return 0.02
        return 0.225 + (0.15 if inputs.get("enable_pbr", True) else 0.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        key = _api_key()
        if not key:
            return ToolResult(success=False, error="fal.ai API key not set. " + self.install_instructions)
        operation = str(inputs.get("operation") or "")
        if operation not in _MODELS:
            return ToolResult(success=False, error=f"Unknown operation {operation!r}")
        if operation == "text_to_3d" and not inputs.get("prompt"):
            return ToolResult(success=False, error="prompt is required for text_to_3d")
        if operation != "text_to_3d" and not (inputs.get("image_url") or inputs.get("image_path")):
            return ToolResult(success=False, error=f"image_url or image_path is required for {operation}")

        payload: dict[str, Any] = {}
        if operation == "text_to_3d":
            payload["prompt"] = inputs["prompt"]
            payload["enable_pbr"] = bool(inputs.get("enable_pbr", True))
        else:
            image_url = inputs.get("image_url")
            if not image_url:
                from tools.video._shared import upload_image_fal
                image_url = upload_image_fal(str(inputs["image_path"]))
            payload["image_url" if operation == "reconstruct_objects" else "input_image_url"] = image_url
            if operation == "image_to_3d":
                payload["enable_pbr"] = bool(inputs.get("enable_pbr", True))
            else:
                payload["export_textured_glb"] = bool(inputs.get("export_textured_glb", True))
                if inputs.get("prompt"):
                    payload["prompt"] = inputs["prompt"]
                if inputs.get("detection_threshold") is not None:
                    payload["detection_threshold"] = inputs["detection_threshold"]
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
        model = _MODELS[operation]
        started = time.time()
        try:
            submit = requests.post(f"https://queue.fal.run/{model}", headers=headers, json=payload, timeout=45)
            submit.raise_for_status()
            queued = submit.json()
            status_url = queued["status_url"]
            response_url = queued["response_url"]
            deadline = time.monotonic() + int(inputs.get("poll_timeout_seconds", 900))
            while time.monotonic() < deadline:
                status_response = requests.get(status_url, headers=headers, timeout=30)
                status_response.raise_for_status()
                status = str(status_response.json().get("status", "")).upper()
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(f"request {status.lower()}")
                time.sleep(3)
            else:
                raise TimeoutError("fal.ai request exceeded the poll timeout")
            result_response = requests.get(response_url, headers=headers, timeout=45)
            result_response.raise_for_status()
            data = result_response.json()

            destination = Path(str(inputs["output_path"])).expanduser().resolve()
            file_infos: list[dict[str, Any]] = []
            if operation == "reconstruct_objects":
                if data.get("model_glb"):
                    file_infos.append(data["model_glb"])
                file_infos.extend(data.get("individual_glbs") or [])
            else:
                urls = data.get("model_urls") or {}
                candidate = urls.get("glb") or data.get("model_glb") or urls.get("obj")
                if candidate:
                    file_infos.append(candidate)
            if not file_infos:
                raise RuntimeError("fal.ai completed without a downloadable mesh")

            artifacts: list[str] = []
            for index, file_info in enumerate(file_infos):
                target = destination if index == 0 else destination.with_name(f"{destination.stem}-{index:02d}{destination.suffix}")
                artifacts.append(str(_download_file(file_info, target)))
            provenance = destination.with_suffix(".provenance.json")
            provenance.write_text(json.dumps({
                "version": "1.0",
                "provider": "fal",
                "model": model,
                "request_id": queued.get("request_id"),
                "operation": operation,
                "prompt": inputs.get("prompt"),
                "metadata": data.get("metadata"),
                "source_url": f"https://fal.ai/models/{model}",
                "outputs": artifacts,
            }, indent=2), encoding="utf-8")
            artifacts.append(str(provenance))
        except Exception as exc:
            return ToolResult(success=False, error=f"fal.ai 3D generation failed: {exc}")

        return ToolResult(
            success=True,
            data={"provider": "fal", "model": model, "operation": operation, "outputs": artifacts[:-1]},
            artifacts=artifacts,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - started, 2),
            seed=inputs.get("seed"),
            model=model,
        )
