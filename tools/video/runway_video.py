"""Runway and third-party video generation through the Runway API.

Supports Runway-native models plus the current Seedance, Gemini Omni Flash,
and MiniMax Hailuo 3 partner models exposed by Runway's API.
"""

from __future__ import annotations

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

_LEGACY_RATIO_MAP = {
    "16:9": "1280:720",
    "9:16": "720:1280",
    "1:1": "720:720",
}

_SEEDANCE_25_RATIOS = {
    "480p": {
        "21:9": "992:432",
        "16:9": "854:480",
        "4:3": "752:560",
        "1:1": "640:640",
        "3:4": "560:752",
        "9:16": "480:854",
    },
    "720p": {
        "21:9": "1470:630",
        "16:9": "1280:720",
        "4:3": "1112:834",
        "1:1": "960:960",
        "3:4": "834:1112",
        "9:16": "720:1280",
    },
}

_COST_PER_SECOND = {
    "gen4_turbo": 0.05,
    "gen4.5": 0.12,
    "seedance2": 0.36,
    "seedance2_fast": 0.29,
    "seedance2_mini": 0.16,
    "seedance2_5": 0.30,
    "gemini_omni_flash": 0.10,
    "hailuo3": 0.15,
}

_RUNTIME_SECONDS = {
    "gen4_turbo": 30.0,
    "gen4.5": 60.0,
    "seedance2": 120.0,
    "seedance2_fast": 60.0,
    "seedance2_mini": 60.0,
    "seedance2_5": 150.0,
    "gemini_omni_flash": 90.0,
    "hailuo3": 120.0,
}

# Single source of truth for the default model. Referenced by both the input
# schema and every code path that reads `model`, so estimate_cost / estimate_runtime
# / execute can never silently diverge from the advertised default again.
_DEFAULT_MODEL = "seedance2"


