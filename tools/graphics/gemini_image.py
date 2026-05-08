"""Google Gemini image generation (gemini-2.5-flash-image / gemini-3-pro-image-preview).

Ported from OpenSwarm 2026-05-08. Adds a third Gemini image provider to the
OpenMontage image-generation family alongside flux_image, openai_image,
recraft_image, grok_image, and local_diffusion.

Default model: `gemini-2.5-flash-image` (fast, iteration-friendly).
Precision tier: `gemini-3-pro-image-preview` (text-heavy, complex compositions).
"""

from __future__ import annotations

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


class GeminiImage(BaseTool):
    name = "gemini_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically (google-genai)
    install_instructions = (
        "Set GOOGLE_API_KEY to your Google AI Studio key.\n"
        "  pip install google-genai"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = [
        "generate_image",
        "generate_illustration",
        "text_to_image",
        "high_precision_text_rendering",
    ]
    supports = {
        "complex_instructions": True,
        "text_in_image": True,
        "multiple_outputs": True,
        "broad_aspect_ratios": True,
    }
    best_for = [
        "fast iterative image workflows (gemini-2.5-flash-image)",
        "text-heavy precision images (gemini-3-pro-image-preview)",
        "complex product compositions with strict constraints",
        "high-fidelity brand assets where prompt adherence matters",
    ]
    not_good_for = ["offline/private generation", "true SVG/vector output"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": [
                    "gemini-2.5-flash-image",
                    "gemini-3-pro-image-preview",
                ],
                "default": "gemini-2.5-flash-image",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": [
                    "1:1", "2:3", "3:2", "3:4", "4:3",
                    "4:5", "5:4", "9:16", "16:9", "21:9",
                ],
                "default": "1:1",
            },
            "num_variants": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 4,
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "aspect_ratio", "model"]
    side_effects = [
        "writes image file to output_path",
        "calls Google Gemini API",
    ]
    user_visible_verification = [
        "Inspect generated image for relevance, prompt adherence, and text accuracy"
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("GOOGLE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Gemini 2.5 Flash Image: ~$0.039/image (cheap, fast)
        # Gemini 3 Pro Image Preview: ~$0.10/image (precision tier)
        # Both per output, scales with num_variants.
        model = inputs.get("model", "gemini-2.5-flash-image")
        n = inputs.get("num_variants", 1)
        per_image = 0.10 if model == "gemini-3-pro-image-preview" else 0.039
        return per_image * n

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("GOOGLE_API_KEY"):
            return ToolResult(
                success=False,
                error="GOOGLE_API_KEY not set. " + self.install_instructions,
            )

        try:
            from google import genai
            from google.genai.types import GenerateContentConfig, ImageConfig
        except ImportError:
            return ToolResult(
                success=False,
                error=(
                    "google-genai not installed. Run: pip install google-genai"
                ),
            )

        start = time.time()
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        model = inputs.get("model", "gemini-2.5-flash-image")
        prompt = inputs["prompt"]
        aspect_ratio = inputs.get("aspect_ratio", "1:1")
        n = inputs.get("num_variants", 1)
        output_path_template = inputs.get("output_path", "generated_image.png")

        artifacts: list[str] = []
        try:
            for idx in range(n):
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=GenerateContentConfig(
                        image_config=ImageConfig(aspect_ratio=aspect_ratio),
                    ),
                )

                image_bytes = self._extract_image_bytes(response)
                if image_bytes is None:
                    continue

                if n > 1:
                    base = Path(output_path_template)
                    out_path = base.with_name(f"{base.stem}_v{idx + 1}{base.suffix}")
                else:
                    out_path = Path(output_path_template)

                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes)
                artifacts.append(str(out_path))

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Gemini image generation failed: {exc}",
            )

        if not artifacts:
            return ToolResult(
                success=False,
                error="Gemini returned no image data (safety filter or empty response).",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "google",
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "outputs": artifacts,
            },
            artifacts=artifacts,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    @staticmethod
    def _extract_image_bytes(response: Any) -> bytes | None:
        """Pull raw image bytes out of a Gemini generate_content response.

        Gemini returns multimodal Parts; the image is in `inline_data.data` as
        bytes, content type `image/png` or `image/jpeg`.
        """
        try:
            for candidate in getattr(response, "candidates", []) or []:
                for part in getattr(candidate.content, "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        return inline.data
        except Exception:
            return None
        return None
