"""Video generation through KIE.AI Market API.

KIE is a multi-model gateway similar in role to fal.ai.  This tool gives
OpenMontage a non-fal route for Seedance/Kling-style clips while preserving the
same selector-driven provider contract used by the rest of the project.
"""

from __future__ import annotations

import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

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


KIE_API_BASE = "https://api.kie.ai"
KIE_UPLOAD_BASE = "https://kieai.redpandaai.co"

KIE_MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "bytedance/seedance-2": {
        "operations": {"text_to_video", "image_to_video", "reference_to_video", "first_last_frame_to_video"},
        "durations": [4, 5, 8, 10, 15],
        "default_duration": 5,
        "resolutions": ["480p", "720p", "1080p"],
        "default_resolution": "720p",
        "supports_audio": True,
    },
    "bytedance/seedance-2-fast": {
        "operations": {"text_to_video", "image_to_video", "reference_to_video", "first_last_frame_to_video"},
        "durations": [4, 5, 8, 10, 15],
        "default_duration": 5,
        "resolutions": ["480p", "720p", "1080p"],
        "default_resolution": "720p",
        "supports_audio": True,
    },
    "kling/v3-turbo-text-to-video": {
        "operations": {"text_to_video"},
        "durations": [5, 10],
        "default_duration": 5,
        "resolutions": ["720p", "1080p"],
        "default_resolution": "720p",
        "supports_audio": False,
    },
    "kling/v3-turbo-image-to-video": {
        "operations": {"image_to_video"},
        "durations": [5, 10],
        "default_duration": 5,
        "resolutions": ["720p", "1080p"],
        "default_resolution": "720p",
        "supports_audio": False,
    },
}


def _duration_to_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    text = str(value).strip().lower().removesuffix("s")
    return int(float(text))


