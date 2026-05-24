"""Local Stable Diffusion image generation via diffusers."""

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


class LocalDiffusion(BaseTool):
    name = "local_diffusion"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "local_diffusion"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked dynamically
    install_instructions = (
        "Install diffusers for local Stable Diffusion:\n"
        "  pip install diffusers transformers accelerate torch"
    )
    agent_skills = []

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": True,
        "seed": True,
        "offline": True,
        "custom_size": True,
    }
    best_for = [
        "offline/air-gapped generation",
        "free image generation (no API cost)",
        "privacy-sensitive workflows",
    ]
    not_good_for = [
        "CPU-only machines (very slow)",
        "highest quality output (API models are better)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": ""},
            "width": {"type": "integer", "default": 512},
            "height": {"type": "integer", "default": 512},
            "model": {
                "type": "string",
                "default": "stabilityai/stable-diffusion-2-1-base",
            },
            "seed": {"type": "integer"},
            "num_inference_steps": {"type": "integer", "default": 30},
            "guidance_scale": {"type": "number", "default": 7.5},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=4000, disk_mb=5000, network_required=False
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
        return 30.0  # ~30s on a mid-range GPU

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="diffusers not installed. " + self.install_instructions,
            )

        import torch
        from diffusers import StableDiffusionPipeline

        start = time.time()
        prompt = inputs["prompt"]
        negative = inputs.get("negative_prompt", "")
        width = inputs.get("width", 512)
        height = inputs.get("height", 512)
        seed = inputs.get("seed")
        model_id = inputs.get("model", "stabilityai/stable-diffusion-2-1-base")
        steps = inputs.get("num_inference_steps", 30)
        guidance = inputs.get("guidance_scale", 7.5)

        try:
            # Device autoselect: CUDA → MPS (Apple Silicon) → CPU
            # MPS support added 2026-05-23 — diffusers on M5 Max 128GB / M4 32GB
            # runs SD2.1-base at ~1-2 it/s with fp16; CPU fallback is ~5x slower.
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32

            pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
            pipe = pipe.to(device)

            # MPS-specific: enable attention slicing to fit larger resolutions
            # in unified memory; harmless on CUDA/CPU but skip there.
            if device == "mps":
                pipe.enable_attention_slicing()

            # MPS doesn't support torch.Generator(device='mps'); use CPU generator
            # and the pipeline handles device transfer correctly.
            generator = None
            if seed is not None:
                gen_device = "cpu" if device == "mps" else device
                generator = torch.Generator(device=gen_device).manual_seed(seed)

            image = pipe(
                prompt,
                negative_prompt=negative,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=generator,
            ).images[0]

            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output_path))

        except Exception as e:
            return ToolResult(success=False, error=f"Local diffusion generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "local_diffusion",
                "model": model_id,
                "prompt": prompt,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_id,
        )