class RunwayVideo(BaseTool):
    name = "runway_video"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "runway"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set RUNWAY_API_KEY to your Runway API secret.\n"
        "  Get one at https://dev.runwayml.com/"
    )
    agent_skills = [
        "seedance-2-0",
        "seedance-2-5",
        "gemini-omni",
        "minimax-h3",
        "ai-video-gen",
    ]

    capabilities = ["text_to_video", "image_to_video", "video_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "video_to_video": True,
        "reference_image": True,
        "reference_video": True,
        "reference_audio": True,
        "professional_control": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "lip_sync": True,
        "multi_shot": True,
    }
    best_for = [
        "Seedance 2.5 clips up to 30 seconds with large multimodal reference sets",
        "Gemini Omni Flash generation and video editing",
        "MiniMax H3 / Hailuo 3.0 generation through Runway",
        "professional video production",
    ]
    not_good_for = ["budget projects", "offline generation", "very long clips"]
    fallback_tools = [
        "seedance_video",
        "seedance_replicate",
        "kling_video",
        "veo_video",
        "minimax_video",
        "wan_video",
    ]
    quality_score = 0.9

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "video_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": [
                    "seedance2_5",
                    "gemini_omni_flash",
                    "hailuo3",
                    "seedance2",
                    "seedance2_fast",
                    "seedance2_mini",
                    "gen4.5",
                    "gen4_turbo",
                ],
                "default": _DEFAULT_MODEL,
                "description": (
                    "Current Runway model identifiers. seedance2_5 supports 4-30s "
                    "and large reference sets; gemini_omni_flash supports 3-10s "
                    "generation/editing; hailuo3 is MiniMax H3 with 5-15s output."
                ),
            },
            "duration": {
                "type": "integer",
                "minimum": 2,
                "maximum": 30,
                "default": 5,
                "description": "Duration in seconds",
            },
            "ratio": {
                "type": "string",
                "enum": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "default": "16:9",
            },
            "image_url": {
                "type": "string",
                "description": "First-frame image URL for image_to_video",
            },
            "video_url": {
                "type": "string",
                "description": "Source video URL for video_to_video",
            },
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_video_urls": {"type": "array", "items": {"type": "string"}},
            "reference_audio_urls": {"type": "array", "items": {"type": "string"}},
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "768P", "2K"],
                "description": "Seedance 2.5: 480p/720p; Hailuo 3: 768P/2K.",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "mode": {
                "type": "string",
                "enum": ["reference", "extend"],
                "default": "reference",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout", "THROTTLED"]
    )
    idempotency_key_fields = ["prompt", "model", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls Runway API"]
    user_visible_verification = [
        "Watch generated clip for visual quality and motion coherence"
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("RUNWAY_API_KEY") or os.environ.get("RUNWAYML_API_SECRET"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _get_api_key(self) -> str | None:
        return os.environ.get("RUNWAY_API_KEY") or os.environ.get("RUNWAYML_API_SECRET")

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", _DEFAULT_MODEL)
        duration = inputs.get("duration", 5)
        rate = _COST_PER_SECOND.get(model, 0.05)
        if model == "gemini_omni_flash" and inputs.get("operation") == "video_to_video":
            rate = 0.11
        if model == "seedance2_5" and inputs.get("resolution", "720p") == "480p":
            rate = 0.20
        if model == "hailuo3" and inputs.get("resolution", "2K") == "768P":
            rate = 0.10
        return rate * duration

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", _DEFAULT_MODEL)
        return _RUNTIME_SECONDS.get(model, 30.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="RUNWAY_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model = inputs.get("model", _DEFAULT_MODEL)
        operation = inputs.get("operation", "text_to_video")
        ratio_friendly = inputs.get("ratio", "16:9")
        duration = inputs.get("duration", 5)
        prompt = inputs.get("prompt", "")
        image_refs = list(inputs.get("reference_image_urls") or [])
        video_refs = list(inputs.get("reference_video_urls") or [])
        audio_refs = list(inputs.get("reference_audio_urls") or [])

        task_payload: dict[str, Any] = {"model": model, "duration": duration}
        if prompt:
            task_payload["promptText"] = prompt

        seedance_models = {
            "seedance2",
            "seedance2_fast",
            "seedance2_mini",
            "seedance2_5",
        }
        if model == "seedance2_5":
            resolution = inputs.get("resolution", "720p")
            if resolution not in _SEEDANCE_25_RATIOS:
                return ToolResult(
                    success=False, error="seedance2_5 resolution must be 480p or 720p"
                )
            if ratio_friendly not in _SEEDANCE_25_RATIOS[resolution]:
                return ToolResult(
                    success=False,
                    error=f"unsupported Seedance 2.5 ratio: {ratio_friendly}",
                )
            task_payload["ratio"] = _SEEDANCE_25_RATIOS[resolution][ratio_friendly]
        elif model == "hailuo3":
            task_payload["ratio"] = ratio_friendly
            task_payload["resolution"] = inputs.get("resolution", "2K")
        elif model == "gemini_omni_flash":
            if ratio_friendly not in {"16:9", "9:16"}:
                return ToolResult(
                    success=False,
                    error="gemini_omni_flash supports only 16:9 or 9:16",
                )
            task_payload["ratio"] = _LEGACY_RATIO_MAP[ratio_friendly]
        else:
            task_payload["ratio"] = _LEGACY_RATIO_MAP.get(ratio_friendly, "1280:720")

        if model == "gemini_omni_flash" and not 3 <= task_payload["duration"] <= 10:
            return ToolResult(
                success=False, error="gemini_omni_flash duration must be 3-10 seconds"
            )
        if model == "seedance2_5" and not 4 <= task_payload["duration"] <= 30:
            return ToolResult(
                success=False, error="seedance2_5 duration must be 4-30 seconds"
            )
        if model == "hailuo3" and not 5 <= task_payload["duration"] <= 15:
            return ToolResult(
                success=False, error="hailuo3 duration must be 5-15 seconds"
            )

        if model in seedance_models or model == "hailuo3":
            if model in seedance_models and "generate_audio" in inputs:
                task_payload["audio"] = inputs["generate_audio"]
            if operation != "image_to_video":
                if image_refs:
                    task_payload["references"] = [{"uri": url} for url in image_refs]
                if video_refs:
                    task_payload["referenceVideos"] = [
                        {"type": "video", "uri": url} for url in video_refs
                    ]
            elif image_refs or video_refs:
                return ToolResult(
                    success=False,
                    error=(
                        f"{model} image_to_video accepts a first frame and optional "
                        "audio references, not additional image/video references"
                    ),
                )
            if audio_refs:
                task_payload["referenceAudio"] = [
                    {"type": "audio", "uri": url} for url in audio_refs
                ]
        elif model == "gemini_omni_flash" and operation != "video_to_video":
            if image_refs or video_refs or audio_refs:
                return ToolResult(
                    success=False,
                    error=(
                        "gemini_omni_flash text/image generation through Runway does "
                        "not accept extra references"
                    ),
                )

        if (
            model in {"gemini_omni_flash", "hailuo3"}
            and inputs.get("generate_audio") is False
        ):
            return ToolResult(
                success=False,
                error=f"Runway's {model} schema does not expose an audio-disable parameter",
            )

        if operation == "image_to_video":
            if not inputs.get("image_url"):
                return ToolResult(
                    success=False, error="image_to_video requires image_url"
                )
            task_payload["promptImage"] = inputs["image_url"]
        if operation == "video_to_video":
            if not inputs.get("video_url"):
                return ToolResult(
                    success=False, error="video_to_video requires video_url"
                )
            source_field = "videoUri" if model == "gemini_omni_flash" else "promptVideo"
            task_payload[source_field] = inputs["video_url"]
            if model == "gemini_omni_flash":
                task_payload.pop("duration", None)
                task_payload.pop("ratio", None)
                if video_refs or audio_refs:
                    return ToolResult(
                        success=False,
                        error="gemini_omni_flash video editing accepts image references only",
                    )
                if image_refs:
                    task_payload["references"] = [{"uri": url} for url in image_refs]
            if model == "seedance2_5":
                task_payload["mode"] = inputs.get("mode", "reference")
                if task_payload["mode"] == "extend":
                    task_payload.pop("ratio", None)

        if operation == "text_to_video" and model == "seedance2_5":
            if not prompt and not (image_refs or video_refs or audio_refs):
                return ToolResult(
                    success=False,
                    error="seedance2_5 text_to_video requires prompt or references",
                )
        elif not prompt and model != "gen4_turbo":
            return ToolResult(success=False, error=f"{model} requires prompt")

        if model == "gen4_turbo" and operation != "image_to_video":
            return ToolResult(
                success=False, error="gen4_turbo supports image_to_video only"
            )
        if model in {"gen4.5", "gen4_turbo"} and operation == "video_to_video":
            return ToolResult(
                success=False, error=f"{model} does not support video_to_video"
            )

        # Choose endpoint based on operation
        endpoint = f"https://api.dev.runwayml.com/v1/{operation}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

        try:
            # Submit generation task
            submit_response = requests.post(
                endpoint,
                headers=headers,
                json=task_payload,
                timeout=30,
            )
            submit_response.raise_for_status()
            task_id = submit_response.json()["id"]

            # Poll for completion (max ~5 minutes)
            video_url = None
            for _ in range(60):
                time.sleep(5)
                poll_response = requests.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers,
                    timeout=15,
                )
                poll_response.raise_for_status()
                task_data = poll_response.json()
                status = task_data["status"]

                if status == "SUCCEEDED":
                    video_url = task_data["output"][0]
                    break
                if status == "FAILED":
                    failure_code = task_data.get("failureCode", "unknown")
                    return ToolResult(
                        success=False,
                        error=f"Runway generation failed ({failure_code}): {task_data.get('failure', 'unknown error')}",
                    )
                # PENDING, THROTTLED, RUNNING — keep polling

            if not video_url:
                return ToolResult(
                    success=False, error="Runway generation timed out after 5 minutes."
                )

            # Download video — URLs are ephemeral (expire in 24-48h)
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "runway_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(
                success=False, error=f"Runway video generation failed: {e}"
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "runway",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": operation,
                "ratio": ratio_friendly,
                "output": str(output_path),
                "output_path": str(output_path),
                "task_id": task_id,
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
