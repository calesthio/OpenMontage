"""WaveSpeed text-to-music provider."""

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
    run_wavespeed_generation,
    wavespeed_estimate_cost,
)


class WaveSpeedTextToMusic(BaseTool):
    name = "wavespeed_text_to_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY for authentication and configure "
        "config.yaml wavespeed.profiles.<profile>.text_to_music.model_id."
    )
    agent_skills = ["wavespeed"]

    capabilities = ["text_to_music", "music_generation"]
    supports = {
        "text_to_music": True,
        "profile_based_model_selection": True,
        "model_id_override": True,
        "metadata_sidecar": True,
    }
    best_for = [
        "AI music/background-track generation through WaveSpeed",
        "prompt-driven instrumental or scored music",
    ]
    not_good_for = ["speech/voiceover (use wavespeed_text_to_audio)"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Music description / style prompt."},
            "output_dir": {"type": "string"},
            "output_path": {"type": "string"},
            "model_id": {
                "type": "string",
                "description": "Optional one-task override. Defaults to active WaveSpeed profile.",
            },
            "params": {
                "type": ["object", "string"],
                "description": "JSON params merged over active profile defaults (e.g. duration, lyrics).",
            },
        },
    }
    output_schema = {"$ref": "schemas/tools/wavespeed_generation.schema.json"}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "model_id", "params"]
    side_effects = ["writes audio files", "writes metadata JSON", "calls WaveSpeed API"]
    user_visible_verification = ["Listen to generated music and inspect metadata sidecar"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("WAVESPEED_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            # Honor a selector-assigned profile/model (active_profile=null mode)
            # so multi-profile candidates report AVAILABLE the same way execute()
            # runs them, instead of UNAVAILABLE from the null-profile lookup.
            resolve_wavespeed_task(
                "text_to_music",
                explicit_profile=getattr(self, "_wavespeed_profile", None),
                explicit_model_id=getattr(self, "_wavespeed_model_id", None),
            )
        except WaveSpeedConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return wavespeed_estimate_cost("text_to_music", inputs)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        inputs = dict(inputs)
        if hasattr(self, "_wavespeed_profile"):
            inputs["_wavespeed_profile"] = self._wavespeed_profile
        if hasattr(self, "_wavespeed_model_id") and "model_id" not in inputs:
            inputs["model_id"] = self._wavespeed_model_id

        return run_wavespeed_generation(
            task_type="text_to_music",
            asset_type="audio",
            inputs=inputs,
        )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        data = super().dry_run(inputs)
        data["would_submit_paid_task"] = True
        data["provider"] = "wavespeed"
        data["task_type"] = "text_to_music"
        return data
