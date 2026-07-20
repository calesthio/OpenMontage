"""Image generation tool for diagrams, overlays, and illustrations.

.. deprecated::
    Use ``image_selector`` instead. This monolithic tool has been replaced by
    the selector/provider pattern: ``image_selector`` routes to per-provider
    tools (flux_image, openai_image, recraft_image, local_diffusion,
    pexels_image, pixabay_image). This file is kept for backwards
    compatibility and will be removed in a future release.

Supports cloud API providers (FLUX via fal.ai/Replicate, OpenAI GPT Image)
and local Stable Diffusion via diffusers. Reports unavailable with
install instructions when no provider is configured.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

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


class ImageGen(BaseTool):
    name = "image_gen"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "image_generation"
    provider = "multi"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.HYBRID  # API (GPT Image/FLUX) or local (diffusers)

    dependencies = []  # checked dynamically based on provider
    install_instructions = (
        "Set one of these environment variables:\n"
        "  OPENAI_API_KEY — for GPT Image 2\n"
        "  FAL_KEY — for FLUX via fal.ai\n"
        "Or install diffusers for local generation:\n"
        "  pip install diffusers transformers accelerate torch"
    )
    agent_skills = ["flux-best-practices", "bfl-api"]

    capabilities = [
        "generate_image",
        "generate_diagram_overlay",
        "generate_illustration",
    ]
    best_for = [
        "DEPRECATED — prefer image_selector which routes to per-provider tools "
        "(flux_image, openai_image, recraft_image, grok_image, local_diffusion, "
        "pexels_image, pixabay_image).",
        "Kept only for backwards compatibility. New code should not call this.",
    ]
    not_good_for = [
        "New production code — use image_selector instead.",
        "Picking a specific provider (use the per-provider tool directly).",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": ""},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "provider": {
                "type": "string",
                "enum": ["openai", "flux", "local"],
                "description": "Auto-detected if not specified",
            },
            "model": {"type": "string"},
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "seed"]
    side_effects = ["writes image file to output_path", "calls external API"]
    user_visible_verification = [
        "Inspect generated image for relevance and quality",
    ]

    def get_status(self) -> ToolStatus:
        provider = self._detect_provider()
        if provider:
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _detect_provider(self) -> Optional[str]:
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY"):
            return "flux"
        try:
            import diffusers  # noqa: F401
            return "local"
        except ImportError:
            pass
        return None

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        provider = inputs.get("provider") or self._detect_provider()
        if provider == "openai":
            return 0.053  # gpt-image-2 medium at 1024x1024 (call uses auto quality)
        if provider == "flux":
            return 0.03
        return 0.0  # local

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        provider = inputs.get("provider") or self._detect_provider()
        if not provider:
            return ToolResult(
                success=False,
                error="No image generation provider available. " + self.install_instructions,
            )

        start = time.time()

        try:
            if provider == "openai":
                result = self._generate_openai(inputs)
            elif provider == "flux":
                result = self._generate_flux(inputs)
            elif provider == "local":
                result = self._generate_local(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown provider: {provider}")
        except Exception as e:
            return ToolResult(success=False, error=f"Generation failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate_openai(self, inputs: dict[str, Any]) -> ToolResult:
        from openai import OpenAI
        import base64

        client = OpenAI()
        prompt = inputs["prompt"]
        size = f"{inputs.get('width', 1024)}x{inputs.get('height', 1024)}"
        model = inputs.get("model", "gpt-image-2")

        # GPT image models don't accept response_format; they always return b64
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            n=1,
        )

        image_data = base64.b64decode(response.data[0].b64_json)
        output_path = Path(inputs.get("output_path", "generated_image.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)

        return ToolResult(
            success=True,
            data={
                "provider": "openai",
                "model": model,
                "prompt": prompt,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )

    def _generate_flux(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = os.environ.get("FAL_KEY") or os.environ["FAL_AI_API_KEY"]
        prompt = inputs["prompt"]
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)
        seed = inputs.get("seed")

        payload = {
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
        }
        if seed is not None:
            payload["seed"] = seed

        response = requests.post(
            "https://fal.run/fal-ai/flux/dev",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        image_url = data["images"][0]["url"]
        image_response = requests.get(image_url, timeout=60)
        image_response.raise_for_status()

        output_path = Path(inputs.get("output_path", "generated_image.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_response.content)

        return ToolResult(
            success=True,
            data={
                "provider": "flux",
                "prompt": prompt,
                "output": str(output_path),
                "seed": data.get("seed"),
            },
            artifacts=[str(output_path)],
            seed=data.get("seed"),
            model="flux-dev",
        )

    def _generate_local(self, inputs: dict[str, Any]) -> ToolResult:
        import torch
        from diffusers import StableDiffusionPipeline

        prompt = inputs["prompt"]
        negative = inputs.get("negative_prompt", "")
        width = inputs.get("width", 512)
        height = inputs.get("height", 512)
        seed = inputs.get("seed")
        model_id = inputs.get("model", "stabilityai/stable-diffusion-2-1-base")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
        pipe = pipe.to(device)

        generator = None
        if seed is not None:
            generator = torch.Generator(device=device).manual_seed(seed)

        image = pipe(
            prompt,
            negative_prompt=negative,
            width=width,
            height=height,
            generator=generator,
        ).images[0]

        output_path = Path(inputs.get("output_path", "generated_image.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path))

        return ToolResult(
            success=True,
            data={
                "provider": "local",
                "model": model_id,
                "prompt": prompt,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            seed=seed,
            model=model_id,
        )
