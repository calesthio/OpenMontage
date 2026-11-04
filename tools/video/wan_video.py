"""Wan local video generation.

Wraps the Wan 2.x family running on the machine's own GPU: text-to-video,
image-to-video, video-to-video, first/last-frame interpolation, and single-frame
text-to-image.  Clips longer than a model's native ~5s pass are produced by
chaining image-to-video segments — see ``tools/video/_wan_engine.py``.
"""

from __future__ import annotations

import time
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
from tools.video._shared import WAN_VARIANTS, local_generation_status, local_install_instructions
from tools.video._wan_engine import (
    DEFAULT_NEGATIVE_PROMPT,
    generate_wan,
    plan_segments,
    snap_frames,
)

DEFAULT_VARIANT = "wan2.2-ti2v-5b"

# Runtime model fitted to measurements on an Ada-class laptop GPU (11.6GB) with
# the 5B TI2V checkpoint in bf16 at 704x480:
#
#   49 frames, 20 steps -> 11.9 s/step      121 frames, 20 steps -> 23.3 s/step
#
# which separates into a per-step cost that does not depend on the clip (under
# sequential offload every step streams the whole transformer across PCIe) and a
# per-step cost proportional to the number of pixels being denoised.
_SEQUENTIAL_STREAM_SECONDS_PER_STEP = 4.1
_SECONDS_PER_STEP_PER_MPX_FRAME = 0.47
_MODEL_LOAD_SECONDS = 15.0


class WanVideo(BaseTool):
    name = "wan_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "wan"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = local_install_instructions()
    fallback = "hunyuan_video"
    fallback_tools = ["hunyuan_video", "ltx_video_local", "cogvideo_video", "image_selector"]
    agent_skills = ["ltx2"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "video_to_video",
        "first_last_frame",
        "text_to_image",
        "long_form_chaining",
        "model_selection",
    ]
    supports = {
        "reference_image": True,
        "offline": True,
        "native_audio": False,
        "local_gpu": True,
        "long_form": True,
    }
    best_for = [
        "best quality-to-VRAM ratio for local generation",
        "long local clips (20s+) assembled by image-to-video chaining",
        "local pipelines that need image-to-video and video-to-video",
    ]
    not_good_for = [
        "CPU-only machines",
        "instant iteration on low-end hardware",
        "single-pass shots longer than ~5s (Wan's trained clip length)",
    ]
    provider_matrix = {key: {"tool": "wan_video", **value, "mode": "local_gpu"} for key, value in WAN_VARIANTS.items()}

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": DEFAULT_NEGATIVE_PROMPT},
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "video_to_video",
                    "first_last_frame",
                    "text_to_image",
                ],
                "default": "text_to_video",
            },
            "model_variant": {"type": "string", "enum": sorted(WAN_VARIANTS), "default": DEFAULT_VARIANT},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "last_image_url": {"type": "string", "description": "Target final frame for first_last_frame"},
            "last_image_path": {"type": "string", "description": "Target final frame for first_last_frame"},
            "source_video_path": {"type": "string", "description": "Input clip for video_to_video"},
            "strength": {"type": "number", "default": 0.8, "description": "video_to_video denoise strength"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "fps": {"type": "integer"},
            "duration_seconds": {
                "type": "number",
                "description": "Target length. Beyond one segment the clip is chained image-to-video.",
            },
            "num_frames": {"type": "integer", "description": "Exact frame count; overrides duration_seconds"},
            "segment_frames": {
                "type": "integer",
                "description": "Frames per chained segment. Defaults to the model's native clip length.",
            },
            "segment_prompts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Per-segment prompts for long clips — a shot list. Falls back to prompt.",
            },
            "correct_drift": {
                "type": "boolean",
                "default": True,
                "description": "Re-grade chained segments to the opening segment's colour statistics.",
            },
            "num_inference_steps": {"type": "integer"},
            "guidance_scale": {"type": "number"},
            "guidance_scale_2": {"type": "number", "description": "Second-expert guidance on MoE (A14B) variants"},
            "precision": {
                "type": "string",
                "enum": ["auto", "bf16", "int8", "int4"],
                "default": "auto",
                "description": "Weight precision. auto picks the best fit for the visible VRAM.",
            },
            "enable_model_offload": {"type": "boolean", "default": True},
            "offload_mode": {
                "type": "string",
                "enum": ["auto", "model", "sequential"],
                "default": "auto",
                "description": (
                    "How weights are staged onto the GPU. 'model' keeps a whole component "
                    "resident (fastest); 'sequential' streams one submodule at a time, which "
                    "is what lets a 12GB card render above 512x320."
                ),
            },
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=16000, vram_mb=8000, disk_mb=40000, network_required=False)
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "model_variant", "operation", "seed", "duration_seconds"]
    side_effects = ["writes video file to output_path", "may download model weights"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and artifacts",
        "On chained clips, check the segment seams for a jump in colour or subject pose",
    ]

    def get_status(self) -> ToolStatus:
        return local_generation_status()

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def _plan(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Resolve the frame/segment plan without loading any weights."""
        meta = WAN_VARIANTS.get(inputs.get("model_variant") or DEFAULT_VARIANT, WAN_VARIANTS[DEFAULT_VARIANT])
        fps = int(inputs.get("fps") or meta["fps"])
        segment_frames = snap_frames(int(inputs.get("segment_frames") or meta["default_num_frames"]))
        if inputs.get("num_frames"):
            total_frames = int(inputs["num_frames"])
        elif inputs.get("duration_seconds"):
            total_frames = max(1, round(float(inputs["duration_seconds"]) * fps))
        else:
            total_frames = segment_frames
        if inputs.get("operation") == "text_to_image":
            total_frames = segment_frames = 1
        # A clip shorter than one native segment is generated at its own length,
        # not padded out to the model's default.
        segment_frames = min(segment_frames, max(1, total_frames))

        from tools.video._wan_engine import resolve_offload_mode, resolve_precision

        precision = resolve_precision(inputs.get("precision", "auto"), meta["params_b"])
        return {
            "meta": meta,
            "precision": precision,
            "offload_mode": resolve_offload_mode(
                inputs.get("offload_mode", "auto"), precision, meta["params_b"]
            ),
            "fps": fps,
            "segment_frames": segment_frames,
            "total_frames": total_frames,
            "segments": plan_segments(total_frames, segment_frames),
            "steps": int(inputs.get("num_inference_steps") or meta["default_steps"]),
            "width": int(inputs.get("width") or meta["default_width"]),
            "height": int(inputs.get("height") or meta["default_height"]),
        }

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimated wall-clock seconds, including weight loading.

        Every chained segment pays the full per-step cost again, so a 30s clip
        costs roughly six times a 5s one rather than a little more.
        """
        plan = self._plan(inputs)
        megapixels = (plan["width"] * plan["height"]) / 1_000_000
        stream = (
            _SEQUENTIAL_STREAM_SECONDS_PER_STEP
            if plan["offload_mode"] == "sequential"
            else 0.0
        )
        per_step = stream + plan["segment_frames"] * megapixels * _SECONDS_PER_STEP_PER_MPX_FRAME
        return round(plan["segments"] * plan["steps"] * per_step + _MODEL_LOAD_SECONDS, 1)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Wan local video generation is unavailable. " + self.install_instructions)
        start = time.time()
        try:
            result = generate_wan(
                tool_name=self.name,
                variants=WAN_VARIANTS,
                default_variant=DEFAULT_VARIANT,
                inputs=inputs,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Wan video generation failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result
