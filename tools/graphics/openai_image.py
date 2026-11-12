"""OpenAI GPT Image generation (gpt-image-2)."""

from __future__ import annotations

import base64
from contextlib import ExitStack
import os
import time
from pathlib import Path
from typing import Any

from tools.provider_pricing import PriceQuoteRequired

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
        "Set OPENAI_API_KEY to your OpenAI API key.\n  pip install openai"
    )
    agent_skills = ["provider-model-refresh"]  # general image gen knowledge

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "complex_instructions": True,
        "text_in_image": True,
        "multiple_outputs": True,
        "image_edit": True,
        "mask": True,
        "transparent_background": True,
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
                "enum": [
                    "gpt-image-2",
                    "gpt-image-2.5-flare",
                    "gpt-image-2.5-sunburst",
                ],
                "default": "gpt-image-2",
            },
            "size": {
                "type": "string",
                "enum": ["1024x1024", "1536x1024", "1024x1536", "auto"],
                "default": "1024x1024",
            },
            "quality": {
                "type": "string",
                "enum": ["low", "medium", "high", "xhigh", "max", "auto"],
                "default": "high",
            },
            "output_format": {
                "type": "string",
                "enum": ["png", "jpeg", "webp"],
                "default": "png",
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "output_path": {"type": "string"},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"]},
            "image_path": {"type": "string"},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 16,
            },
            "mask_path": {"type": "string"},
            "background": {"type": "string", "enum": ["auto", "opaque", "transparent"]},
            "output_compression": {"type": "integer", "minimum": 0, "maximum": 100},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "size", "quality", "model"] + [
        "generation_mode",
        "image_path",
        "image_paths",
        "mask_path",
        "background",
        "output_format",
        "output_compression",
        "n",
    ]
    side_effects = ["writes image file to output_path", "calls OpenAI API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    @staticmethod
    def _output_paths(
        output_path: str | None, count: int, extension: str
    ) -> list[Path]:
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
        if inputs.get("model", "gpt-image-2") != "gpt-image-2":
            raise PriceQuoteRequired(
                "GPT Image 2.5 uses token pricing; obtain a quote for the chosen size and quality"
            )
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
        client = OpenAI(max_retries=0)
        model = inputs.get("model", "gpt-image-2")
        prompt = inputs["prompt"]
        size = inputs.get("size", "1024x1024")
        n = inputs.get("n", 1)

        try:
            quality = inputs.get("quality", "high")
            output_format = inputs.get("output_format", "png")
            from jsonschema import validate

            validate(inputs, self.input_schema)
            if (
                inputs.get("image_url")
                or inputs.get("image_urls")
                or inputs.get("mask_url")
            ):
                raise ValueError(
                    "Direct OpenAI edits require local image_path/image_paths and mask_path"
                )
            if model == "gpt-image-2" and quality in {"xhigh", "max"}:
                raise ValueError("xhigh/max quality requires GPT Image 2.5")
            paths = list(inputs.get("image_paths") or [])
            if inputs.get("image_path"):
                paths.insert(0, inputs["image_path"])
            mode = inputs.get("generation_mode", "edit" if paths else "generate")
            if (mode == "edit") != bool(paths):
                raise ValueError(
                    "Edit requires source images; generate cannot accept source images"
                )
            if len(paths) > 16 or (inputs.get("mask_path") and not paths):
                raise ValueError(
                    "At most 16 source images; a mask requires a source image"
                )
            if inputs.get("background") == "transparent" and output_format == "jpeg":
                raise ValueError("Transparent output requires PNG or WebP")
            params = dict(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                output_format=output_format,
                n=n,
            )
            for key in ("background", "output_compression"):
                if key in inputs:
                    params[key] = inputs[key]
            with ExitStack() as stack:
                if paths:
                    params["image"] = [
                        stack.enter_context(open(path, "rb")) for path in paths
                    ]
                    if inputs.get("mask_path"):
                        params["mask"] = stack.enter_context(
                            open(inputs["mask_path"], "rb")
                        )
                    response = client.images.edit(**params)
                else:
                    response = client.images.generate(**params)

            items = response.data or []
            if not items:
                return ToolResult(
                    success=False, error="OpenAI returned no image outputs"
                )

            ext = output_format
            output_paths = self._output_paths(
                inputs.get("output_path"), len(items), ext
            )
            outputs: list[str] = []
            for item, out_path in zip(items, output_paths):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(base64.b64decode(item.b64_json))
                outputs.append(str(out_path))

        except Exception as e:
            return ToolResult(
                success=False, error=f"OpenAI image generation failed: {e}"
            )

        return ToolResult(
            success=True,
            data={
                "provider": "openai",
                "model": model,
                "prompt": prompt,
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
                "operation": mode,
                "usage": response.usage.model_dump()
                if getattr(response, "usage", None)
                and hasattr(response.usage, "model_dump")
                else None,
                "cost_status": "estimated"
                if model == "gpt-image-2"
                else "usage_reported_unpriced",
            },
            artifacts=outputs,
            cost_usd=self.estimate_cost(inputs) if model == "gpt-image-2" else None,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
