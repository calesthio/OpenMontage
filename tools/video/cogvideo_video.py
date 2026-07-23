"""CogVideo local video generation."""

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
from tools.video._shared import COGVIDEO_VARIANTS, estimate_local_runtime, generate_local_video, local_generation_status, local_install_instructions


class CogVideoVideo(BaseTool):
    name = "cogvideo_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "cogvideo"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = local_install_instructions()
    fallback = "wan_video"
    fallback_tools = ["wan_video", "hunyuan_video", "ltx_video_local", "image_selector"]
    agent_skills = ["ltx2"]

    capabilities = ["text_to_video", "image_to_video", "model_selection"]
    supports = {
        "reference_image": True,
        "offline": True,
        "native_audio": False,
        "local_gpu": True,
    }
    best_for = [
        "lower-VRAM local video experimentation",
        "teams that want an explicit CogVideo family path in the registry",
    ]
    not_good_for = ["best-in-class local quality targets"]
    provider_matrix = {key: {"tool": "cogvideo_video", **value, "mode": "local_gpu"} for key, value in COGVIDEO_VARIANTS.items()}

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {"type": "string", "enum": ["text_to_video", "image_to_video"], "default": "text_to_video"},
            "model_variant": {"type": "string", "enum": sorted(COGVIDEO_VARIANTS), "default": "cogvideo-5b"},
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

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=16000, vram_mb=6000, disk_mb=4000, network_required=False)
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "model_variant", "operation", "seed"]
    side_effects = ["writes video file to output_path", "may download model weights"]
    user_visible_verification = ["Watch generated clip for motion coherence and artifacts"]

    def get_status(self) -> ToolStatus:
        return local_generation_status()

    DEFAULT_VARIANT = "cogvideo-5b"

    def _variant_for(self, inputs: dict[str, object]) -> dict[str, object]:
        """Resolve the active variant dict, falling back to the default."""
        return COGVIDEO_VARIANTS.get(
            inputs.get("model_variant", self.DEFAULT_VARIANT),
            COGVIDEO_VARIANTS[self.DEFAULT_VARIANT],
        )

    def is_operation_available(self, operation: str) -> bool:
        """Capability is variant-driven, not unconditional.

        cogvideo_video advertised image_to_video unconditionally, but the 2B
        variant declares i2v=False (it is t2v-only). The selector calls this
        without inputs, so we report capability for the DEFAULT variant
        (cogvideo-5b: t2v=True, i2v=True) — execute() re-checks against the
        caller's chosen variant and fails fast if it lacks the requested mode.
        """
        variant = COGVIDEO_VARIANTS[self.DEFAULT_VARIANT]
        if operation == "image_to_video":
            return bool(variant.get("i2v"))
        if operation == "text_to_video":
            return bool(variant.get("t2v"))
        return True

    def estimate_cost(self, inputs: dict[str, object]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, object]) -> float:
        variant = COGVIDEO_VARIANTS.get(inputs.get("model_variant", "cogvideo-5b"), COGVIDEO_VARIANTS["cogvideo-5b"])
        return estimate_local_runtime(variant["speed"])

    def execute(self, inputs: dict[str, object]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="CogVideo local generation is unavailable. " + self.install_instructions)

        # Consult the variant flag the selector cannot see: the 2B variant is
        # t2v-only (i2v=False), so an image_to_video brief against it would
        # otherwise reach the diffusion pipeline and fail opaquely.
        operation = inputs.get("operation", "text_to_video")
        variant = self._variant_for(inputs)
        if operation == "image_to_video" and not variant.get("i2v"):
            chosen = inputs.get("model_variant", self.DEFAULT_VARIANT)
            return ToolResult(
                success=False,
                error=(
                    f"CogVideo variant '{chosen}' does not support image_to_video "
                    f"(i2v=False). Use the cogvideo-5b variant or a text_to_video operation."
                ),
            )

        start = time.time()
        try:
            result = generate_local_video(tool_name=self.name, variants=COGVIDEO_VARIANTS, default_variant="cogvideo-5b", inputs=inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"CogVideo generation failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

