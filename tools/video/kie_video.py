"""KIE AI video generation gateway.

KIE AI (https://kie.ai) is a multi-model aggregator: one API key and one
unified async task contract in front of dozens of video models (Veo, Kling,
Runway, Seedance, ...). This tool defaults to Veo 3.1 -- the best-documented,
flagship text/image-to-video model on the platform -- and exposes a generic
`extra_input` passthrough plus `kie_model` override so any other Market video
model can be called without a code change. Check https://kie.ai/market for
the exact `input` fields of a given model before switching `kie_model`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import kie_client
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
from tools.provider_pricing import PriceQuoteRequired

_DEFAULT_MODEL = "veo-3-1"


class KieVideo(BaseTool):
    name = "kie_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kie"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KIE_API_KEY"]
    install_instructions = kie_client.INSTALL_INSTRUCTIONS
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "first_last_frame": True,
        "native_audio": True,
        "resolutions": ["720p", "1080p", "4k"],
        "aspect_ratios": ["16:9", "9:16", "Auto"],
        "multi_model_gateway": True,
    }
    best_for = [
        "Veo 3.1 text/image-to-video with native audio through a single KIE AI key",
        "Trying other KIE Market video models (Kling, Runway, Seedance) via kie_model + extra_input",
    ]
    not_good_for = ["offline generation", "guaranteed pricing without checking kie.ai/pricing"]
    fallback_tools = ["veo_video", "kling_video", "seedance_video"]
    quality_score = 0.85

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "kie_model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "KIE AI Market model id for createTask's top-level 'model' field.",
            },
            "veo_tier": {
                "type": "string",
                "enum": ["veo3_fast", "veo3_lite", "veo3"],
                "default": "veo3_fast",
                "description": "Only used when kie_model == 'veo-3-1'. Maps to Veo 3.1's input.model tier.",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "image_url": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "Auto"], "default": "16:9"},
            "resolution": {"type": "string", "enum": ["720p", "1080p", "4k"], "default": "720p"},
            "duration": {"type": "integer", "enum": [4, 6, 8], "default": 8},
            "watermark": {"type": "string"},
            "enable_translation": {"type": "boolean"},
            "extra_input": {
                "type": "object",
                "description": "Raw fields merged into the Market 'input' object -- use for non-default kie_model schemas.",
            },
            "callback_url": {"type": "string"},
            "poll_interval": {"type": "number", "default": 5.0},
            "poll_timeout": {"type": "number", "default": 900.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=800, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "kie_model", "operation", "aspect_ratio", "resolution", "duration"]
    side_effects = ["writes video file to output_path", "calls KIE AI API"]
    user_visible_verification = ["Watch the result for motion fidelity and native audio"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "KIE AI video pricing varies by model/resolution/duration -- see https://kie.ai/pricing"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

    def _build_veo_input(self, inputs: dict[str, Any], api_key: str) -> dict[str, Any]:
        operation = str(inputs.get("operation", "text_to_video"))
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "model": inputs.get("veo_tier", "veo3_fast"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "resolution": inputs.get("resolution", "720p"),
            "duration": int(inputs.get("duration", 8)),
        }
        mode_map = {
            "text_to_video": "TEXT_2_VIDEO",
            "image_to_video": "FIRST_AND_LAST_FRAMES_2_VIDEO",
            "reference_to_video": "REFERENCE_2_VIDEO",
        }
        payload["generation_type"] = mode_map[operation]

        images = [str(value) for value in (inputs.get("image_urls") or [])]
        if inputs.get("image_url"):
            images.insert(0, str(inputs["image_url"]))
        if operation != "text_to_video":
            if not images:
                raise ValueError(f"{operation} requires image_url or image_urls")
            payload["image_urls"] = [kie_client.resolve_media(value, api_key) for value in images]

        if inputs.get("watermark"):
            payload["watermark"] = inputs["watermark"]
        if inputs.get("enable_translation") is not None:
            payload["enable_translation"] = bool(inputs["enable_translation"])
        return payload

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = kie_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="KIE_API_KEY not set. " + self.install_instructions)

        kie_model = str(inputs.get("kie_model", _DEFAULT_MODEL))
        started = time.time()
        try:
            if kie_model == _DEFAULT_MODEL:
                market_input = self._build_veo_input(inputs, api_key)
            else:
                market_input = {"prompt": inputs.get("prompt", "")}
            extra = inputs.get("extra_input")
            if isinstance(extra, dict):
                market_input.update(extra)

            task_id = kie_client.create_task(
                kie_model, market_input, api_key, callback_url=inputs.get("callback_url")
            )
            urls = kie_client.poll_task(
                task_id,
                api_key,
                interval=float(inputs.get("poll_interval", 5.0)),
                timeout=float(inputs.get("poll_timeout", 900.0)),
            )
            output_path = Path(inputs.get("output_path") or "kie_video_output.mp4")
            kie_client.download(urls[0], output_path)
        except (kie_client.KieError, ValueError, KeyError) as exc:
            return ToolResult(success=False, error=f"KIE AI video generation failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"KIE AI video generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "kie",
                "model": kie_model,
                "prompt": inputs.get("prompt", ""),
                "operation": inputs.get("operation", "text_to_video"),
                "output": str(output_path),
                "output_path": str(output_path),
                "task_id": task_id,
                "source_url": urls[0],
                "source_urls": urls,
                "request_params": market_input,
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - started, 2),
            model=kie_model,
        )
