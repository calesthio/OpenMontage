"""WaveSpeed text-to-image provider."""

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
from tools.wavespeed_generation import cli_main, run_wavespeed_generation


class WaveSpeedTextToImage(BaseTool):
    name = "wavespeed_text_to_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY for authentication and configure "
        "config.yaml wavespeed.profiles.<profile>.text_to_image.model_id."
    )
    agent_skills = ["wavespeed"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "text_to_image": True,
        "profile_based_model_selection": True,
        "model_id_override": True,
        "metadata_sidecar": True,
    }
    best_for = [
        "AI image generation through WaveSpeed with profile-based model selection",
        "text-to-image asset generation",
    ]
    not_good_for = ["stock image search", "direct non-WaveSpeed provider calls"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
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
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "aspect_ratio": {"type": "string"},
            "seed": {"type": "integer"},
            "negative_prompt": {"type": "string"},
        },
    }
    output_schema = {"$ref": "schemas/tools/wavespeed_generation.schema.json"}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "model_id", "params"]
    side_effects = ["writes image files", "writes metadata JSON", "calls WaveSpeed API"]
    user_visible_verification = ["Inspect generated image and metadata sidecar"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("WAVESPEED_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            resolve_wavespeed_task("text_to_image")
        except WaveSpeedConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

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
            task_type="text_to_image",
            asset_type="image",
            inputs=inputs,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        data = super().dry_run(inputs)
        data["would_submit_paid_task"] = True
        data["provider"] = "wavespeed"
        data["task_type"] = "text_to_image"
        return data


if __name__ == "__main__":
    raise SystemExit(
        cli_main(
            tool_name="wavespeed_text_to_image",
            task_type="text_to_image",
            asset_type="image",
        )
    )
