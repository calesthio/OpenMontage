"""Text-to-3D asset generation through Atlas Cloud.

The tool deliberately exposes mesh generation as its own capability. Atlas's
HTTP endpoint happens to be named ``generateImage`` for historical reasons;
that implementation detail must not make 3D assets look like image outputs to
the OpenMontage registry or pipeline.
"""

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


_MODEL = "tripo-h3.1/text-to-3d"
_ENV_KEYS = ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY", "ATLAS_API_KEY")


def _api_key() -> str | None:
    return next((os.environ.get(name) for name in _ENV_KEYS if os.environ.get(name)), None)


def _extension(url: str, content_type: str | None, fallback: str = ".glb") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".glb", ".gltf", ".fbx", ".obj", ".zip"}:
        return suffix
    if content_type == "model/gltf-binary":
        return ".glb"
    return fallback


class Atlas3D(BaseTool):
    name = "atlas_3d"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "3d_asset_generation"
    provider = "atlas_cloud"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API
    dependencies = ["env:ATLASCLOUD_API_KEY"]
    install_instructions = (
        "Set ATLASCLOUD_API_KEY (ATLAS_CLOUD_API_KEY and ATLAS_API_KEY are also accepted). "
        "Create a key at https://www.atlascloud.ai/."
    )
    agent_skills = ["3d-asset-generation", "threejs-loaders", "threejs-materials"]
    capabilities = ["text_to_3d", "textured_glb", "pbr_mesh", "seeded_mesh_generation"]
    supports = {
        "text_to_3d": True,
        "texture": True,
        "pbr": True,
        "detailed_geometry": True,
        "face_limit": True,
        "seed": True,
        "glb": True,
    }
    best_for = [
        "Unique hero props and environment pieces described in text",
        "Textured PBR GLB assets for Blender or Three.js",
    ]
    not_good_for = [
        "Whole coherent worlds in one request",
        "Repeated foliage or rocks that should come from a licensed local catalog",
    ]
    input_schema = {
        "type": "object",
        "required": ["prompt", "output_path"],
        "properties": {
            "prompt": {"type": "string", "minLength": 3, "maxLength": 1024},
            "negative_prompt": {"type": "string"},
            "output_path": {"type": "string"},
            "texture": {"type": "boolean", "default": True},
            "pbr": {"type": "boolean", "default": True},
            "texture_quality": {"type": "string", "enum": ["standard", "detailed"], "default": "standard"},
            "geometry_quality": {"type": "string", "enum": ["standard", "detailed"], "default": "standard"},
            "face_limit": {"type": "integer", "minimum": 1000, "maximum": 2000000},
            "model_seed": {"type": "integer"},
            "image_seed": {"type": "integer"},
            "texture_seed": {"type": "integer"},
            "auto_size": {"type": "boolean", "default": True},
            "quad": {"type": "boolean", "default": False},
            "poll_timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 1800, "default": 900},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "3d_asset"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=1000, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "prompt", "negative_prompt", "texture", "pbr", "texture_quality",
        "geometry_quality", "face_limit", "model_seed", "image_seed", "texture_seed",
    ]
    side_effects = ["calls the Atlas Cloud API", "writes a generated mesh and provenance manifest"]
    user_visible_verification = [
        "Inspect the downloaded mesh from front, back, silhouette, UV, and PBR material views before scene assembly"
    ]
    quality_score = 0.86

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        texture = bool(inputs.get("texture", True))
        texture_quality = inputs.get("texture_quality", "standard")
        cost = 0.22 if not texture else (0.44 if texture_quality == "detailed" else 0.33)
        if inputs.get("geometry_quality", "standard") == "detailed":
            cost += 0.22
        if inputs.get("quad", False):
            cost += 0.055
        return round(cost, 3)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        key = _api_key()
        if not key:
            return ToolResult(success=False, error="Atlas Cloud API key not set. " + self.install_instructions)

        output = Path(str(inputs["output_path"])).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "model": _MODEL,
            "prompt": inputs["prompt"],
            "texture": bool(inputs.get("texture", True)),
            "pbr": bool(inputs.get("pbr", True)),
            "texture_quality": inputs.get("texture_quality", "standard"),
            "geometry_quality": inputs.get("geometry_quality", "standard"),
            "auto_size": bool(inputs.get("auto_size", True)),
            "quad": bool(inputs.get("quad", False)),
        }
        for key_name in ("negative_prompt", "face_limit", "model_seed", "image_seed", "texture_seed"):
            if inputs.get(key_name) is not None:
                payload[key_name] = inputs[key_name]

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        started = time.time()
        try:
            submit = requests.post(
                "https://api.atlascloud.ai/api/v1/model/generateImage",
                headers=headers,
                json=payload,
                timeout=45,
            )
            submit.raise_for_status()
            prediction = submit.json()["data"]
            prediction_id = prediction["id"]
            deadline = time.monotonic() + int(inputs.get("poll_timeout_seconds", 900))
            while time.monotonic() < deadline:
                poll = requests.get(
                    f"https://api.atlascloud.ai/api/v1/model/prediction/{prediction_id}",
                    headers=headers,
                    timeout=30,
                )
                poll.raise_for_status()
                prediction = poll.json().get("data", poll.json())
                status = str(prediction.get("status", "")).lower()
                if status in {"completed", "succeeded"}:
                    break
                if status in {"failed", "cancelled"}:
                    raise RuntimeError(str(prediction.get("error") or f"prediction {status}"))
                time.sleep(3)
            else:
                raise TimeoutError(f"Prediction {prediction_id} exceeded the poll timeout")

            files = list(prediction.get("files") or [])
            mesh_file = next(
                (item for item in files if str(item.get("type", "")).lower() == "glb"),
                None,
            ) or next(
                (item for item in files if _extension(str(item.get("url", "")), item.get("content_type")) == ".glb"),
                None,
            )
            if mesh_file is None:
                outputs = [url for url in prediction.get("outputs") or [] if isinstance(url, str)]
                mesh_url = next((url for url in outputs if Path(urlparse(url).path).suffix.lower() == ".glb"), None)
                if mesh_url is None:
                    raise RuntimeError("Atlas prediction completed without a GLB output")
                mesh_file = {"url": mesh_url, "content_type": "model/gltf-binary"}

            mesh_url = str(mesh_file["url"])
            if output.suffix.lower() != ".glb":
                output = output.with_suffix(_extension(mesh_url, mesh_file.get("content_type")))
            download = requests.get(mesh_url, timeout=180)
            download.raise_for_status()
            output.write_bytes(download.content)

            manifest = output.with_suffix(".provenance.json")
            manifest.write_text(json.dumps({
                "version": "1.0",
                "provider": "atlas_cloud",
                "model": _MODEL,
                "prediction_id": prediction_id,
                "prompt": inputs["prompt"],
                "parameters": {key: value for key, value in payload.items() if key != "prompt"},
                "source_url": "https://www.atlascloud.ai/models/tripo-h3.1/text-to-3d",
                "output": str(output),
            }, indent=2), encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"Atlas Cloud 3D generation failed: {exc}")

        return ToolResult(
            success=True,
            data={"provider": "atlas_cloud", "model": _MODEL, "output": str(output), "prediction_id": prediction_id},
            artifacts=[str(output), str(manifest)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - started, 2),
            seed=inputs.get("model_seed"),
            model=_MODEL,
        )
