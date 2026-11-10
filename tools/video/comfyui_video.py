"""ComfyUI video generation via a local or remote ComfyUI server.

Supports text-to-video and image-to-video using WAN 2.2 14B with
4-step LightX2V LoRA acceleration, and MiniMax H3 open weights
(``model_family="minimax_h3_local"``, 20-step base mode with native audio).
Custom workflows are accepted via the ``workflow_json`` input.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

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
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import (
    BUNDLED_MODEL_STACKS,
    COMFYUI_SETUP_OFFER,
    MODEL_LICENSE_NOTES,
    missing_models_payload,
    model_stack,
    workflow_hash,
)
from tools.video._shared import probe_output

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"

# Output node IDs in the bundled workflows
_T2V_OUTPUT_NODE = "16"
_I2V_OUTPUT_NODE = "108"

# --- MiniMax H3 (local open weights) -------------------------------------
# Node IDs follow the official Comfy-Org templates (video_minimax_h3_t2v /
# video_minimax_h3_i2v); the bundled JSON is their API-format equivalent.
_H3_STACK = "minimax-h3-local"
_H3_WORKFLOWS = {
    "text_to_video": "minimax-h3-t2v.json",
    "image_to_video": "minimax-h3-i2v.json",
}
_H3_OUTPUT_NODE = "92"
_H3_FPS = 24
_H3_FRAME_STEP = 17  # valid frame counts are 17k + 5
_H3_FRAME_OFFSET = 5
_H3_MIN_SECONDS = 4
_H3_MAX_SECONDS = 15  # ~362 frames, the top of the trained range
_H3_LONG_EDGE = 1344  # native 16:9 canvas is 1344x768
_H3_SHORT_EDGE = 768
_H3_CANVAS_STEP = 32
_H3_DEFAULT_STEPS = 20
# Runtime estimate, calibrated on one measured setting: a 4 s clip (107 frames)
# at 1344x768 with 20 base steps took 185 s (text-to-video, weights not yet
# loaded) and 178 s (image-to-video, right after it) through this tool on a
# rented RTX 5090 with cu130 PyTorch and SageAttention (2026-11-10). The split
# between loading and sampling below is assumed, not measured, and other GPUs,
# step counts and clip lengths are extrapolated linearly from that point.
_H3_SECONDS_PER_STEP_PER_5S = 7.5
_H3_LOAD_OVERHEAD_SECONDS = 60


def h3_frame_count(seconds: float) -> int:
    """Return the H3 frame count for *seconds* at 24 fps.

    H3 only accepts counts on the ``17k + 5`` grid; ComfyUI snaps an off-grid
    ``length`` up, so snapping here keeps the reported duration honest.
    """
    frames = max(_H3_FRAME_OFFSET, round(seconds * _H3_FPS))
    return frames + (_H3_FRAME_OFFSET - frames % _H3_FRAME_STEP) % _H3_FRAME_STEP


def _snap_canvas_edge(value: float) -> int:
    """Round to the nearest multiple of 32 (ties up), never below 32."""
    return max(
        _H3_CANVAS_STEP, int(value / _H3_CANVAS_STEP + 0.5) * _H3_CANVAS_STEP
    )


def h3_canvas_for_ratio(ratio_w: float, ratio_h: float) -> tuple[int, int]:
    """Return the largest H3 canvas (width, height) with the given aspect ratio.

    The short edge is 768 unless that would push the long edge past 1344, in
    which case the long edge is pinned to 1344 (e.g. 21:9 -> 1344x576).
    """
    if ratio_w <= 0 or ratio_h <= 0:
        raise ValueError(f"aspect ratio must be positive, got {ratio_w}:{ratio_h}")
    landscape = ratio_w >= ratio_h
    ratio = max(ratio_w, ratio_h) / min(ratio_w, ratio_h)
    short = _H3_SHORT_EDGE
    long = _snap_canvas_edge(short * ratio)
    if long > _H3_LONG_EDGE:
        long = _H3_LONG_EDGE
        short = _snap_canvas_edge(long / ratio)
    return (long, short) if landscape else (short, long)


def h3_snap_canvas(width: int, height: int) -> tuple[int, int]:
    """Snap an explicit size to multiples of 32 and enforce H3's native canvas."""
    w, h = _snap_canvas_edge(width), _snap_canvas_edge(height)
    if max(w, h) > _H3_LONG_EDGE or min(w, h) > _H3_SHORT_EDGE:
        raise ValueError(
            f"{w}x{h} is past MiniMax H3's native canvas (long edge <= "
            f"{_H3_LONG_EDGE}, short edge <= {_H3_SHORT_EDGE}). Use 1344x768 "
            "(16:9) or 768x1344 (9:16); the 1.0 MP preset gives a 1376 px edge "
            "and is over the limit."
        )
    return w, h