class KieVideo(BaseTool):
    name = "kie_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kie"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set KIE_API_KEY to your KIE.AI API key.\n"
        "  Get one from https://kie.ai after signing in."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "first_last_frame_to_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "first_last_frame_to_video": True,
        "native_audio": True,
        "local_image_upload": True,
        "seedance_2": True,
        "kling": True,
    }
    best_for = [
        "non-fal.ai access to Seedance/Kling video models",
        "image-to-video from local reference images via KIE upload",
        "short vertical social clips with 5-15s model generations",
    ]
    not_good_for = ["offline generation", "long-form continuous video"]
    fallback_tools = ["kling_video", "seedance_video", "minimax_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "first_last_frame_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": list(KIE_MODEL_DEFAULTS.keys()),
                "default": "bytedance/seedance-2",
            },
            "duration": {
                "type": ["string", "integer"],
                "description": "Duration in seconds. Seedance supports 4-15s; Kling commonly supports 5/10s.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "default": "720p",
            },
            "generate_audio": {"type": "boolean", "default": False},
            "web_search": {"type": "boolean", "default": False},
            "nsfw_checker": {"type": "boolean", "default": False},
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "image_path": {"type": "string", "description": "Local reference image path for image_to_video"},
            "reference_image_url": {"type": "string", "description": "Alias for image_url"},
            "reference_image_path": {"type": "string", "description": "Alias for image_path"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "first_frame_url": {"type": "string"},
            "first_frame_path": {"type": "string"},
            "last_frame_url": {"type": "string"},
            "last_frame_path": {"type": "string"},
            "callBackUrl": {"type": "string"},
            "poll_interval_seconds": {"type": "number", "default": 5},
            "timeout_seconds": {"type": "integer", "default": 900},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls KIE.AI API"]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("KIE_API_KEY") or os.environ.get("KIE_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Return a rough USD estimate.

        KIE bills in credits and changes model pricing over time.  Keep this
        deliberately conservative; provider-returned creditsConsumed is reported
        in the final result when available.
        """
        variant = inputs.get("model_variant", "bytedance/seedance-2")
        meta = KIE_MODEL_DEFAULTS.get(variant, KIE_MODEL_DEFAULTS["bytedance/seedance-2"])
        duration = _duration_to_int(inputs.get("duration"), meta["default_duration"])
        if "fast" in variant:
            return 0.06 * (duration / 5)
        if "kling" in variant:
            return 0.12 * (duration / 5)
        return 0.10 * (duration / 5)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        variant = inputs.get("model_variant", "bytedance/seedance-2")
        if "fast" in variant:
            return 45.0
        return 90.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(success=False, error="KIE_API_KEY not set. " + self.install_instructions)

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        model = self._resolve_model(inputs.get("model_variant", "bytedance/seedance-2"), operation)
        meta = KIE_MODEL_DEFAULTS.get(model)
        if not meta:
            return ToolResult(success=False, error=f"Unsupported KIE model_variant: {model}")
        if operation not in meta["operations"]:
            return ToolResult(success=False, error=f"KIE model {model} does not support operation {operation}")

        try:
            payload = self._build_create_payload(inputs, model, operation, meta, api_key)
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            submit_resp = requests.post(
                f"{KIE_API_BASE}/api/v1/jobs/createTask",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            if submit_data.get("code") != 200:
                return ToolResult(success=False, error=f"KIE task creation failed: {submit_data}")
            task_id = submit_data.get("data", {}).get("taskId")
            if not task_id:
                return ToolResult(success=False, error=f"KIE response missing taskId: {submit_data}")

            record = self._poll_task(api_key, task_id, inputs)
            result_json = record.get("resultJson") or "{}"
            result_data = json.loads(result_json) if isinstance(result_json, str) else result_json
            result_urls = result_data.get("resultUrls") or []
            if not result_urls:
                return ToolResult(success=False, error=f"KIE task succeeded but returned no resultUrls: {record}")
            video_url = result_urls[0]

            output_path = Path(inputs.get("output_path", "kie_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            download_resp = requests.get(video_url, timeout=180)
            if download_resp.status_code >= 400:
                # Some KIE URLs require a temporary download URL conversion.
                video_url = self._get_download_url(api_key, video_url)
                download_resp = requests.get(video_url, timeout=180)
            download_resp.raise_for_status()
            output_path.write_bytes(download_resp.content)
        except Exception as e:
            return ToolResult(success=False, error=f"KIE video generation failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        credits = record.get("creditsConsumed")
        return ToolResult(
            success=True,
            data={
                "provider": "kie",
                "model": model,
                "task_id": task_id,
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "output": str(output_path),
                "output_path": str(output_path),
                "source_url": video_url,
                "format": "mp4",
                "credits_consumed": credits,
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    @staticmethod
    def _resolve_model(model_variant: str, operation: str) -> str:
        if model_variant == "kling/v3-turbo-text-to-video" and operation == "image_to_video":
            return "kling/v3-turbo-image-to-video"
        if model_variant == "kling/v3-turbo-image-to-video" and operation == "text_to_video":
            return "kling/v3-turbo-text-to-video"
        return model_variant

    def _build_create_payload(
        self,
        inputs: dict[str, Any],
        model: str,
        operation: str,
        meta: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        duration = _duration_to_int(inputs.get("duration"), meta["default_duration"])
        if duration not in meta["durations"]:
            # KIE docs accept Seedance 4-15s, while some model pages list examples.
            # Clamp only for Kling-style limited variants; allow the general Seedance range.
            if model.startswith("bytedance/seedance") and 4 <= duration <= 15:
                pass
            else:
                allowed = ", ".join(str(d) for d in meta["durations"])
                raise ValueError(f"duration={duration} is not supported by {model}; allowed: {allowed}")

        resolution = inputs.get("resolution") or meta["default_resolution"]
        if resolution not in meta["resolutions"]:
            raise ValueError(f"resolution={resolution} is not supported by {model}")

        input_payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "duration": duration if model.startswith("bytedance/seedance") else str(duration),
            "resolution": resolution,
        }

        if model.startswith("bytedance/seedance"):
            input_payload["aspect_ratio"] = inputs.get("aspect_ratio", "16:9")
            input_payload["generate_audio"] = bool(inputs.get("generate_audio", False))
            input_payload["web_search"] = bool(inputs.get("web_search", False))
            input_payload["nsfw_checker"] = bool(inputs.get("nsfw_checker", False))
        elif model.startswith("kling/") and operation == "image_to_video":
            # Kling v3 turbo image-to-video docs only require prompt/image_urls/duration/resolution.
            pass

        first_frame = self._normalize_url_or_upload(
            api_key, inputs.get("first_frame_url"), inputs.get("first_frame_path")
        )
        last_frame = self._normalize_url_or_upload(
            api_key, inputs.get("last_frame_url"), inputs.get("last_frame_path")
        )
        image_url = self._normalize_url_or_upload(
            api_key,
            inputs.get("image_url") or inputs.get("reference_image_url"),
            inputs.get("image_path") or inputs.get("reference_image_path"),
        )
        reference_urls = list(inputs.get("reference_image_urls") or [])
        for path in inputs.get("reference_image_paths") or []:
            reference_urls.append(self._upload_file(api_key, path, upload_path="openmontage"))

        if operation == "image_to_video":
            if model.startswith("kling/"):
                urls = reference_urls or ([image_url] if image_url else [])
                if not urls:
                    raise ValueError("image_to_video with KIE Kling requires image_url/image_path/reference_image_urls")
                input_payload["image_urls"] = urls
            else:
                frame = first_frame or image_url
                if not frame:
                    raise ValueError("image_to_video requires image_url/image_path/first_frame_url/first_frame_path")
                input_payload["first_frame_url"] = frame
        elif operation == "first_last_frame_to_video":
            if not first_frame or not last_frame:
                raise ValueError("first_last_frame_to_video requires first_frame and last_frame")
            input_payload["first_frame_url"] = first_frame
            input_payload["last_frame_url"] = last_frame
        elif operation == "reference_to_video":
            if image_url:
                reference_urls.insert(0, image_url)
            if not reference_urls:
                raise ValueError("reference_to_video requires at least one reference image URL/path")
            input_payload["reference_image_urls"] = reference_urls[:9]

        payload: dict[str, Any] = {"model": model, "input": input_payload}
        if inputs.get("callBackUrl"):
            payload["callBackUrl"] = inputs["callBackUrl"]
        return payload

    @staticmethod
    def _normalize_url_or_upload(api_key: str, url: str | None, path: str | None) -> str | None:
        if url:
            return url
        if path:
            return KieVideo._upload_file(api_key, path, upload_path="openmontage")
        return None

    @staticmethod
    def _upload_file(api_key: str, path_str: str, upload_path: str = "openmontage") -> str:
        import requests

        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as f:
            resp = requests.post(
                f"{KIE_UPLOAD_BASE}/api/file-stream-upload",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, f, mime_type)},
                data={"uploadPath": upload_path, "fileName": path.name},
                timeout=120,
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200 and not data.get("success"):
            raise RuntimeError(f"KIE file upload failed: {data}")
        file_url = KieVideo._extract_uploaded_file_url(data)
        if not file_url:
            raise RuntimeError(f"KIE file upload response missing fileUrl/downloadUrl: {data}")
        return file_url

    @staticmethod
    def _extract_uploaded_file_url(upload_response: dict[str, Any]) -> str | None:
        """Return the usable URL from KIE file-upload response variants.

        KIE docs show `data.fileUrl`, while the live file-stream API may return
        `data.downloadUrl` plus `data.filePath`.  Market video endpoints accept a
        normal HTTPS URL, so prefer `fileUrl` when present and fall back to the
        temporary `downloadUrl` returned by the live API.
        """
        payload = upload_response.get("data") or {}
        if not isinstance(payload, dict):
            return None
        return payload.get("fileUrl") or payload.get("downloadUrl")

    @staticmethod
    def _poll_task(api_key: str, task_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        import requests

        deadline = time.time() + int(inputs.get("timeout_seconds", 900))
        interval = float(inputs.get("poll_interval_seconds", 5))
        headers = {"Authorization": f"Bearer {api_key}"}
        last_record: dict[str, Any] | None = None
        while time.time() < deadline:
            resp = requests.get(
                f"{KIE_API_BASE}/api/v1/jobs/recordInfo",
                headers=headers,
                params={"taskId": task_id},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            record = payload.get("data") or {}
            last_record = record
            state = record.get("state")
            if state == "success":
                return record
            if state == "fail":
                raise RuntimeError(f"KIE task failed: {record.get('failCode')} {record.get('failMsg')}")
            time.sleep(interval)
            interval = min(interval * 1.25, 30.0)
        raise TimeoutError(f"KIE task {task_id} timed out. Last status: {last_record}")

    @staticmethod
    def _get_download_url(api_key: str, url: str) -> str:
        import requests

        resp = requests.post(
            f"{KIE_API_BASE}/api/v1/common/download-url",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"KIE download-url conversion failed: {data}")
        return data["data"]
