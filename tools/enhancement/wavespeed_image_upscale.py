"""WaveSpeed image-upscale (super-resolution) provider."""

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
from tools.wavespeed_generation import run_wavespeed_generation


class WaveSpeedImageUpscale(BaseTool):
    name = "wavespeed_image_upscale"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY for authentication and configure "
        "config.yaml wavespeed.profiles.<profile>.image_upscale.model_id."
    )
    agent_skills = ["wavespeed"]

    capabilities = ["image_upscale", "super_resolution"]
    supports = {
        "image_upscale": True,
        "profile_based_model_selection": True,
        "model_id_override": True,
        "metadata_sidecar": True,
    }
    best_for = [
        "AI image upscaling / super-resolution through WaveSpeed",
        "boosting resolution of an existing image",
    ]
    not_good_for = ["generating new images from text"]

    input_schema = {
        "type": "object",
        "required": [],
        "properties": {
            # Upscaling operates on a source image; no text prompt required.
            "image_url": {"type": "string", "description": "Source image URL."},
            "image_path": {"type": "string", "description": "Local source image path."},
            "prompt": {"type": "string", "description": "Optional guidance; usually omitted."},
            "output_dir": {"type": "string"},
            "output_path": {"type": "string"},
            "model_id": {
                "type": "string",
                "description": "Optional one-task override. Defaults to active WaveSpeed profile.",
            },
            "params": {
                "type": ["object", "string"],
                "description": "JSON params merged over active profile defaults (e.g. upscale factor).",
            },
        },
    }
    output_schema = {"$ref": "schemas/tools/wavespeed_generation.schema.json"}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=300, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["image_url", "image_path", "model_id", "params"]
    side_effects = ["writes image files", "writes metadata JSON", "calls WaveSpeed API"]
    user_visible_verification = ["Inspect upscaled image and metadata sidecar"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("WAVESPEED_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            resolve_wavespeed_task("image_upscale")
        except WaveSpeedConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        inputs = dict(inputs)
        if hasattr(self, "_wavespeed_profile"):
            inputs["_wavespeed_profile"] = self._wavespeed_profile
        if hasattr(self, "_wavespeed_model_id") and "model_id" not in inputs:
            inputs["model_id"] = self._wavespeed_model_id

        return run_wavespeed_generation(
            task_type="image_upscale",
            asset_type="image",
            inputs=inputs,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        data = super().dry_run(inputs)
        data["would_submit_paid_task"] = True
        data["provider"] = "wavespeed"
        data["task_type"] = "image_upscale"
        return data
