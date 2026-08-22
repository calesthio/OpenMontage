"""ComfyUI video generation via a local or remote ComfyUI server.

Supports text-to-video and image-to-video using WAN 2.2 14B with
4-step LightX2V LoRA acceleration.  Custom workflows are accepted
via the ``workflow_json`` input.
"""

from __future__ import annotations

import json
import subprocess
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
    missing_models_payload,
    model_stack,
    workflow_hash,
)

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"

# Output node IDs in the bundled workflows
_T2V_OUTPUT_NODE = "16"
_I2V_OUTPUT_NODE = "108"

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
        "MiniMax H3 requires its official model stack and exported API workflow.\n"
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
                ],
                "default": "wan2.2",
                "description": (
                    "Built-in execution family. The three *_api/hosted families use "
                    "ComfyUI Partner Nodes and credits; minimax_h3_local uses open weights "
                    "through a caller-supplied official/custom workflow."
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
                "description": "Partner Node duration; bundled WAN still uses num_frames.",
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

    def operation_statuses(self) -> dict[str, str]:
        """Return per-operation readiness for selector routing and preflight."""
        if not self._client.is_available():
            return {
                "text_to_video": "unavailable",
                "image_to_video": "unavailable",
            }

        _, missing_t2v = self._client.check_models(_REQUIRED_MODELS_T2V)
        _, missing_i2v = self._client.check_models(_REQUIRED_MODELS_I2V)
        return {
            "text_to_video": "available" if not missing_t2v else "degraded",
            "image_to_video": "available" if not missing_i2v else "degraded",
        }

    def is_operation_available(self, operation: str) -> bool:
        if operation not in {"text_to_video", "image_to_video"}:
            return False
        return self.operation_statuses().get(operation) == "available"

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["operation_statuses"] = self.operation_statuses()
        info["resource_profiles"] = _RESOURCE_PROFILES
        info["setup_offer"] = self.setup_offer
        info["bundled_model_stacks"] = {
            "text_to_video": BUNDLED_MODEL_STACKS["wan22-t2v-4step"],
            "image_to_video": BUNDLED_MODEL_STACKS["wan22-i2v-4step"],
        }
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
        operation = inputs.get("operation", "text_to_video")
        if operation == "image_to_video":
            return 210.0  # ~3.5 min
        return 240.0  # ~4 min

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        custom_workflow = bool(
            inputs.get("workflow_json") or inputs.get("workflow_path")
        )
        model_family = str(inputs.get("model_family", "wan2.2"))
        partner_nodes = {
            "gemini_omni_flash": "GeminiVideoOmni",
            "seedance_2.5": "ByteDance2TextToVideoNode",
            "minimax_h3_api": "MinimaxHailuo03TextToVideoNode",
        }
        if model_family == "minimax_h3_local" and not custom_workflow:
            return ToolResult(
                success=False,
                data={
                    "provider": "comfyui",
                    "model": "MiniMax-H3",
                    "workflow_template": "https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json",
                    "model_stack": BUNDLED_MODEL_STACKS["minimax-h3-local"],
                },
                error=(
                    "minimax_h3_local requires the official MiniMax H3 ComfyUI workflow "
                    "exported in API format via workflow_json/workflow_path plus output_node."
                ),
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
        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        output_path = Path(
            inputs.get("output_path", f"comfyui_video_{operation}_{seed}.mp4")
        )

        try:
            if custom_workflow:
                workflow = self._load_custom_workflow(inputs)
                output_node = str(inputs["output_node"])
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
        coherence = self._assess_coherence(paths[0])
        if coherence:
            result_data["coherence"] = coherence
            if coherence.get("verdict") == "STROBING_STILLS":
                return ToolResult(
                    success=False,
                    error=(
                        "Generated video is a sequence of unrelated stills, not "
                        "motion (mean adjacent-frame difference "
                        f"{coherence['mean_abs_diff']:.1f} with coefficient of "
                        f"variation {coherence['cv']:.2f}). This is what a video "
                        "model produces when its latent is an image latent "
                        "rather than a temporal one -- check that the workflow's "
                        "latent node is EmptyHunyuanLatentVideo (or the "
                        "model-appropriate video latent) with `length` set to "
                        "the frame count and `batch_size` 1. The file itself is "
                        "structurally valid, which is why ffprobe accepts it."
                    ),
                    data=result_data,
                    artifacts=[str(p) for p in paths],
                    cost_usd=self.estimate_cost(inputs),
                    duration_seconds=round(time.time() - start, 2),
                    seed=seed,
                    model=model_name,
                )

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(p) for p in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    @staticmethod
    def _assess_coherence(path: Path) -> dict[str, Any] | None:
        """Is this actually motion, or a strobe of unrelated frames?

        The failure this catches is invisible to every structural check: a
        workflow whose latent is an image latent emits N independent stills, and
        the resulting mp4 has the right frame count, the right duration, the
        right codec and a clean ffprobe. Only the relationship between
        consecutive frames tells them apart.

        Purely numerical -- it says nothing about what the frames depict.
        Decode to small greyscale, take the mean absolute difference between
        each adjacent pair, and look at the distribution: coherent motion gives
        small, smoothly varying differences, while independent stills give
        large ones that barely vary, because every pair is equally unrelated.

        Returns None when the check cannot run (no ffmpeg, no numpy, too few
        frames). A diagnostic that cannot run must never fail a good render.
        """
        try:
            import numpy as np
        except ImportError:
            return None

        w, h = 104, 60
        try:
            proc = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(path),
                 "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                capture_output=True, check=False, timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        buf = np.frombuffer(proc.stdout, dtype=np.uint8)
        n = buf.size // (w * h)
        if n < 3:
            return None
        frames = buf[: n * w * h].reshape(n, h, w).astype(np.int16)
        diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
        mean = float(diffs.mean())
        cv = float(diffs.std() / mean) if mean else 0.0

        # Thresholds separate two populations measured on this failure: coherent
        # WAN 2.2 clips run mean 3.5-9 with cv 0.18-0.59, while 81 independent
        # stills land far higher with a very low cv -- every pair is equally
        # unrelated, so the differences barely vary. Both conditions must hold,
        # so a legitimately busy clip (high mean, high cv) is not condemned.
        strobing = mean > 25.0 and cv < 0.35
        return {
            "frames_analyzed": int(n),
            "mean_abs_diff": round(mean, 2),
            "median_abs_diff": round(float(np.median(diffs)), 2),
            "cv": round(cv, 3),
            "verdict": "STROBING_STILLS" if strobing else "COHERENT_MOTION",
        }

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

        # Resolve reference image
        ref_path = inputs.get("reference_image_path")
        ref_url = inputs.get("reference_image_url")

        if ref_url and not ref_path:
            # Download to a temp location
            resp = requests.get(ref_url, timeout=60)
            resp.raise_for_status()
            ref_path = str(output_path.with_suffix(".ref.png"))
            Path(ref_path).parent.mkdir(parents=True, exist_ok=True)
            Path(ref_path).write_bytes(resp.content)

        if not ref_path:
            raise ComfyUIError(
                "image_to_video requires reference_image_path or reference_image_url"
            )

        # Upload to ComfyUI
        upload_name = f"om_{output_path.stem}.png"
        server_name = self._client.upload_image(Path(ref_path), upload_name)

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
            }.get(str(inputs.get("model_family", "wan2.2")), "custom-comfyui-model")
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
