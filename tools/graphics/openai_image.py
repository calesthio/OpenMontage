"""OpenAI GPT Image generation (gpt-image-2)."""

from __future__ import annotations

import base64
import os
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


class OpenAIImage(BaseTool):
    name = "openai_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "openai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically
    install_instructions = (
        "Set OPENAI_API_KEY to your OpenAI API key.\n"
        "  pip install openai"
    )
    agent_skills = ["flux-best-practices"]  # general image gen knowledge

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "complex_instructions": True,
        "text_in_image": True,
        "multiple_outputs": True,
    }
    best_for = [
        "complex multi-element compositions",
        "images with text/labels",
        "following detailed instructions accurately",
    ]
    not_good_for = ["offline generation", "budget-constrained projects at high quality"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["gpt-image-2"],
                "default": "gpt-image-2",
            },
            "size": {
                "type": "string",
                "enum": ["1024x1024", "1536x1024", "1024x1536", "auto"],
                "default": "1024x1024",
            },
            "quality": {
                "type": "string",
                "enum": ["low", "medium", "high", "auto"],
                "default": "high",
            },
            "output_format": {
                "type": "string",
                "enum": ["png", "jpeg", "webp"],
                "default": "png",
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "size", "quality", "model"]
    side_effects = ["writes image file to output_path", "calls OpenAI API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    @staticmethod
    def _output_paths(output_path: str | None, count: int, extension: str) -> list[Path]:
        """Derive one output path per generated image.

        With a single image, honor the requested path as-is. With several,
        suffix each with `_1`, `_2`, … so no image overwrites another.
        """
        ext = extension if extension.startswith(".") else f".{extension}"
        if not output_path:
            return [Path(f"generated_image_{idx + 1}{ext}") for idx in range(count)]

        path = Path(output_path)
        suffix = path.suffix or ext
        if count == 1:
            return [path if path.suffix else path.with_suffix(suffix)]

        base = path.with_suffix("") if path.suffix else path
        return [base.parent / f"{base.name}_{idx + 1}{suffix}" for idx in range(count)]

    def get_status(self) -> ToolStatus:
        if os.environ.get("OPENAI_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # gpt-image-2 per-image pricing at 1024x1024 (non-square sizes run
        # slightly cheaper): https://developers.openai.com/api/docs/guides/image-generation
        quality = inputs.get("quality", "high")
        n = inputs.get("n", 1)
        cost_map = {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053}
        return cost_map.get(quality, 0.053) * n

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("OPENAI_API_KEY"):
            return ToolResult(
                success=False,
                error="OPENAI_API_KEY not set. " + self.install_instructions,
            )

        from openai import OpenAI

        start = time.time()
        client = OpenAI()
        model = inputs.get("model", "gpt-image-2")
        prompt = inputs["prompt"]
        size = inputs.get("size", "1024x1024")
        n = inputs.get("n", 1)

        try:
            quality = inputs.get("quality", "high")
            output_format = inputs.get("output_format", "png")
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                output_format=output_format,
                n=n,
            )

            items = response.data or []
            if not items:
                return ToolResult(success=False, error="OpenAI returned no image outputs")

            ext = output_format
            output_paths = self._output_paths(inputs.get("output_path"), len(items), ext)
            outputs: list[str] = []
            for item, out_path in zip(items, output_paths):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(base64.b64decode(item.b64_json))
                outputs.append(str(out_path))

        except Exception as e:
            return ToolResult(success=False, error=f"OpenAI image generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "openai",
                "model": model,
                "prompt": prompt,
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
            },
            artifacts=outputs,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
