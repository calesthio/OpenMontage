"""WaveSpeed digital-human (avatar / talking-head) provider."""

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


class WaveSpeedDigitalHuman(BaseTool):
    name = "wavespeed_digital_human"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY for authentication and configure "
        "config.yaml wavespeed.profiles.<profile>.digital_human.model_id."
    )
    agent_skills = ["wavespeed"]

    capabilities = ["digital_human", "avatar", "talking_head"]
    supports = {
        "digital_human": True,
        "profile_based_model_selection": True,
        "model_id_override": True,
        "metadata_sidecar": True,
    }
    best_for = [
        "AI avatar / talking-head video generation through WaveSpeed",
        "digital human asset generation with profile-based model selection",
    ]
    not_good_for = ["direct non-WaveSpeed provider calls", "footage-led speaker videos"]

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
        },
    }
    output_schema = {"$ref": "schemas/tools/wavespeed_generation.schema.json"}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "model_id", "params"]
    side_effects = ["writes video files", "writes metadata JSON", "calls WaveSpeed API"]
    user_visible_verification = ["Inspect generated avatar video and metadata sidecar"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("WAVESPEED_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            resolve_wavespeed_task("digital_human")
        except WaveSpeedConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        inputs = dict(inputs)

        # Selector/candidate mode may set _wavespeed_profile / _wavespeed_model_id.
        if hasattr(self, "_wavespeed_profile"):
            inputs["_wavespeed_profile"] = self._wavespeed_profile
        if hasattr(self, "_wavespeed_model_id") and "model_id" not in inputs:
            inputs["model_id"] = self._wavespeed_model_id

        return run_wavespeed_generation(
            task_type="digital_human",
            asset_type="video",
            inputs=inputs,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        data = super().dry_run(inputs)
        data["would_submit_paid_task"] = True
        data["provider"] = "wavespeed"
        data["task_type"] = "digital_human"
        return data
