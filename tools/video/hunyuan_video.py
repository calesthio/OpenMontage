"""Hunyuan local video generation."""

from __future__ import annotations

import time

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
from tools.video._shared import HUNYUAN_VARIANTS, estimate_local_runtime, generate_local_video, local_generation_status, local_install_instructions


class HunyuanVideo(BaseTool):
    name = "hunyuan_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "hunyuan"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = local_install_instructions()
    fallback = "wan_video"
    fallback_tools = ["wan_video", "ltx_video_local", "cogvideo_video", "image_selector"]
    agent_skills = ["ltx2"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "reference_image": True,
        "offline": True,
        "native_audio": False,
        "local_gpu": True,
    }
    best_for = [
        "local generation when Hunyuan motion behavior fits the brief",
        "teams that want one known Hunyuan baseline instead of multiple variants",
    ]
    not_good_for = ["CPU-only machines"]
    provider_matrix = {key: {"tool": "hunyuan_video", **value, "mode": "local_gpu"} for key, value in HUNYUAN_VARIANTS.items()}

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {"type": "string", "enum": ["text_to_video", "image_to_video"], "default": "text_to_video"},
            "model_variant": {"type": "string", "enum": ["hunyuan-1.5", "hunyuan-1.5-distilled"], "default": "hunyuan-1.5"},
            "offload_mode": {"type": "string", "enum": ["model", "sequential"], "default": "model"},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "num_frames": {"type": "integer"},
            "num_inference_steps": {"type": "integer"},
            "enable_model_offload": {"type": "boolean", "default": True},
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=16000, vram_mb=14000, disk_mb=4000, network_required=False)
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "model_variant", "operation", "seed"]
    side_effects = ["writes video file to output_path", "may download model weights"]
    user_visible_verification = ["Watch generated clip for motion coherence and artifacts"]

    def get_status(self) -> ToolStatus:
        return local_generation_status()

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return estimate_local_runtime(HUNYUAN_VARIANTS["hunyuan-1.5"]["speed"])

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Hunyuan local video generation is unavailable. " + self.install_instructions)
        start = time.time()
        try:
            result = generate_local_video(tool_name=self.name, variants=HUNYUAN_VARIANTS, default_variant="hunyuan-1.5", inputs=inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Hunyuan video generation failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result
