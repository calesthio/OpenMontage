"""Nano Banana 2 image generation via KIE.AI.

Google Gemini 2.5 Flash Image — multimodal, accepts up to 14 reference images
(Pseudo-Soul ID pattern for character consistency across shots).

Best for: product photography, character master refs, multi-ref consistency.
Reference grammar: ~/.claude/skills/model-cheatsheet.md → Nano Banana section.

User added 2026-05-07 alongside Qwen3 TTS.
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


class KIENanoBanana(BaseTool):
    name = "kie_nano_banana"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "kie:google_nano_banana"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set KIE_AI_API_KEY (https://kie.ai)."
    agent_skills = ["ai-video-gen", "flux-best-practices"]

    capabilities = ["text_to_image", "multi_reference_to_image"]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        "multi_reference": True,    # up to 14 ref images (Pseudo-Soul ID)
        "character_consistency": True,
    }
    best_for = [
        "character master ref + 9-angle production",
        "product hero photography (clean glass, soft window light)",
        "scene continuity across multi-shot videos (re-use same hero ref)",
    ]
    not_good_for = [
        "logos / packaging text rendering — use kie_gpt_image instead",
        "pure typography or graphic design output",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["google/nano-banana", "nano-banana-2"],
                "default": "nano-banana-2",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "9:16", "16:9", "3:4", "4:3"],
                "default": "1:1",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 14 reference URLs/local-paths. Local paths are auto-uploaded.",
                "maxItems": 14,
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "output_path": {"type": "string", "default": "nano_banana_output.png"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "5xx"])
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "reference_image_urls"]
    side_effects = ["calls KIE.AI", "writes image file to output_path"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.is_configured() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.04  # ~$0.04 per image (KIE catalog)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="KIE_AI_API_KEY not set. " + self.install_instructions)

        start = time.time()
        try:
            output_path = Path(inputs.get("output_path", "nano_banana_output.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Resolve any local reference images
            ref_urls = []
            for ref in inputs.get("reference_image_urls", []) or []:
                ref_urls.append(kie_client.maybe_upload(ref))

            payload: dict[str, Any] = {
                "prompt": inputs["prompt"],
                "aspect_ratio": inputs.get("aspect_ratio", "1:1"),
                "n": int(inputs.get("n", 1)),
            }
            if ref_urls:
                payload["reference_image_urls"] = ref_urls

            model = inputs.get("model", "nano-banana-2")
            record = kie_client.run_unified(model, payload, max_wait_s=300)
            urls = kie_client.extract_result_urls(record)
            if not urls:
                return ToolResult(success=False, error=f"Nano Banana returned no result URLs: {record}")

            kie_client.download_to(urls[0], output_path)

            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "prompt_length": len(inputs["prompt"]),
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
            return ToolResult(success=False, error=f"KIE Nano Banana: {exc}", duration_seconds=round(time.time() - start, 2))
        except Exception as exc:
            return ToolResult(success=False, error=f"KIE Nano Banana unexpected: {exc}", duration_seconds=round(time.time() - start, 2))