def _parse_aspect_ratio(value: str) -> tuple[float, float]:
    try:
        left, right = str(value).split(":")
        return float(left), float(right)
    except ValueError as exc:
        raise ValueError(
            f"aspect_ratio must look like '16:9', got {value!r}"
        ) from exc

# Models required by the bundled WAN 2.2 workflows
_REQUIRED_MODELS_COMMON = [
    "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
]
_REQUIRED_MODELS_I2V = [
    *_REQUIRED_MODELS_COMMON,
    "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "wan_2.1_vae.safetensors",
    "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
]
_REQUIRED_MODELS_T2V = [
    *_REQUIRED_MODELS_COMMON,
    "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
    "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
    "wan_2.1_vae.safetensors",
    "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
    "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
]

# Single source of truth: the loaders in the bundled H3 graphs and this list
# are checked against the same metadata stack by the contract tests.
_REQUIRED_MODELS_H3 = [item["name"] for item in BUNDLED_MODEL_STACKS[_H3_STACK]]

# Bundled local families, in the order a call that names no model_family tries
# them. wan2.2 stays first so servers that have it behave as they always did.
_DEFAULT_FAMILY = "wan2.2"
_LOCAL_FAMILY_ORDER = (_DEFAULT_FAMILY, "minimax_h3_local")
_OPERATIONS = ("text_to_video", "image_to_video")

_RESOURCE_PROFILES = {
    "provider_floor": {
        "vram_mb": 8000,
        "ram_mb": 16000,
        "applies_to": (
            "ComfyUI provider availability and low-VRAM custom workflows. "
            "Actual requirements depend on workflow_json/workflow_path."
        ),
    },
    "bundled_wan22_14b_fp8": {
        "vram_mb": 16000,
        "ram_mb": 32000,
        "applies_to": (
            "Bundled WAN 2.2 14B FP8 T2V/I2V workflows. This is not a "
            "ComfyUI provider-wide requirement."
        ),
    },
    "low_vram_custom_workflows": {
        "vram_mb": "8000-12000",
        "ram_mb": "16000-32000",
        "examples": [
            "Wan 2.1 1.3B",
            "LTX-Video / LTXV FP8 or quantized workflows",
            "Wan 2.2 GGUF / quantized community workflows",
        ],
    },
}


