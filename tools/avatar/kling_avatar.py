"""Kling official API avatar image-to-video provider."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools._kling.account import account_usage_hint_for_error, get_account_costs
from tools._kling.callbacks import validate_callback_url
from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError
from tools._kling.media import (
    extension_from_url,
    normalize_image_input,
    normalize_media_input,
    numbered_output_path,
    output_path_with_suffix,
)
from tools._kling.schemas import AVATAR_MODES
from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.video._shared import probe_output


class KlingAvatar(BaseTool):
    name = "kling_avatar"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "kling_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KLING_API_KEY"]
    install_instructions = (
        "Set KLING_API_KEY in .env for the official Kling API. "
        "Provide an avatar image plus either audio_id or sound_file/audio_path."
    )
    agent_skills = ["kling-official", "avatar-video"]

    capabilities = ["photo_to_video", "avatar_video", "audio_driven_avatar"]
    supports = {
        "photo_to_video": True,
        "audio_driven_animation": True,
        "offline": False,
        "cloud_render": True,
    }
    best_for = [
        "official Kling cloud avatar presenter clips",
        "high-quality image-to-video avatar generation from a supplied portrait",
        "projects already using a Kling official account and resource pack",
    ]
    not_good_for = [
        "fully offline avatar generation",
        "free local drafts",
        "silently replacing the local talking_head provider",
    ]
    fallback_tools = ["talking_head", "lip_sync"]

    input_schema = {
        "type": "object",
        "anyOf": [
            {"required": ["image_url"]},
            {"required": ["image_path"]},
        ],
        "allOf": [
            {
                "anyOf": [
                    {"required": ["audio_id"]},
                    {"required": ["sound_file"]},
                    {"required": ["sound_file_url"]},
                    {"required": ["sound_file_path"]},
                    {"required": ["audio_path"]},
                ]
            }
        ],
        "properties": {
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "audio_id": {"type": "string"},
            "sound_file": {
                "type": "string",
                "description": "Official Kling sound_file value or raw base64 audio.",
            },
            "sound_file_url": {"type": "string"},
            "sound_file_path": {"type": "string"},
            "audio_path": {
                "type": "string",
                "description": "Alias for sound_file_path for compatibility with local avatar tools.",
            },
            "prompt": {"type": "string"},
            "mode": {"type": "string", "enum": AVATAR_MODES, "default": "std"},
            "callback_url": {"type": "string"},
            "external_task_id": {"type": "string"},
            "include_account_usage": {
                "type": "boolean",
                "default": False,
                "description": "Optional low-frequency account usage diagnostic; not used by default.",
            },
            "timeout_seconds": {"type": "integer", "default": 900},
            "poll_interval": {"type": "number", "default": 5.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["1302", "1303", "5000", "5001", "5002"],
    )
    idempotency_key_fields = [
        "image_url",
        "image_path",
        "audio_id",
        "sound_file",
        "sound_file_url",
        "sound_file_path",
        "audio_path",
        "prompt",
        "mode",
    ]
    side_effects = ["paid remote generation via official Kling API", "writes avatar video to output_path"]
    user_visible_verification = ["Watch generated avatar video for identity preservation and mouth motion"]
    quality_score = 0.82
    latency_p50_seconds = 240.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        base = 0.35
        if inputs.get("mode") == "pro":
            base *= 1.7
        if inputs.get("sound_file_path") or inputs.get("audio_path"):
            base += 0.04
        return round(base, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 240.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        result.update(
            {
                "paid_api": True,
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative OpenMontage avatar estimate pending official account-usage reconciliation.",
            }
        )
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            self.check_dependencies()
        except DependencyError as exc:
            return ToolResult(success=False, error=str(exc))

        start = time.time()
        try:
            request = self._build_request(inputs)
            client = KlingClient()
            task_id = client.create_classic_task(request["path"], request["payload"])
            outputs = client.poll_classic(
                request["path"],
                task_id,
                "videos",
                timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                poll_interval=float(inputs.get("poll_interval", 5.0)),
            )
            paths = self._download_videos(client, outputs, inputs)
            probed = probe_output(paths[0])
        except (KlingAPIError, TimeoutError, ValueError, KeyError, FileNotFoundError) as exc:
            data: dict[str, Any] = {"provider": self.provider}
            if isinstance(exc, KlingAPIError):
                data.update(
                    {
                        "error_code": exc.code,
                        "request_id": exc.request_id,
                        "http_status": exc.http_status,
                        "account_usage_diagnostic": account_usage_hint_for_error(exc),
                    }
                )
            return ToolResult(success=False, data=data, error=f"Kling official avatar generation failed: {exc}")
        except Exception as exc:
            return ToolResult(success=False, data={"provider": self.provider}, error=f"Kling official avatar generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "kling-official-avatar",
                "task_id": task_id,
                "operation": "image_to_avatar_video",
                "mode": request["payload"].get("mode"),
                "prompt": request["payload"].get("prompt"),
                "avatar_source": request["avatar_source"],
                "audio_source": request["audio_source"],
                "remote_outputs": outputs,
                "output": str(paths[0]),
                "output_path": str(paths[0]),
                "video_paths": [str(path) for path in paths],
                "format": "mp4",
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative estimate pending official account-usage reconciliation.",
                **self._account_usage_result(inputs, client),
                **self._callback_result_data(inputs, task_id),
                **probed,
            },
            artifacts=[str(path) for path in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="kling-official-avatar",
        )

    def _build_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        image = normalize_image_input(inputs.get("image_url"), inputs.get("image_path"))
        if not image:
            raise ValueError("Kling avatar requires image_url or image_path")

        mode = str(inputs.get("mode") or "std")
        if mode not in AVATAR_MODES:
            raise ValueError(f"mode must be one of: {', '.join(AVATAR_MODES)}")

        payload: dict[str, Any] = {
            "image": image,
            "mode": mode,
        }
        if inputs.get("prompt"):
            payload["prompt"] = str(inputs["prompt"])

        audio_source = self._copy_audio_input(inputs, payload)
        self._copy_common_task_fields(inputs, payload)
        return {
            "protocol": "classic",
            "path": "/v1/videos/avatar/image2video",
            "payload": payload,
            "operation": "image_to_avatar_video",
            "model": "kling-official-avatar",
            "avatar_source": inputs.get("image_url") or inputs.get("image_path"),
            "audio_source": audio_source,
        }

    @staticmethod
    def _copy_audio_input(inputs: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        audio_id = str(inputs.get("audio_id") or "").strip()
        if audio_id:
            payload["audio_id"] = audio_id
            return {"type": "audio_id", "value": audio_id}

        sound_path = inputs.get("sound_file_path") or inputs.get("audio_path")
        sound_file = normalize_media_input(
            url=inputs.get("sound_file_url"),
            path=sound_path,
            value=inputs.get("sound_file"),
            label="Avatar audio file",
        )
        if not sound_file:
            raise ValueError("Kling avatar requires audio_id, sound_file, sound_file_url, sound_file_path, or audio_path")
        payload["sound_file"] = sound_file
        return {
            "type": "sound_file",
            "source": inputs.get("sound_file_url") or sound_path or "inline",
        }

    def _download_videos(
        self,
        client: KlingClient,
        outputs: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> list[Path]:
        if not outputs:
            raise ValueError("Kling avatar response contained no videos")
        base_path = Path(inputs.get("output_path", "kling_avatar.mp4"))
        paths: list[Path] = []
        for index, item in enumerate(outputs):
            url = self._output_url(item)
            suffix = extension_from_url(url, ".mp4")
            output_path = numbered_output_path(output_path_with_suffix(base_path, suffix), index, suffix)
            client.download(url, output_path)
            paths.append(output_path)
        return paths

    @staticmethod
    def _output_url(item: dict[str, Any]) -> str:
        url = item.get("url") or item.get("video_url") or item.get("resource_url")
        if url:
            return str(url)
        resource = item.get("resource") or {}
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
        raise ValueError(f"Kling avatar response item contained no downloadable URL: {item}")

    @staticmethod
    def _copy_common_task_fields(inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            payload["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            payload["external_task_id"] = inputs["external_task_id"]

    @staticmethod
    def _callback_result_data(inputs: dict[str, Any], task_id: str) -> dict[str, Any]:
        callback_url = inputs.get("callback_url")
        if not callback_url:
            return {}
        return {
            "callback_url": str(callback_url),
            "callback_requested": True,
            "polling_used": True,
            "task_id": task_id,
        }

    @staticmethod
    def _account_usage_result(inputs: dict[str, Any], client: KlingClient) -> dict[str, Any]:
        if not inputs.get("include_account_usage"):
            return {}
        try:
            usage = get_account_costs(client=client)
            return {
                "account_usage": usage,
                "cost_source": "estimate_with_account_usage_context",
                "reconciled_cost_usd": None,
            }
        except Exception as exc:
            return {
                "account_usage_error": str(exc),
                "cost_source": "estimate",
                "reconciled_cost_usd": None,
            }
