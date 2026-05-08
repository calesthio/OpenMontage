"""GPT Image 2 (and 4o-image) via KIE.AI.

Best for: logo wordmarks, packaging mockups with readable label text,
typography-heavy product shots — OpenAI image models have the strongest
text-rendering in the current commercial fleet.

Reference: ~/.claude/projects/-Users-abalioglu/memory/reference_kieai_models.md
- Pattern A: `openai/gpt-image-2` via /jobs/createTask
- Pattern B: `4o Image` via dedicated /gpt4o-image/generate (fallback)

User added 2026-05-07 alongside Nano Banana 2 + Qwen3 TTS.
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
from lib import kie_client


class KIEGPTImage(BaseTool):
    name = "kie_gpt_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "kie:openai_gpt_image"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set KIE_AI_API_KEY (https://kie.ai)."
    agent_skills = ["flux-best-practices"]

    capabilities = ["text_to_image", "text_in_image", "image_to_image"]
    supports = {
        "text_to_image": True,
        "text_in_image": True,         # the moat — readable typography
        "image_to_image": True,
        "high_resolution": True,       # 1024×1792 / 1792×1024
    }
    best_for = [
        "logo wordmarks, brand marks with readable text",
        "packaging mockups with label text (bottle, box, tube)",
        "infographic / data visualization with embedded labels",
        "any product shot where text MUST be legible",
    ]
    not_good_for = [
        "best price-per-image (Nano Banana is cheaper for plain product/character)",
        "extreme photorealism (Imagen 4 / Flux often score higher on pure photoreal)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "1-20,000 characters"},
            "model": {
                "type": "string",
                "enum": [
                    "gpt-image-2-text-to-image",
                    "gpt-image-2-image-to-image",
                ],
                "default": "gpt-image-2-text-to-image",
                "description": (
                    "text-to-image: prompt only. "
                    "image-to-image: prompt + input_urls (max 16). "
                    "If reference_image_urls is provided, model auto-switches to image-to-image."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "1:1", "9:16", "16:9", "4:3", "3:4"],
                "default": "auto",
            },
            "resolution": {
                "type": "string",
                "enum": ["1K", "2K", "4K"],
                "default": "1K",
                "description": "1:1 cannot use 4K. auto aspect_ratio limited to 1K.",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 16,
                "description": "Reference image URLs/paths (local auto-uploaded). Triggers image-to-image mode.",
            },
            "output_path": {"type": "string", "default": "gpt_image_output.png"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "5xx"])
    idempotency_key_fields = ["prompt", "model", "size", "quality", "reference_image_urls"]
    side_effects = ["calls KIE.AI", "writes image file to output_path"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.is_configured() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # KIE pricing scales with resolution: ~$0.04 (1K), ~$0.10 (2K), ~$0.20 (4K)
        # Adjust per official KIE catalog if these drift.
        resolution = inputs.get("resolution", "1K")
        return {"1K": 0.04, "2K": 0.10, "4K": 0.20}.get(resolution, 0.04)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="KIE_AI_API_KEY not set. " + self.install_instructions)

        start = time.time()
        try:
            output_path = Path(inputs.get("output_path", "gpt_image_output.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Resolve any local reference images
            ref_urls = []
            for ref in inputs.get("reference_image_urls", []) or []:
                ref_urls.append(kie_client.maybe_upload(ref))

            # Auto-pick model based on whether refs are provided
            model = inputs.get("model")
            if not model:
                model = "gpt-image-2-image-to-image" if ref_urls else "gpt-image-2-text-to-image"
            elif ref_urls and model == "gpt-image-2-text-to-image":
                # User asked for text-to-image but provided refs → switch
                model = "gpt-image-2-image-to-image"

            payload: dict[str, Any] = {
                "prompt": inputs["prompt"],
                "aspect_ratio": inputs.get("aspect_ratio", "auto"),
                "resolution": inputs.get("resolution", "1K"),
            }

            # Constraint: 1:1 cannot use 4K
            if payload["aspect_ratio"] == "1:1" and payload["resolution"] == "4K":
                payload["resolution"] = "2K"

            # Constraint: auto aspect_ratio limited to 1K
            if payload["aspect_ratio"] == "auto" and payload["resolution"] != "1K":
                payload["resolution"] = "1K"

            # image-to-image needs input_urls
            if model == "gpt-image-2-image-to-image":
                if not ref_urls:
                    return ToolResult(
                        success=False,
                        error="gpt-image-2-image-to-image requires reference_image_urls (input_urls)",
                    )
                payload["input_urls"] = ref_urls[:16]  # max 16 per spec

            record = kie_client.run_unified(model, payload, max_wait_s=300)
            urls = kie_client.extract_result_urls(record)

            if not urls:
                return ToolResult(
                    success=False,
                    error=f"GPT Image returned no result URLs (model={model}): {record}",
                )

            kie_client.download_to(urls[0], output_path)

            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "prompt_length": len(inputs["prompt"]),
                    "aspect_ratio": payload["aspect_ratio"],
                    "resolution": payload["resolution"],
                    "output": str(output_path),
                    "all_urls": urls,
                    "format": "png",
                },
                artifacts=[str(output_path)],
                model=model,
                cost_usd=self.estimate_cost(inputs),
                duration_seconds=round(time.time() - start, 2),
            )
        except kie_client.KIEError as exc:
            return ToolResult(success=False, error=f"KIE GPT Image: {exc}", duration_seconds=round(time.time() - start, 2))
        except Exception as exc:
            return ToolResult(success=False, error=f"KIE GPT Image unexpected: {exc}", duration_seconds=round(time.time() - start, 2))
