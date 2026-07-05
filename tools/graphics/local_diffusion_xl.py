"""Modern commercial-safe local image generation (SDXL / FLUX-schnell / SD3.5).

A NEW alternative alongside `local_diffusion` (which stays on SD-2.1) — it does
not replace it. Uses diffusers' AutoPipelineForText2Image so one tool loads
whichever modern model you point it at:

    stabilityai/stable-diffusion-xl-base-1.0   default — commercial-safe, ~8GB VRAM
    black-forest-labs/FLUX.1-schnell           Apache 2.0, highest quality, ~12GB+
    stabilityai/stable-diffusion-3.5-large     commercial-safe, ~18GB

LICENSE NOTE: FLUX.1-dev / FLUX.2-dev are NON-COMMERCIAL. For commercial work use
the models above (SDXL, FLUX.1-schnell, SD3.5, Qwen-Image) — never FLUX-dev.

Free (no API cost). Reports UNAVAILABLE until diffusers is installed, so it never
disturbs existing flows and auto-joins the image menu via image_selector.

FLUX and SDXL take different call arguments (FLUX has no negative_prompt and wants
guidance≈0 with ~4 steps); that per-model difference is the one calibration knob,
isolated + `ponytail:`-marked in `_build_call_kwargs`. Everything else is shared.
"""

from __future__ import annotations

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

_DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

# Commercial-safe defaults surfaced to the agent. FLUX.1-dev deliberately excluded.
COMMERCIAL_SAFE_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-3.5-large",
    "Qwen/Qwen-Image",
]


def _is_flux_schnell(model_id: str) -> bool:
    m = (model_id or "").lower()
    return "flux" in m and "schnell" in m


class LocalDiffusionXL(BaseTool):
    name = "local_diffusion_xl"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "local_diffusion_xl"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked dynamically
    install_instructions = (
        "Install diffusers for modern local image models:\n"
        "  pip install 'diffusers>=0.30' transformers accelerate torch safetensors\n"
        "First run downloads the model weights (SDXL ~7GB, FLUX-schnell ~24GB)."
    )
    agent_skills = ["flux-best-practices", "bfl-api"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": True,  # SDXL/SD3.5 (ignored for FLUX-schnell)
        "seed": True,
        "offline": True,
        "custom_size": True,
    }
    best_for = [
        "high-quality free local image generation",
        "commercial-safe open image models (SDXL, FLUX-schnell, SD3.5)",
        "bulk and draft image generation without API cost",
        "offline/air-gapped generation",
    ]
    not_good_for = [
        "CPU-only machines (SDXL/FLUX are impractically slow without a GPU)",
        "FLUX.1-dev (non-commercial license — use FLUX.1-schnell or SDXL instead)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {
                "type": "string",
                "default": "",
                "description": "Used by SDXL/SD3.5; ignored for FLUX-schnell (no negative prompt).",
            },
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": (
                    "Commercial-safe: stable-diffusion-xl-base-1.0 (default), FLUX.1-schnell, "
                    "stable-diffusion-3.5-large, Qwen-Image. Do NOT use FLUX.1-dev/FLUX.2-dev "
                    "(non-commercial)."
                ),
            },
            "seed": {"type": "integer"},
            "num_inference_steps": {
                "type": "integer",
                "description": "Default adapts to model: ~30 for SDXL, ~4 for FLUX-schnell.",
            },
            "guidance_scale": {
                "type": "number",
                "description": "Default adapts to model: ~7.0 for SDXL, 0.0 for FLUX-schnell.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=16000, vram_mb=12000, disk_mb=25000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "width", "height", "seed", "model"]
    side_effects = ["writes image file to output_path", "may download model weights on first run"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def get_status(self) -> ToolStatus:
        try:
            import diffusers  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model_id = inputs.get("model", _DEFAULT_MODEL)
        return 6.0 if _is_flux_schnell(model_id) else 25.0

    @staticmethod
    def _build_call_kwargs(model_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build model-appropriate pipeline call kwargs (no generator — added in execute).

        ponytail: FLUX-schnell vs SDXL is the one real per-model difference —
        FLUX has no negative_prompt and is distilled (guidance≈0, ~4 steps). This
        is the knob to tune; the rest of the flow is model-agnostic. Pure function,
        so it's unit-tested without loading any weights.
        """
        flux = _is_flux_schnell(model_id)
        kwargs: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "width": inputs.get("width", 1024),
            "height": inputs.get("height", 1024),
            "num_inference_steps": inputs.get("num_inference_steps", 4 if flux else 30),
            "guidance_scale": inputs.get("guidance_scale", 0.0 if flux else 7.0),
        }
        if not flux:
            kwargs["negative_prompt"] = inputs.get("negative_prompt", "")
        return kwargs

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="diffusers not installed. " + self.install_instructions,
            )

        import torch
        from diffusers import AutoPipelineForText2Image

        start = time.time()
        model_id = inputs.get("model", _DEFAULT_MODEL)
        seed = inputs.get("seed")

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            pipe = AutoPipelineForText2Image.from_pretrained(model_id, torch_dtype=dtype)
            pipe = pipe.to(device)

            call_kwargs = self._build_call_kwargs(model_id, inputs)
            if seed is not None:
                call_kwargs["generator"] = torch.Generator(device=device).manual_seed(seed)

            image = pipe(**call_kwargs).images[0]

            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output_path))

        except Exception as e:  # noqa: BLE001 - surface generation failure to the agent
            return ToolResult(success=False, error=f"Local diffusion (XL) generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model_id,
                "prompt": inputs["prompt"],
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_id,
        )