class ComfyUIVideo(BaseTool):
    name = "comfyui_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "Bundled local WAN requires WAN 2.2 models and LightX2V LoRAs. Local "
        "MiniMax H3 (model_family=minimax_h3_local) runs a bundled 20-step "
        "workflow once the four files in the Comfy-Org/MiniMax-H3 stack are "
        "installed; it needs a large GPU (see docs) and its licence excludes "
        "the EU, UK, South Korea and the US.\n"
        "Gemini Omni, Seedance 2.5, and MiniMax H3 Partner Nodes require a "
        "logged-in Comfy account, credits, and network access.\n"
        "Running a separate ComfyUI instance for video? Set COMFYUI_VIDEO_SERVER_URL "
        "instead -- it takes priority over COMFYUI_SERVER_URL for this tool only."
    )
    agent_skills = [
        "comfyui",
        "gemini-omni",
        "seedance-2-5",
        "minimax-h3",
        "ai-video-gen",
        "ltx2",
    ]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "seed": True,
        "reference_image": True,
        "custom_workflow": True,
        "custom_output_node": True,
        "offline": True,
        "gemini_omni_flash_partner_node": True,
        "seedance_2_5_partner_node": True,
        "minimax_h3_partner_node": True,
        "minimax_h3_local_weights": True,
    }
    best_for = [
        "local GPU video generation without API costs",
        "Blackwell / DGX Spark hardware where diffusers is unsupported",
        "image-to-video with WAN 2.2 14B (4-step accelerated)",
        "text-to-video with WAN 2.2 14B (4-step accelerated)",
        "custom low-VRAM ComfyUI workflows on 8GB-12GB GPUs",
        "ComfyUI Partner Node workflows for Gemini Omni Flash, Seedance 2.5, and MiniMax H3",
        "open-weight MiniMax H3 custom workflows with native stereo audio",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "CPU-only machines",
        "running the bundled WAN 2.2 14B FP8 workflows on GPUs below 16GB VRAM",
    ]
    fallback = "wan_video"
    fallback_tools = ["wan_video", "hunyuan_video", "ltx_video_local", "kling_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt for video generation",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model_family": {
                "type": "string",
                "enum": [
                    "wan2.2",
                    "gemini_omni_flash",
                    "seedance_2.5",
                    "minimax_h3_api",
                    "minimax_h3_local",
                    "ltx_2.5_local",
                ],
                "default": "wan2.2",
                "description": (
                    "Built-in execution family. The three *_api/hosted families use "
                    "ComfyUI Partner Nodes and credits; minimax_h3_local runs the open "
                    "weights through a bundled T2V/I2V workflow (or a caller-supplied "
                    "workflow_path/workflow_json)."
                ),
            },
            "reference_image_path": {
                "type": "string",
                "description": "Local path to reference image (for image_to_video)",
            },
            "reference_image_url": {
                "type": "string",
                "description": "URL of reference image (for image_to_video, downloaded first)",
            },
            "width": {
                "type": "integer",
                "default": 832,
                "description": "T2V default 832, I2V default 640",
            },
            "height": {
                "type": "integer",
                "default": 480,
                "description": "T2V default 480, I2V default 640",
            },
            "num_frames": {
                "type": "integer",
                "default": 81,
                "description": "81 frames = 5s at 16fps",
            },
            "duration": {
                "type": "integer",
                "minimum": 3,
                "maximum": 30,
                "default": 5,
                "description": (
                    "Clip length in seconds for Partner Nodes and minimax_h3_local "
                    "(local H3 accepts 4-15 s and snaps up to the 17k+5 frame grid "
                    "at 24 fps). Bundled WAN still uses num_frames."
                ),
            },
            "steps": {
                "type": "integer",
                "minimum": 1,
                "description": (
                    "Sampling steps for minimax_h3_local (default 20; the model card "
                    "uses 50 for maximum quality). Ignored by other families."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "768P", "2K"],
                "default": "720p",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the video"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON. Requires output_node.",
            },
            "workflow_path": {
                "type": "string",
                "description": "Optional path to a ComfyUI workflow JSON file. Requires output_node.",
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label for a custom workflow.",
            },
            "workflow_model_stack": {
                "type": "array",
                "description": (
                    "Optional provenance metadata for custom workflow dependencies. "
                    "Items should include name, role, quantization, scheduler, "
                    "and LoRA strengths when known."
                ),
                "items": {"type": "object"},
            },
            "timeout_seconds": {
                "type": "integer",
                "description": (
                    "How long to wait for the ComfyUI job to finish before giving up. "
                    "Default 3600s (1hr) covers slow/local GPUs and non-accelerated "
                    "custom workflows; raise it further for large frame counts or "
                    "high resolutions. On timeout the job is NOT cancelled server-side "
                    "and the error's data.prompt_id can be passed back via "
                    "resume_prompt_id to keep waiting without resubmitting."
                ),
            },
            "resume_prompt_id": {
                "type": "string",
                "description": (
                    "A prompt_id from a previous timed-out call (see error data on "
                    "timeout). Skips resubmission and just resumes waiting/downloading."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2,
        ram_mb=16000,
        vram_mb=8000,
        disk_mb=2000,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = [
        "prompt",
        "operation",
        "width",
        "height",
        "num_frames",
        "seed",
    ]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and artifacts"
    ]

    def __init__(self) -> None:
        self._client = ComfyUIClient(capability="video")
        self._last_progress_log = 0.0

    def _log_progress(self, data: dict) -> None:
        """Print a throttled progress line for long video renders.

        Video jobs can run for tens of minutes; without this the process
        looks hung. Throttled to once per 10s since ComfyUI pushes a
        ``progress`` event per sampling step, which would otherwise flood
        stdout on fast GPUs.
        """
        now = time.monotonic()
        if now - self._last_progress_log < 10:
            return
        self._last_progress_log = now
        value, max_value = data.get("value"), data.get("max")
        if value is not None and max_value:
            print(f"[comfyui_video] step {value}/{max_value}")

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        statuses = self.operation_statuses()
        if any(status == "available" for status in statuses.values()):
            return ToolStatus.AVAILABLE
        if statuses:
            return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def model_family_statuses(self) -> dict[str, dict[str, str]]:
        """Return per-operation readiness of each bundled local family.

        A server set up for MiniMax H3 has none of the WAN 2.2 files, so
        readiness has to be judged per family, not on WAN alone.
        """
        if not self._client.is_available():
            return {
                family: {operation: "unavailable" for operation in _OPERATIONS}
                for family in _LOCAL_FAMILY_ORDER
            }

        def ready(required: list[str]) -> str:
            _, missing = self._client.check_models(required)
            return "available" if not missing else "degraded"

        h3 = ready(_REQUIRED_MODELS_H3)
        return {
            "wan2.2": {
                "text_to_video": ready(_REQUIRED_MODELS_T2V),
                "image_to_video": ready(_REQUIRED_MODELS_I2V),
            },
            # One checkpoint serves both H3 operations.
            "minimax_h3_local": {operation: h3 for operation in _OPERATIONS},
        }

    def operation_statuses(
        self, family_statuses: dict[str, dict[str, str]] | None = None
    ) -> dict[str, str]:
        """Return per-operation readiness for selector routing and preflight.

        An operation is ready when any bundled local family can run it.
        """
        families = family_statuses or self.model_family_statuses()
        statuses: dict[str, str] = {}
        for operation in _OPERATIONS:
            states = {families[family][operation] for family in _LOCAL_FAMILY_ORDER}
            if "available" in states:
                statuses[operation] = "available"
            elif states == {"unavailable"}:
                statuses[operation] = "unavailable"
            else:
                statuses[operation] = "degraded"
        return statuses

    def default_model_family(
        self, family_statuses: dict[str, dict[str, str]] | None = None
    ) -> dict[str, str]:
        """Return the family a call without ``model_family`` runs, per operation.

        The first installed family in ``_LOCAL_FAMILY_ORDER`` wins. With none
        installed it stays ``wan2.2``, so the missing-model report names the
        documented default.
        """
        families = family_statuses or self.model_family_statuses()
        return {
            operation: next(
                (
                    family
                    for family in _LOCAL_FAMILY_ORDER
                    if families[family][operation] == "available"
                ),
                _DEFAULT_FAMILY,
            )
            for operation in _OPERATIONS
        }

    def is_operation_available(self, operation: str) -> bool:
        if operation not in {"text_to_video", "image_to_video"}:
            return False
        return self.operation_statuses().get(operation) == "available"

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        family_statuses = self.model_family_statuses()
        info["operation_statuses"] = self.operation_statuses(family_statuses)
        info["model_family_statuses"] = family_statuses
        info["default_model_family"] = self.default_model_family(family_statuses)
        info["resource_profiles"] = _RESOURCE_PROFILES
        info["setup_offer"] = self.setup_offer
        info["bundled_model_stacks"] = {
            "text_to_video": BUNDLED_MODEL_STACKS["wan22-t2v-4step"],
            "image_to_video": BUNDLED_MODEL_STACKS["wan22-i2v-4step"],
            "minimax_h3_local": BUNDLED_MODEL_STACKS[_H3_STACK],
        }
        info["license_notes"] = {"minimax_h3_local": MODEL_LICENSE_NOTES["minimax-h3"]}
        info["resource_profile_note"] = (
            "The top-level resource_profile is a ComfyUI provider floor, not a "
            "promise that every workflow fits 8GB VRAM. Bundled WAN 2.2 14B FP8 "
            "workflows recommend 16GB VRAM; custom low-VRAM workflows can target "
            "8GB-12GB depending on model, quantization, resolution, and frame count."
        )
        info["execution_modes"] = {
            "wan2.2": {
                "hosted": False,
                "network_required": False,
                "cost": "local compute",
            },
            "minimax_h3_local": {
                "hosted": False,
                "network_required": False,
                "cost": "local compute",
            },
            "gemini_omni_flash": {
                "hosted": True,
                "network_required": True,
                "billing": "ComfyUI Partner Node credits",
            },
            "seedance_2.5": {
                "hosted": True,
                "network_required": True,
                "billing": "ComfyUI Partner Node credits",
            },
            "minimax_h3_api": {
                "hosted": True,
                "network_required": True,
                "billing": "ComfyUI Partner Node credits",
            },
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        family = str(inputs.get("model_family", "wan2.2"))
        duration = float(inputs.get("duration", 5))
        if family == "gemini_omni_flash":
            return round(0.146 * duration, 4)
        if family == "seedance_2.5":
            rate = 0.1483 if inputs.get("resolution", "720p") == "480p" else 0.3333
            return round(rate * duration, 4)
        if family == "minimax_h3_api":
            rate = 0.1287 if inputs.get("resolution", "768P") == "768P" else 0.1859
            return round(rate * duration, 4)
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        if str(inputs.get("model_family")) == "minimax_h3_local" and not (
            inputs.get("workflow_json") or inputs.get("workflow_path")
        ):
            steps = int(inputs.get("steps", _H3_DEFAULT_STEPS))
            duration = float(inputs.get("duration", 5))
            return round(
                _H3_LOAD_OVERHEAD_SECONDS
                + _H3_SECONDS_PER_STEP_PER_5S * steps * duration / 5,
                1,
            )
        operation = inputs.get("operation", "text_to_video")
        if operation == "image_to_video":
            return 210.0  # ~3.5 min
        return 240.0  # ~4 min

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        custom_workflow = bool(
            inputs.get("workflow_json") or inputs.get("workflow_path")
        )
        # A caller that names no family gets whichever bundled local family the
        # server has; an explicit choice is never swapped for another model.
        auto_family = not custom_workflow and not inputs.get("model_family")
        model_family = str(inputs.get("model_family") or _DEFAULT_FAMILY)
        partner_nodes = {
            "gemini_omni_flash": "GeminiVideoOmni",
            "seedance_2.5": "ByteDance2TextToVideoNode",
            "minimax_h3_api": "MinimaxHailuo03TextToVideoNode",
        }
        if model_family == "ltx_2.5_local" and not custom_workflow:
            return ToolResult(
                success=False,
                error="LTX-2.5 local requires an installed model stack and an exported ComfyUI API workflow via workflow_path/workflow_json plus output_node. No older LTX or WAN fallback is performed.",
                data={"model": "LTX-2.5", "setup_required": True},
            )
        if (
            model_family in partner_nodes
            and inputs.get("operation", "text_to_video") != "text_to_video"
        ):
            return ToolResult(
                success=False,
                error=(
                    f"Built-in {model_family} Partner Node execution currently supports "
                    "text_to_video; use an official ComfyUI custom workflow for other modes."
                ),
            )
        if custom_workflow and not inputs.get("output_node"):
            return ToolResult(
                success=False,
                error=(
                    "Custom ComfyUI workflows require output_node so OpenMontage "
                    "knows which ComfyUI node to download artifacts from."
                ),
            )

        if not self._client.is_available():
            return ToolResult(
                success=False,
                error=self._client.unavailable_reason(),
            )

        operation = inputs.get("operation", "text_to_video")

        if auto_family:
            model_family = self.default_model_family().get(operation, _DEFAULT_FAMILY)
        # Model naming and provenance read the family from the inputs.
        inputs = {**inputs, "model_family": model_family}

        if not custom_workflow and model_family == "wan2.2":
            required = (
                _REQUIRED_MODELS_I2V
                if operation == "image_to_video"
                else _REQUIRED_MODELS_T2V
            )
            _, missing = self._client.check_models(required)
            if missing:
                workflow_key = (
                    "wan22-i2v-4step"
                    if operation == "image_to_video"
                    else "wan22-t2v-4step"
                )
                return ToolResult(
                    success=False,
                    data=missing_models_payload(
                        missing,
                        workflow_key=workflow_key,
                        workflow_name=f"{workflow_key}.json",
                        operation=operation,
                    ),
                    error=(
                        f"ComfyUI server is running but missing models for {operation}: "
                        f"{', '.join(missing)}.\n"
                        f"See data.missing_models for destination hints and download URLs."
                    ),
                )
        if not custom_workflow and model_family == "minimax_h3_local":
            _, missing = self._client.check_models(_REQUIRED_MODELS_H3)
            if missing:
                return ToolResult(
                    success=False,
                    data=missing_models_payload(
                        missing,
                        workflow_key=_H3_STACK,
                        workflow_name=_H3_WORKFLOWS[operation],
                        operation=operation,
                    ),
                    error=(
                        f"ComfyUI server is running but missing MiniMax H3 models: "
                        f"{', '.join(missing)}.\n"
                        f"See data.missing_models for destination hints and download URLs."
                    ),
                )

        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        output_path = Path(
            inputs.get("output_path", f"comfyui_video_{operation}_{seed}.mp4")
        )
        h3_params: dict[str, Any] | None = None

        try:
            if custom_workflow:
                workflow = self._load_custom_workflow(inputs)
                output_node = str(inputs["output_node"])
            elif model_family == "minimax_h3_local":
                workflow, output_node, h3_params = self._build_h3_local(
                    inputs, seed, output_path, operation
                )
            elif model_family in partner_nodes:
                node_class = partner_nodes[model_family]
                if not self._client.has_node(node_class):
                    raise ComfyUIError(
                        f"ComfyUI server does not expose {node_class}; update ComfyUI "
                        "and enable Partner Nodes. These are hosted API nodes, not offline models."
                    )
                workflow, output_node = self._build_partner_t2v(
                    inputs, seed, output_path, model_family
                )
            elif operation == "image_to_video":
                workflow, output_node = self._build_i2v(inputs, seed, output_path)
            else:
                workflow, output_node = self._build_t2v(inputs, seed, output_path)

            provenance = self._workflow_provenance(
                inputs, custom_workflow, output_node, operation, workflow, model_family
            )
            paths = self._client.generate(
                workflow,
                output_node=output_node,
                dest=output_path,
                timeout=inputs.get("timeout_seconds", 3600),
                interval=10,
                resume_prompt_id=inputs.get("resume_prompt_id"),
                on_progress=self._log_progress,
            )

        except ComfyUIError as exc:
            data = {"prompt_id": exc.prompt_id} if exc.prompt_id else {}
            if exc.prompt_id:
                error_msg = (
                    f"{exc}\n\nThis job was NOT cancelled and is very likely still "
                    f"running server-side. To recover it without resubmitting, call "
                    f"execute() again with resume_prompt_id={exc.prompt_id!r} "
                    f"(and a longer timeout_seconds if it needs more time), or poll "
                    f"GET {{COMFYUI_SERVER_URL}}/history/{exc.prompt_id} directly."
                )
            else:
                error_msg = str(exc)
            return ToolResult(success=False, error=error_msg, data=data)
        except Exception as exc:
            return ToolResult(
                success=False, error=f"ComfyUI video generation failed: {exc}"
            )

        model_name = self._model_name(inputs, custom_workflow)
        partner_execution = model_family in partner_nodes and not custom_workflow
        result_data: dict[str, Any] = {
            "provider": "comfyui",
            "model": model_name,
            "prompt": inputs["prompt"],
            "operation": operation,
            "output": str(paths[0]),
            "format": "mp4",
            "workflow_provenance": provenance,
            "hosted": partner_execution,
            "network_required": partner_execution,
            "model_family": model_family,
            "model_family_auto_selected": auto_family,
        }
        if partner_execution:
            result_data.update(
                {
                    "duration_seconds": int(inputs.get("duration", 5)),
                    "fps": 24,
                    "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                    "resolution": inputs.get("resolution", "720p"),
                    "billing": "ComfyUI Partner Node credits",
                }
            )
        elif h3_params is not None:
            result_data.update(
                {
                    **h3_params,
                    "fps": _H3_FPS,
                    "duration_seconds": round(h3_params["num_frames"] / _H3_FPS, 2),
                    "has_audio": True,
                }
            )
        else:
            width = inputs.get("width", 832 if operation == "text_to_video" else 640)
            height = inputs.get("height", 480 if operation == "text_to_video" else 640)
            num_frames = inputs.get("num_frames", 81)
            result_data.update(
                {
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                    "fps": 16,
                    "duration_seconds": round(num_frames / 16, 2),
                }
            )
        wall = round(time.time() - start, 3)
        comfy_timing = dict(getattr(self._client, "last_timing", None) or {})
        exec_s = comfy_timing.get("comfy_prompt_exec_s")
        overhead = wall
        if isinstance(exec_s, (int, float)):
            overhead = round(max(0.0, wall - float(exec_s)), 3)
        result_data["timing"] = {
            **comfy_timing,
            "client_overhead_s": overhead,
            "wall_s": wall,
        }


        result_data.update(self._probe_media(paths[0]))
        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(p) for p in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    # ------------------------------------------------------------------
    # Workflow builders
    # ------------------------------------------------------------------

    def _build_t2v(
        self, inputs: dict[str, Any], seed: int, output_path: Path
    ) -> tuple[dict, str]:
        width = inputs.get("width", 832)
        height = inputs.get("height", 480)
        num_frames = inputs.get("num_frames", 81)

        workflow = ComfyUIClient.load_workflow(_WORKFLOWS / "wan22-t2v-4step.json")
        workflow = ComfyUIClient.patch_workflow(
            workflow,
            {
                "2": {"text": inputs["prompt"]},
                # `length` is the frame count, `batch_size` is how many separate
                # clips to make. Node 11 used to be an EmptyLatentImage with
                # batch_size=num_frames, which asks for 81 unrelated images
                # rather than one 81-frame video: the mp4 has the right frame
                # count and duration and passes ffprobe, but strobes. WAN 2.2
                # needs a temporal video latent, as ComfyUI's own
                # video_wan2_2_14B_t2v template uses.
                "11": {
                    "width": width,
                    "height": height,
                    "length": num_frames,
                    "batch_size": 1,
                },
                "12": {"noise_seed": seed},
                "16": {"filename_prefix": output_path.stem},
            },
        )
        return workflow, _T2V_OUTPUT_NODE

    def _build_i2v(
        self, inputs: dict[str, Any], seed: int, output_path: Path
    ) -> tuple[dict, str]:
        width = inputs.get("width", 640)
        height = inputs.get("height", 640)
        num_frames = inputs.get("num_frames", 81)

        server_name, _ = self._stage_reference_image(inputs, output_path)

        workflow = ComfyUIClient.load_workflow(_WORKFLOWS / "wan22-i2v-4step.json")
        workflow = ComfyUIClient.patch_workflow(
            workflow,
            {
                "93": {"text": inputs["prompt"]},
                "97": {"image": server_name},
                "98": {"width": width, "height": height, "length": num_frames},
                "86": {"noise_seed": seed},
                "108": {"filename_prefix": output_path.stem},
            },
        )
        return workflow, _I2V_OUTPUT_NODE

    def _stage_reference_image(
        self, inputs: dict[str, Any], output_path: Path
    ) -> tuple[str, Path]:
        """Resolve the reference image and upload it to ComfyUI.

        Returns ``(server_side_name, local_path)``. A ``reference_image_url`` is
        downloaded next to *output_path* first.
        """
        ref_path = inputs.get("reference_image_path")
        ref_url = inputs.get("reference_image_url")

        if ref_url and not ref_path:
            resp = requests.get(ref_url, timeout=60)
            resp.raise_for_status()
            ref_path = str(output_path.with_suffix(".ref.png"))
            Path(ref_path).parent.mkdir(parents=True, exist_ok=True)
            Path(ref_path).write_bytes(resp.content)

        if not ref_path:
            raise ComfyUIError(
                "image_to_video requires reference_image_path or reference_image_url"
            )

        upload_name = f"om_{output_path.stem}.png"
        server_name = self._client.upload_image(Path(ref_path), upload_name)
        return server_name, Path(ref_path)

    def _build_h3_local(
        self,
        inputs: dict[str, Any],
        seed: int,
        output_path: Path,
        operation: str,
    ) -> tuple[dict, str, dict[str, Any]]:
        """Patch the bundled MiniMax H3 T2V/I2V graph.

        Returns ``(workflow, output_node, params)``. Bad durations or canvases
        raise :class:`ComfyUIError` so they surface as a normal tool error.
        """
        try:
            duration = float(inputs.get("duration", 5))
            if not _H3_MIN_SECONDS <= duration <= _H3_MAX_SECONDS:
                raise ValueError(
                    f"duration must be between {_H3_MIN_SECONDS} and "
                    f"{_H3_MAX_SECONDS} seconds for minimax_h3_local, got {duration:g}"
                )
            num_frames = h3_frame_count(duration)
            steps = int(inputs.get("steps", _H3_DEFAULT_STEPS))
            if steps < 1:
                raise ValueError(f"steps must be at least 1, got {steps}")

            explicit = inputs.get("width") is not None and inputs.get("height") is not None
            server_name: str | None = None
            if operation == "image_to_video":
                # The first frame is stretched to the canvas, so an unspecified
                # canvas follows the reference image's aspect ratio.
                server_name, local_path = self._stage_reference_image(inputs, output_path)
                if explicit:
                    width, height = h3_snap_canvas(inputs["width"], inputs["height"])
                else:
                    from PIL import Image

                    with Image.open(local_path) as image:
                        width, height = h3_canvas_for_ratio(*image.size)
            elif explicit:
                width, height = h3_snap_canvas(inputs["width"], inputs["height"])
            else:
                width, height = h3_canvas_for_ratio(
                    *_parse_aspect_ratio(inputs.get("aspect_ratio") or "16:9")
                )
        except ValueError as exc:
            raise ComfyUIError(str(exc)) from exc

        patches: dict[str, dict[str, Any]] = {
            "131": {
                "prompt": inputs["prompt"],
                "width": width,
                "height": height,
                "length": num_frames,
            },
            "129": {"noise_seed": seed},
            "124": {"steps": steps},
            "92": {"filename_prefix": f"video/{output_path.stem}"},
        }
        if server_name is not None:
            patches["114"] = {"image": server_name}

        workflow = ComfyUIClient.patch_workflow(
            ComfyUIClient.load_workflow(_WORKFLOWS / _H3_WORKFLOWS[operation]),
            patches,
        )
        params = {
            "width": width,
            "height": height,
            "num_frames": num_frames,
            "steps": steps,
        }
        return workflow, _H3_OUTPUT_NODE, params

    @staticmethod
    def _probe_media(path: Path) -> dict[str, Any]:
        """Measure the downloaded clip instead of trusting the request.

        Custom workflows set their own size, frame count and frame rate, so
        the request values (WAN defaults when omitted) can be wrong. When
        ffprobe cannot read the file, the request values are kept and the
        result is flagged so callers know they were not measured.
        """
        probed = probe_output(path) if path.is_file() else {}
        width = probed.get("video_width")
        height = probed.get("video_height")
        fps = probed.get("video_fps")
        duration = probed.get("duration_seconds")
        if not (width and height and fps and duration):
            warning = (
                f"Could not probe {path} with ffprobe; the reported media "
                "metadata comes from the request, not the output file."
            )
            print(f"[comfyui_video] {warning}")
            return {"metadata_source": "requested", "metadata_warning": warning}
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "num_frames": probed.get("video_num_frames") or round(duration * fps),
            "duration_seconds": duration,
            "metadata_source": "ffprobe",
        }

    @staticmethod
    def _load_custom_workflow(inputs: dict[str, Any]) -> dict:
        if inputs.get("workflow_json"):
            return json.loads(inputs["workflow_json"])
        return ComfyUIClient.load_workflow(Path(inputs["workflow_path"]))

    @staticmethod
    def _model_name(inputs: dict[str, Any], custom_workflow: bool) -> str:
        if not custom_workflow:
            return {
                "wan2.2": "wan2.2-14b-fp8-4step",
                "gemini_omni_flash": "gemini-omni-flash-preview (ComfyUI Partner Node)",
                "seedance_2.5": "Seedance 2.5 (ComfyUI Partner Node)",
                "minimax_h3_api": "MiniMax-H3 (ComfyUI Partner Node)",
                "minimax_h3_local": "MiniMax-H3 FL2VA int8 (ComfyUI local)",
            }.get(str(inputs.get("model_family", "wan2.2")), "custom-comfyui-model")
        if str(inputs.get("model_family")) == "ltx_2.5_local":
            return inputs.get("workflow_model") or "LTX-2.5 (local ComfyUI workflow)"
        if str(inputs.get("model_family")) == "minimax_h3_local":
            return inputs.get("workflow_model") or "MiniMax-H3 (local ComfyUI workflow)"
        return (
            inputs.get("workflow_model")
            or inputs.get("model")
            or inputs.get("workflow_name")
            or "custom-comfyui-workflow"
        )

    @staticmethod
    def _workflow_provenance(
        inputs: dict[str, Any],
        custom_workflow: bool,
        output_node: str,
        operation: str,
        workflow: dict[str, Any],
        model_family: str,
    ) -> dict[str, Any]:
        partner_nodes = {
            "gemini_omni_flash": "GeminiVideoOmni",
            "seedance_2.5": "ByteDance2TextToVideoNode",
            "minimax_h3_api": "MinimaxHailuo03TextToVideoNode",
        }
        if not custom_workflow and model_family in partner_nodes:
            return {
                "source": "comfyui_partner_node",
                "node_class": partner_nodes[model_family],
                "hosted": True,
                "network_required": True,
                "billing": "ComfyUI Partner Node credits",
                "workflow_hash_sha256": workflow_hash(workflow),
                "output_node": output_node,
            }
        if not custom_workflow and model_family == "minimax_h3_local":
            return {
                "source": "bundled",
                "workflow": _H3_WORKFLOWS[operation],
                "workflow_hash_sha256": workflow_hash(workflow),
                "model_stack": model_stack(_H3_STACK, inputs),
                "output_node": output_node,
            }
        if not custom_workflow:
            workflow_key = (
                "wan22-i2v-4step"
                if operation == "image_to_video"
                else "wan22-t2v-4step"
            )
            return {
                "source": "bundled",
                "workflow": (
                    "wan22-i2v-4step.json"
                    if operation == "image_to_video"
                    else "wan22-t2v-4step.json"
                ),
                "workflow_hash_sha256": workflow_hash(workflow),
                "model_stack": model_stack(workflow_key, inputs),
                "output_node": output_node,
            }
        local_h3 = model_family == "minimax_h3_local"
        return {
            "source": "user_supplied",
            "workflow_name": inputs.get("workflow_name"),
            "workflow_path": inputs.get("workflow_path"),
            "model": inputs.get("workflow_model") or inputs.get("model"),
            "workflow_hash_sha256": workflow_hash(workflow),
            "model_stack": (
                BUNDLED_MODEL_STACKS["minimax-h3-local"]
                if local_h3 and not inputs.get("workflow_model_stack")
                else model_stack(None, inputs)
            ),
            "model_stack_source": (
                "caller_supplied"
                if inputs.get("workflow_model_stack")
                else "official_minimax_h3_stack"
                if local_h3
                else "unknown_custom_workflow"
            ),
            "output_node": output_node,
        }

    @staticmethod
    def _build_partner_t2v(
        inputs: dict[str, Any], seed: int, output_path: Path, model_family: str
    ) -> tuple[dict[str, Any], str]:
        duration = int(inputs.get("duration", 5))
        ratio = inputs.get("aspect_ratio", "16:9")
        resolution = inputs.get("resolution", "720p")
        if model_family == "gemini_omni_flash":
            node_class = "GeminiVideoOmni"
            model = {
                "model": "Omni Flash",
                "prompt": (
                    f"{inputs['prompt']}\nGenerate a {duration}-second {ratio} video."
                ),
                "temperature": 1.0,
                "top_p": 0.95,
            }
        elif model_family == "seedance_2.5":
            node_class = "ByteDance2TextToVideoNode"
            model = {
                "model": "Seedance 2.5",
                "prompt": inputs["prompt"],
                "resolution": resolution if resolution in {"480p", "720p"} else "720p",
                "ratio": ratio,
                "duration": duration,
                "generate_audio": bool(inputs.get("generate_audio", True)),
            }
        else:
            node_class = "MinimaxHailuo03TextToVideoNode"
            model = {
                "model": "MiniMax H3",
                "prompt": inputs["prompt"],
                "resolution": "768P"
                if resolution not in {"768P", "2K"}
                else resolution,
                "ratio": ratio,
                "duration": duration,
            }
        workflow = {
            "1": {
                "class_type": node_class,
                "inputs": {"model": model, "seed": seed, "watermark": False},
            },
            "2": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["1", 0],
                    "filename_prefix": f"video/{output_path.stem}",
                    "format": "auto",
                    "codec": {"codec": "auto"},
                },
            },
        }
        if model_family == "gemini_omni_flash":
            workflow["1"]["inputs"].pop("watermark", None)
        return workflow, "2"
