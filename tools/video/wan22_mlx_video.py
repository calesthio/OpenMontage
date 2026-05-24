"""Wan 2.2 local MLX text-to-video / image-to-video generation.

Apple-Silicon-native video generation via Prince Canuma's `mlx-video`
package (https://github.com/Blaizzy/mlx-video) — pure MLX, no PyTorch
dependency, runs on M-series unified memory.

Why a separate tool from `wan_video.py`:
- `wan_video.py` wraps the diffusers / PyTorch Wan 2.1 path. Works on
  CUDA + (laboriously) on MPS, but PyTorch's MPS backend has rough edges
  for video diffusion (memory pressure, fallback ops).
- `wan22_mlx_video` targets the MLX-native Wan 2.2 path. Faster on
  Apple Silicon, less memory thrash, supports newer Wan 2.2 architectures
  (T2V-14B, TI2V-5B, I2V-14B).
- gbb-os / atx-os / GLI-OS marketing ensembles call
  `registry.get("wan22_mlx_video")` by name; this tool provides the
  implementation.

Hardware:
- M5 Max 128 GB: T2V-14B / TI2V-5B fits comfortably at fp16
- M4 32 GB: TI2V-5B fits; T2V-14B borderline (may need offload/lower-res)
- CUDA / non-Apple-Silicon: tool reports UNAVAILABLE

Install requirements (deferred to first use; tool returns INSTALL_REQUIRED
status until met):
- `pip install git+https://github.com/Blaizzy/mlx-video.git`
- Model weights downloaded to a local directory via `huggingface-cli download`
  or by mlx-video's own loader on first invocation
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
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


WAN22_MLX_VARIANTS = {
    "wan2.2-ti2v-5b": {
        "name": "Wan 2.2 TI2V (5B)",
        "hf_id": "Wan-AI/Wan2.2-TI2V-5B",
        "module": "mlx_video.wan_2.generate",
        "vram_mb": 12000,
        "quality": "high",
        "speed": "medium",
        "t2v": True,
        "i2v": True,
        "default_width": 832,
        "default_height": 480,
        "default_num_frames": 81,
        "default_steps": 30,
        "fps": 16,
    },
    "wan2.2-t2v-14b": {
        "name": "Wan 2.2 T2V (14B)",
        "hf_id": "Wan-AI/Wan2.2-T2V-14B",
        "module": "mlx_video.wan_2.generate",
        "vram_mb": 32000,
        "quality": "highest",
        "speed": "slow",
        "t2v": True,
        "i2v": False,
        "default_width": 1280,
        "default_height": 720,
        "default_num_frames": 81,
        "default_steps": 40,
        "fps": 16,
    },
    "wan2.2-i2v-14b": {
        "name": "Wan 2.2 I2V (14B)",
        "hf_id": "Wan-AI/Wan2.2-I2V-14B",
        "module": "mlx_video.wan_2.generate",
        "vram_mb": 32000,
        "quality": "highest",
        "speed": "slow",
        "t2v": False,
        "i2v": True,
        "default_width": 1280,
        "default_height": 720,
        "default_num_frames": 81,
        "default_steps": 40,
        "fps": 16,
    },
}


class Wan22MlxVideo(BaseTool):
    name = "wan22_mlx_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "wan-mlx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = (
        "Wan 2.2 MLX requires Apple Silicon (M1/M2/M3/M4/M5) + macOS 14+ + MLX 0.22+.\n"
        "Install:\n"
        "  pip install git+https://github.com/Blaizzy/mlx-video.git\n"
        "Download a Wan 2.2 model (example for TI2V-5B, ~12GB):\n"
        "  huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir ~/models/wan22-ti2v-5b\n"
        "Then call this tool with model_dir=~/models/wan22-ti2v-5b."
    )
    fallback = "wan_video"
    fallback_tools = ["wan_video", "ltx_video_local", "ltx_video_modal", "image_selector"]
    agent_skills = ["ltx2", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "model_selection"]
    supports = {
        "reference_image": True,
        "offline": True,
        "native_audio": False,
        "local_gpu": True,
        "apple_silicon_only": True,
    }
    best_for = [
        "Apple Silicon owners who want fastest local video gen",
        "tenant marketing ensembles that route through registry.get('wan22_mlx_video')",
        "image-to-video animation of brand stills produced by FLUX / local_diffusion",
    ]
    not_good_for = [
        "non-Apple-Silicon hardware (use wan_video or runway_video instead)",
        "video over 5-6 seconds (Wan 2.2 default is ~5s at 16fps × 81 frames)",
    ]
    provider_matrix = {
        key: {"tool": "wan22_mlx_video", **value, "mode": "local_mlx"}
        for key, value in WAN22_MLX_VARIANTS.items()
    }

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": sorted(WAN22_MLX_VARIANTS),
                "default": "wan2.2-ti2v-5b",
                "description": "Which Wan 2.2 variant. TI2V-5B is the M4-friendly default.",
            },
            "model_dir": {
                "type": "string",
                "description": "Local directory holding the downloaded model weights. If absent, the tool reports INSTALL_REQUIRED.",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Required for image_to_video / TI2V conditioning.",
            },
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "num_frames": {"type": "integer"},
            "num_inference_steps": {"type": "integer"},
            "seed": {"type": "integer"},
            "output_path": {
                "type": "string",
                "description": "Where to write the output mp4. Default: ./wan22_<timestamp>.mp4",
            },
            "extra_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Pass-through extra CLI args for mlx-video. Use for new flags ahead of this tool's schema being updated.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=32000, vram_mb=32000, disk_mb=15000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = [
        "prompt",
        "model_variant",
        "operation",
        "reference_image_path",
        "width",
        "height",
        "num_frames",
        "num_inference_steps",
        "seed",
    ]
    side_effects = ["writes video file to output_path", "loads model into unified memory"]
    user_visible_verification = [
        "Watch output mp4 — verify motion coherence, prompt adherence, no flicker at frame boundaries",
    ]

    # --------------------------------------------------------------- status

    def get_status(self) -> ToolStatus:
        # Apple Silicon gate
        if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
            return ToolStatus.UNAVAILABLE
        # Dynamic import — don't crash at module import time
        try:
            import mlx  # noqa: F401
            import mlx_video  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Empirical (mlx-video Wan 2.2):
        #  TI2V-5B / M5 Max: ~30s for 81 frames @ 832x480 / 30 steps
        #  T2V-14B / M5 Max: ~3 min for 81 frames @ 1280x720 / 40 steps
        variant = inputs.get("model_variant", "wan2.2-ti2v-5b")
        if variant.endswith("-14b"):
            return 180.0
        if variant.endswith("-5b"):
            return 30.0
        return 60.0

    # --------------------------------------------------------------- execute

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        status = self.get_status()
        if status != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Wan 2.2 MLX unavailable. " + self.install_instructions)

        variant_key = inputs.get("model_variant", "wan2.2-ti2v-5b")
        if variant_key not in WAN22_MLX_VARIANTS:
            return ToolResult(
                success=False,
                error=f"Unknown model_variant: {variant_key}. Available: {', '.join(sorted(WAN22_MLX_VARIANTS))}",
            )
        meta = WAN22_MLX_VARIANTS[variant_key]

        operation = inputs.get("operation", "text_to_video")
        if operation == "image_to_video" and not meta.get("i2v"):
            return ToolResult(success=False, error=f"{meta['name']} does not support image_to_video")
        if operation == "text_to_video" and not meta.get("t2v"):
            return ToolResult(success=False, error=f"{meta['name']} does not support text_to_video")

        prompt = inputs.get("prompt")
        if not prompt:
            return ToolResult(success=False, error="prompt is required")

        ref_image = inputs.get("reference_image_path")
        if operation == "image_to_video" and not ref_image:
            return ToolResult(success=False, error="reference_image_path is required for image_to_video")

        model_dir = inputs.get("model_dir")
        if not model_dir:
            return ToolResult(
                success=False,
                error=(
                    f"model_dir not provided and the tool can't auto-download in this version. "
                    f"Download with: huggingface-cli download {meta['hf_id']} --local-dir <DIR>"
                ),
            )
        model_dir_path = Path(model_dir).expanduser()
        if not model_dir_path.exists():
            return ToolResult(success=False, error=f"model_dir does not exist: {model_dir_path}")

        width = int(inputs.get("width", meta["default_width"]))
        height = int(inputs.get("height", meta["default_height"]))
        num_frames = int(inputs.get("num_frames", meta["default_num_frames"]))
        steps = int(inputs.get("num_inference_steps", meta["default_steps"]))
        seed = inputs.get("seed")
        extra_args = list(inputs.get("extra_args") or [])

        output_path = Path(
            inputs.get("output_path") or f"wan22_{variant_key}_{int(time.time())}.mp4"
        ).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build mlx-video CLI invocation. Module entrypoint:
        #   python -m mlx_video.wan_2.generate --model-dir ... --prompt ...
        cmd = [
            sys.executable, "-m", meta["module"],
            "--model-dir", str(model_dir_path),
            "--prompt", prompt,
            "--width", str(width),
            "--height", str(height),
            "--num-frames", str(num_frames),
            "--steps", str(steps),
            "--output-path", str(output_path),
        ]
        if seed is not None:
            cmd.extend(["--seed", str(int(seed))])
        if ref_image:
            cmd.extend(["--image", str(Path(ref_image).expanduser())])
        cmd.extend(extra_args)

        start = time.time()
        try:
            # mlx-video logs to stderr; capture both for the result
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            duration = round(time.time() - start, 2)

            if proc.returncode != 0 or not output_path.exists():
                return ToolResult(
                    success=False,
                    error=(
                        f"mlx-video exited {proc.returncode}: "
                        f"{(proc.stderr or proc.stdout or '<no output>')[-1500:]}"
                    ),
                    duration_seconds=duration,
                    model=meta["hf_id"],
                    seed=seed if isinstance(seed, int) else None,
                )

            return ToolResult(
                success=True,
                data={
                    "provider": "wan-mlx",
                    "model": meta["hf_id"],
                    "variant": variant_key,
                    "operation": operation,
                    "prompt": prompt,
                    "output_path": str(output_path),
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                    "steps": steps,
                    "fps": meta["fps"],
                    "duration_estimate_s": num_frames / meta["fps"],
                },
                artifacts=[str(output_path)],
                cost_usd=0.0,
                duration_seconds=duration,
                seed=seed if isinstance(seed, int) else None,
                model=meta["hf_id"],
            )
        except FileNotFoundError as exc:
            return ToolResult(
                success=False,
                error=f"Python executable or mlx-video module not found: {exc}. " + self.install_instructions,
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"Wan 2.2 MLX generation failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )
