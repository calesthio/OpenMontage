"""Tencent Hunyuan (腾讯混元) 3D asset generation via TokenHub API.

Calls the Tencent TokenHub API (tokenhub.tencentmaas.com) using simple Bearer
token authentication

API flow: POST /v1/api/3d/submit -> poll /v1/api/3d/query -> download
``data[].url`` mesh files. The professional API returns the OBJ entry as a
ZIP package (obj + mtl + textures); the tool detects it by magic bytes and
extracts it automatically.

Only the ``hy-3d-3.1`` model is supported. TokenHub request parameters mirror
the native Tencent Cloud actions ``SubmitHunyuanTo3DProJob`` /
``QueryHunyuanTo3DProJob`` but use lowercase snake_case names:

- Submit: https://cloud.tencent.com/document/api/1804/123447
- Query:  https://cloud.tencent.com/document/api/1804/123448
- TokenHub 3D guide: https://cloud.tencent.com/document/product/1823/130082

The 3.1 model supports text-to-3D, image-to-3D, multi-view (up to eight
views) image-to-3D, and untextured geometry (white-model) generation.
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
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

_HOST = "tokenhub.tencentmaas.com"
_SUBMIT_PATH = "/v1/api/3d/submit"
_QUERY_PATH = "/v1/api/3d/query"

# TokenHub model identifiers
_MODEL = "hy-3d-3.1"

# Generate types available on the 3.1 model.
_GENERATE_TYPES_31 = ("Normal", "Geometry")

# Multi-view image viewpoints supported by the 3.1 model (all of them).
_VIEW_TYPES = (
    "left", "right", "back", "top", "bottom", "left_front", "right_front",
)

# Mesh extensions we download from the completed job's data array.
_MESH_SUFFIXES = {".glb", ".gltf", ".obj", ".fbx", ".stl", ".usdz"}

# TokenHub 3D post-paid pricing: 1 credit = 0.12 RMB, ~7.2 RMB/USD.
# Source: https://cloud.tencent.com.cn/document/product/1823/130055 (1积分对应0.12元)
_CREDIT_TO_USD = 0.12 / 7.2

# Per-job credit consumption for 混元生3D (专业版). Source:
# https://cloud.tencent.com.cn/document/product/1804/123461
_CREDITS_BASE = {"Normal": 20.0, "Geometry": 15.0}
_CREDITS_MULTI_VIEW = 10.0
_CREDITS_PBR = 10.0
_CREDITS_FACE_COUNT = 10.0
_CREDITS_RESULT_FORMAT = 5.0


class HunyuanCloud3D(BaseTool):
    """Tencent Hunyuan 3D asset generation via TokenHub API."""
    name = "hunyuan_cloud_3d"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "3d_asset_generation"
    provider = "hunyuan_cloud"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:TENCENT_TOKENHUB_API_KEY"]
    install_instructions = (
        "Set TENCENT_TOKENHUB_API_KEY to your Tencent Cloud TokenHub API key.\n"
        "  Get it at https://console.cloud.tencent.com/tokenhub"
    )
    agent_skills = ["3d-asset-generation", "threejs-loaders", "threejs-materials"]

    capabilities = ["text_to_3d", "image_to_3d", "textured_glb", "pbr_mesh", "white_model"]
    supports = {
        "text_to_3d": True,
        "image_to_3d": True,
        "multi_view": True,
        "pbr": True,
        "glb": True,
        "seed": False,
    }
    best_for = [
        "Hunyuan 3D 3.1 text/image/multi-view-to-3D via Tencent TokenHub API",
        "simple Bearer-token auth (no TC3 signing required)",
        "direct Tencent Cloud quota usage (not through a third-party gateway)",
        "Chinese-language prompt understanding",
    ]
    not_good_for = [
        "Repeated foliage or rocks that should come from a licensed local catalog",
        "offline generation or air-gapped environments",
        "users without Tencent Cloud account and real-name verification",
    ]
    fallback_tools = ["fal_3d", "atlas_3d"]

    input_schema = {
        "type": "object",
        "required": ["operation", "output_path"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["text_to_3d", "image_to_3d"],
                "description": "Generation mode.",
            },
            "model": {
                "type": "string",
                "enum": ["hy-3d-3.1"],
                "default": "hy-3d-3.1",
                "description": "Only hy-3d-3.1 is supported.",
            },
            "prompt": {
                "type": "string",
                "minLength": 3,
                "maxLength": 1024,
                "description": (
                    "Text-to-3D description. Max 1024 UTF-8 characters. "
                    "Describe one isolated object: silhouette, materials, "
                    "style, scale. Cannot be combined with images."
                ),
            },
            "image_url": {
                "type": "string",
                "description": (
                    "Public image URL for image-to-3D (front view). "
                    "Max 8MB, sides 128-5000px, jpg/png/jpeg/webp."
                ),
            },
            "image_path": {
                "type": "string",
                "description": (
                    "Local image path for image-to-3D (front view). "
                    "Base64-encoded inline. Max ~6MB raw."
                ),
            },
            "multi_view_images": {
                "type": "array",
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "required": ["view"],
                    "properties": {
                        "view": {"type": "string", "enum": list(_VIEW_TYPES)},
                        "image_url": {"type": "string"},
                        "image_path": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "description": (
                    "Optional multi-view reference images for image_to_3d. "
                    "view: left/right/back/top/bottom/left_front/right_front, "
                    "one image per view. The front view comes from image_url "
                    "or image_path. Encoded total must stay under 8MB."
                ),
            },
            "enable_pbr": {
                "type": "boolean",
                "default": False,
                "description": "Enable PBR material generation (default false).",
            },
            "face_count": {
                "type": "integer",
                "minimum": 3000,
                "maximum": 1500000,
                "description": "Target triangle count (default 500000).",
            },
            "generate_type": {
                "type": "string",
                "enum": list(_GENERATE_TYPES_31),
                "default": "Normal",
                "description": (
                    "Normal: textured geometry. Geometry: untextured white model (enable_pbr ignored)"
                ),
            },
            "result_format": {
                "type": "string",
                "enum": ["STL", "USDZ", "FBX"],
                "description": (
                    "Optional extra export format. OBJ and GLB are always "
                    "returned (GLB only for Geometry)."
                ),
            },
            "output_path": {"type": "string"},
            "poll_timeout_seconds": {
                "type": "integer",
                "minimum": 30,
                "maximum": 1800,
                "default": 900,
                "description": "Maximum seconds to wait for generation.",
            },
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "3d_asset"}

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=2000, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, backoff_seconds=2.0, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "operation", "model", "prompt", "image_url", "image_path",
        "multi_view_images", "enable_pbr", "face_count", "generate_type",
        "result_format",
    ]
    side_effects = [
        "calls the Tencent TokenHub API (Bearer-token submit + poll + download)",
        "may upload a local input image inline",
        "writes generated 3D assets and a provenance manifest",
    ]
    user_visible_verification = [
        "Inspect the downloaded mesh from front, back, silhouette, UV, and PBR material views before scene assembly"
    ]
    quality_score = 0.88

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _api_key() -> str | None:
        val = os.environ.get("TENCENT_TOKENHUB_API_KEY", "")
        if val and not val.strip().startswith("#"):
            return val.strip()
        return None

    # ------------------------------------------------------------------
    # Tool contract methods
    # ------------------------------------------------------------------

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate cost in USD from the official per-job credit schedule.

        Per the 混元生3D billing overview, the professional model deducts
        credits per job: Normal = 20, Geometry = 15. Optional extras stack:
        MultiViewImages +10, EnablePBR +10, FaceCount +10, ResultFormat +5.
        Post-paid price is 0.12 RMB/credit, settled daily; prepaid packs run
        0.09-0.10 RMB/credit. Failed jobs are never billed. Uses the
        post-paid rate and ~7.2 RMB/USD.

        Sources:
        - https://cloud.tencent.com.cn/document/product/1804/123461 (积分扣减说明)
        - https://cloud.tencent.com.cn/document/product/1823/130054 (计费方式)
        - https://cloud.tencent.com.cn/document/product/1823/130055 (模型价格)
        """
        credits = _CREDITS_BASE.get(inputs.get("generate_type", "Normal"), 20.0)
        if inputs.get("multi_view_images"):
            credits += _CREDITS_MULTI_VIEW
        if bool(inputs.get("enable_pbr", False)):
            credits += _CREDITS_PBR
        if inputs.get("face_count") is not None:
            credits += _CREDITS_FACE_COUNT
        if inputs.get("result_format"):
            credits += _CREDITS_RESULT_FORMAT
        return round(credits * _CREDIT_TO_USD, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate wall-clock time in seconds.

        Tencent publishes no official latency for the 3D professional model.
        300s covers the typical queue + generate window; the poll loop is the
        hard timeout.
        """
        return 300.0

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="TENCENT_TOKENHUB_API_KEY not set. " + self.install_instructions,
            )

        validation_error = self._validate(inputs)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Hunyuan TokenHub 3D generation failed: {self._safe_error(exc)}",
            )
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _validate(self, inputs: dict[str, Any]) -> str | None:
        if not inputs.get("output_path"):
            return "output_path is required for hunyuan_cloud_3d generation"
        operation = str(inputs.get("operation") or "")
        if operation not in {"text_to_3d", "image_to_3d"}:
            return f"Unknown operation {operation!r}"
        if operation == "text_to_3d" and not inputs.get("prompt"):
            return "prompt is required for text_to_3d"
        if operation != "text_to_3d" and inputs.get("prompt"):
            return "prompt cannot be combined with image inputs"
        if operation == "image_to_3d":
            if not (inputs.get("image_url") or inputs.get("image_path")):
                return "image_to_3d requires image_url or image_path"
            if inputs.get("image_url") and inputs.get("image_path"):
                return "provide only one of image_url or image_path, not both"
        if operation != "image_to_3d" and inputs.get("multi_view_images"):
            return "multi_view_images is only valid with image_to_3d"
        for item in inputs.get("multi_view_images") or []:
            view = item.get("view")
            if view not in _VIEW_TYPES:
                return f"unsupported multi-view viewpoint {view!r}"
            if item.get("image_url") and item.get("image_path"):
                return f"view {view}: provide only one of image_url or image_path"
            if not (item.get("image_url") or item.get("image_path")):
                return f"view {view}: image_url or image_path is required"
        generate_type = inputs.get("generate_type", "Normal")
        if generate_type not in _GENERATE_TYPES_31:
            return (
                f"generate_type {generate_type!r} is not available on "
                f"{_MODEL} (LowPoly and Sketch are 3.0-only)"
            )
        if inputs.get("model") and inputs.get("model") != _MODEL:
            return f"only model {_MODEL!r} is supported, got {inputs['model']!r}"
        return None

    # ------------------------------------------------------------------
    # Generation pipeline
    # ------------------------------------------------------------------

    def _generate(self, inputs: dict[str, Any], *, api_key: str) -> ToolResult:
        payload = self._build_payload(inputs)
        job_id = self._submit_task(payload, api_key=api_key)
        completed = self._poll_task(
            job_id,
            api_key=api_key,
            poll_timeout=int(inputs.get("poll_timeout_seconds", 900)),
        )

        files = completed.get("data") or []
        if not isinstance(files, list) or not files:
            raise RuntimeError(f"TokenHub job {job_id} completed without downloadable files")

        destination = Path(str(inputs["output_path"])).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        outputs: list[str] = []
        packages: list[str] = []
        preview_urls: list[str] = []
        written = 0
        for file_info in files:
            file_type = str(file_info.get("type", "")).lower()
            url = file_info.get("url")
            if not url:
                continue
            if not any(file_type.startswith(prefix) for prefix in ("glb", "gltf", "obj", "fbx", "stl", "usdz")):
                continue  # skip preview images and unknown entries
            if file_info.get("preview_image_url"):
                preview_urls.append(str(file_info["preview_image_url"]))
            download = requests.get(url, timeout=300)
            download.raise_for_status()
            content = download.content

            # The professional API often returns a ZIP package (obj + mtl +
            # textures) instead of a bare mesh. Detect by magic bytes rather
            # than the URL suffix, which is unreliable here.
            if content[:2] == b"PK":
                package_dir = destination.parent / f"{destination.stem}-pkg"
                if package_dir.exists():
                    package_dir = destination.parent / f"{destination.stem}-pkg-{len(packages) + 1:02d}"
                package_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    members = [
                        name for name in archive.namelist()
                        if name and not name.endswith("/")
                        and ".." not in Path(name).parts
                        and not Path(name).is_absolute()
                    ]
                    archive.extractall(package_dir, members=members)
                for member in members:
                    extracted = package_dir / member
                    if Path(member).suffix.lower() in _MESH_SUFFIXES:
                        outputs.append(str(extracted))
                packages.append(str(package_dir))
                continue

            suffix = Path(urlparse(url).path).suffix.lower()
            if suffix not in _MESH_SUFFIXES:
                suffix = f".{file_type}" if file_type in {"glb", "gltf", "obj", "fbx", "stl", "usdz"} else ".glb"
            if written == 0:
                target = destination if destination.suffix.lower() in _MESH_SUFFIXES else destination.with_suffix(suffix)
            else:
                target = destination.with_name(f"{destination.stem}-{written:02d}{suffix}")
            target.write_bytes(content)
            outputs.append(str(target))
            written += 1
        if not outputs:
            raise RuntimeError(f"TokenHub job {job_id} returned no mesh files: {files}")

        manifest = destination.with_suffix(".provenance.json")
        manifest.write_text(json.dumps({
            "version": "1.0",
            "provider": "hunyuan_cloud",
            "route": "tokenhub",
            "model": _MODEL,
            "job_id": job_id,
            "operation": inputs.get("operation"),
            "prompt": inputs.get("prompt"),
            "parameters": self._provenance_parameters(inputs, payload),
            "preview_image_urls": preview_urls,
            "packages": packages,
            "source_url": "https://cloud.tencent.com/document/product/1823/130082",
            "outputs": outputs,
        }, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "provider": "hunyuan_cloud",
                "route": "tokenhub",
                "model": _MODEL,
                "operation": inputs.get("operation"),
                "job_id": job_id,
                "outputs": outputs,
                "preview_image_urls": preview_urls,
            },
            artifacts=[*outputs, str(manifest)],
            cost_usd=self.estimate_cost(inputs),
            model=_MODEL,
        )

    # ------------------------------------------------------------------
    # Payload construction (TokenHub snake_case, mirrors SubmitHunyuanTo3DProJob)
    # ------------------------------------------------------------------

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if inputs.get("prompt"):
            payload["prompt"] = inputs["prompt"]
        if inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]
        elif inputs.get("image_path"):
            payload["image_base64"] = self._encode_image(inputs["image_path"])
        multi_view = inputs.get("multi_view_images")
        if multi_view:
            payload["multi_view_images"] = [
                {
                    "view_type": item["view"],
                    **(
                        {"view_image_url": item["image_url"]}
                        if item.get("image_url")
                        else {"view_image_base64": self._encode_image(item["image_path"])}
                    ),
                }
                for item in multi_view
            ]
        if "enable_pbr" in inputs:
            payload["enable_pbr"] = bool(inputs["enable_pbr"])
        if inputs.get("face_count") is not None:
            payload["face_count"] = int(inputs["face_count"])
        payload["generate_type"] = inputs.get("generate_type", "Normal")
        if inputs.get("result_format"):
            payload["result_format"] = inputs["result_format"]
        return payload

    @staticmethod
    def _provenance_parameters(inputs: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """Payload parameters with base64 image data replaced by source paths.

        The manifest must stay small and readable — inline base64 blobs can
        reach megabytes. Record the local path or public URL that produced
        each image instead.
        """
        params = {key: value for key, value in payload.items() if key != "prompt"}
        if "image_base64" in params:
            params.pop("image_base64")
            params["image_path"] = inputs.get("image_path")
        if params.get("multi_view_images"):
            params["multi_view_images"] = [
                {
                    "view": item["view"],
                    **(
                        {"image_url": item["image_url"]}
                        if item.get("image_url")
                        else {"image_path": item.get("image_path")}
                    ),
                }
                for item in inputs.get("multi_view_images") or []
            ]
        return params

    @staticmethod
    def _encode_image(path: str) -> str:
        """Read a local image file and return a base64-encoded string."""
        import base64

        image_path = Path(path)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")

        raw = image_path.read_bytes()
        max_raw = 6 * 1024 * 1024  # 6MB raw ≈ 8MB base64
        if len(raw) > max_raw:
            raise ValueError(
                f"Image too large ({len(raw)} bytes). Max ~6MB raw (8MB base64-encoded)."
            )

        return base64.b64encode(raw).decode("ascii")

    # ------------------------------------------------------------------
    # API communication (TokenHub OpenAI-compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def _auth_headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _submit_task(self, payload: dict[str, Any], *, api_key: str) -> str:
        """Submit a 3D generation task and return the job id."""
        body = {"model": _MODEL, **payload}
        resp = requests.post(
            f"https://{_HOST}{_SUBMIT_PATH}",
            json=body,
            headers=self._auth_headers(api_key),
            timeout=30,
        )
        data = self._json_or_raise(resp)
        self._check_response(data)

        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"TokenHub 3D submit returned no job id: {data}")
        return job_id

    def _poll_task(self, job_id: str, *, api_key: str, poll_timeout: int) -> dict[str, Any]:
        """Poll /v1/api/3d/query until completion, return the completed body."""
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            time.sleep(5)

            resp = requests.post(
                f"https://{_HOST}{_QUERY_PATH}",
                json={"model": _MODEL, "id": job_id},
                headers=self._auth_headers(api_key),
                timeout=30,
            )
            data = self._json_or_raise(resp)
            self._check_response(data)

            status = str(data.get("status", "")).lower()
            if status == "completed":
                return data
            if status == "failed":
                error = data.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else str(error or "unknown error")
                raise RuntimeError(f"TokenHub 3D job {job_id} failed: {message}")
            if status not in {"queued", "running", "in_progress"}:
                raise RuntimeError(f"TokenHub 3D job {job_id} returned unknown status: {status}")

        raise TimeoutError(f"TokenHub 3D job {job_id} did not finish within {poll_timeout}s")

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        """Redact secret values from exception messages."""
        msg = str(exc)
        val = os.environ.get("TENCENT_TOKENHUB_API_KEY", "")
        if val:
            msg = msg.replace(val, "[redacted]")
        return msg

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        """Parse JSON response body or raise with HTTP status."""
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from TokenHub API: HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _check_response(payload: dict[str, Any]) -> None:
        """Check the TokenHub API response for errors.

        TokenHub returns errors at the top level with an ``error`` field.
        """
        error = payload.get("error")
        if error:
            if isinstance(error, dict):
                message = error.get("message", "unknown error")
                code = error.get("code", error.get("type", "unknown"))
            else:
                message, code = str(error), "unknown"
            raise RuntimeError(f"TokenHub API error: code={code}, message={message}")
