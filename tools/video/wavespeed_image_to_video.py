"""WaveSpeed image-to-video provider."""

from __future__ import annotations

import os
from typing import Any

from lib.wavespeed_config import resolve_wavespeed_task, WaveSpeedConfigError
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
from tools.wavespeed_generation import (
    cli_main,
    run_wavespeed_generation,
    wavespeed_estimate_cost,
)


class WaveSpeedImageToVideo(BaseTool):
    name = "wavespeed_image_to_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY for authentication and configure "
        "config.yaml wavespeed.profiles.<profile>.image_to_video.model_id."
    )
    agent_skills = ["wavespeed"]

    capabilities = ["generate_video", "image_to_video"]
    supports = {
        "text_to_video": False,
        "image_to_video": True,
        "reference_image": True,
        "profile_based_model_selection": True,
        "model_id_override": True,
        "metadata_sidecar": True,
    }
    best_for = [
        "AI image-to-video generation with profile-based model selection",
        "turning approved still frames into motion while preserving provenance",
    ]
    not_good_for = ["stock footage search", "direct non-WaveSpeed provider calls"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["image_to_video"],
                "default": "image_to_video",
            },
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "output_path": {"type": "string"},
            "model_id": {
                "type": "string",
                "description": "Optional one-task override. Defaults to active WaveSpeed profile.",
            },
            "params": {
                "type": ["object", "string"],
                "description": "JSON params merged over active profile defaults.",
            },
            "duration": {"type": ["string", "integer", "number"]},
            "aspect_ratio": {"type": "string"},
            "resolution": {"type": "string"},
            "seed": {"type": "integer"},
        },
    }
    output_schema = {"$ref": "schemas/tools/wavespeed_generation.schema.json"}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "prompt",
        "model_id",
        "params",
        "image_url",
        "reference_image_url",
    ]
    side_effects = ["writes video files", "writes metadata JSON", "calls WaveSpeed API"]
    user_visible_verification = ["Watch generated clip and inspect metadata sidecar"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("WAVESPEED_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            # Honor a selector-assigned profile/model (active_profile=null mode)
            # so multi-profile candidates report AVAILABLE the same way execute()
            # runs them, instead of UNAVAILABLE from the null-profile lookup.
            resolve_wavespeed_task(
                "image_to_video",
                explicit_profile=getattr(self, "_wavespeed_profile", None),
                explicit_model_id=getattr(self, "_wavespeed_model_id", None),
            )
        except WaveSpeedConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return wavespeed_estimate_cost("image_to_video", inputs)

    def is_operation_available(self, operation: str) -> bool:
        return operation == "image_to_video"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # Selector may have set _wavespeed_profile and _wavespeed_model_id
        # for multi-profile candidate mode (active_profile=null).
        # Pass these to run_wavespeed_generation if present.
        if hasattr(self, "_wavespeed_profile") or hasattr(self, "_wavespeed_model_id"):
            inputs = dict(inputs)  # shallow copy
            if hasattr(self, "_wavespeed_profile"):
                inputs["_wavespeed_profile"] = self._wavespeed_profile
            if hasattr(self, "_wavespeed_model_id") and "model_id" not in inputs:
                inputs["model_id"] = self._wavespeed_model_id

        return run_wavespeed_generation(
            task_type="image_to_video",
            asset_type="video",
            inputs=inputs,
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(os.environ.get("WAVESPEED_MAX_WAIT_SECONDS", 900))

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        data = super().dry_run(inputs)
        data["would_submit_paid_task"] = True
        data["provider"] = "wavespeed"
        data["task_type"] = "image_to_video"
        return data


if __name__ == "__main__":
    raise SystemExit(
        cli_main(
            tool_name="wavespeed_image_to_video",
            task_type="image_to_video",
            asset_type="video",
        )
    )
