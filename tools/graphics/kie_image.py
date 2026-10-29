"""KIE AI image generation / editing gateway.

KIE AI (https://kie.ai) is a multi-model aggregator: one API key and one
unified async task contract in front of dozens of image models (Nano Banana,
Seedream, GPT Image, FLUX, Ideogram, ...). This tool defaults to Google Nano
Banana (and its Edit variant) -- cheap, fast, well documented -- and exposes
a generic `extra_input` passthrough plus `kie_model` override so any other
Market image model can be called without a code change. Check
https://kie.ai/market for the exact `input` fields of a given model before
switching `kie_model`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import kie_client
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
from tools.provider_pricing import PriceQuoteRequired

_DEFAULT_MODEL = "google/nano-banana"
_DEFAULT_EDIT_MODEL = "google/nano-banana-edit"


class KieImage(BaseTool):
    name = "kie_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "kie"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KIE_API_KEY"]
    install_instructions = kie_client.INSTALL_INSTRUCTIONS
    agent_skills = ["flux-best-practices"]

    capabilities = ["text_to_image", "image_edit"]
    supports = {
        "text_to_image": True,
        "image_edit": True,
        "multiple_reference_images": True,
        "aspect_ratio": True,
        "multi_model_gateway": True,
    }
    best_for = [
        "Nano Banana text-to-image and multi-image editing through a single KIE AI key",
        "Trying other KIE Market image models (Seedream, GPT Image, FLUX, Ideogram) via kie_model + extra_input",
    ]
    not_good_for = ["offline generation", "guaranteed pricing without checking kie.ai/pricing"]
    fallback_tools = ["google_imagen", "flux_image", "openai_image"]
    quality_score = 0.8

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "kie_model": {
                "type": "string",
                "description": "KIE AI Market model id for createTask's top-level 'model' field. "
                "Defaults to google/nano-banana, or google/nano-banana-edit when image_urls is set.",
            },
            "image_url": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"],
                "default": "1:1",
            },
            "output_format": {"type": "string", "enum": ["png", "jpeg"], "default": "png"},
            "extra_input": {
                "type": "object",
                "description": "Raw fields merged into the Market 'input' object -- use for non-default kie_model schemas.",
            },
            "callback_url": {"type": "string"},
            "poll_interval": {"type": "number", "default": 2.0},
            "poll_timeout": {"type": "number", "default": 300.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=200, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "kie_model", "aspect_ratio"]
    side_effects = ["writes image file to output_path", "calls KIE AI API"]
    user_visible_verification = ["Inspect the generated image for prompt fidelity"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "KIE AI image pricing varies by model -- see https://kie.ai/pricing"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 25.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = kie_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="KIE_API_KEY not set. " + self.install_instructions)

        images = [str(value) for value in (inputs.get("image_urls") or [])]
        if inputs.get("image_url"):
            images.insert(0, str(inputs["image_url"]))
        is_edit = bool(images)

        kie_model = str(inputs.get("kie_model") or (_DEFAULT_EDIT_MODEL if is_edit else _DEFAULT_MODEL))

        started = time.time()
        try:
            market_input: dict[str, Any] = {
                "prompt": inputs.get("prompt", ""),
                "aspect_ratio": inputs.get("aspect_ratio", "1:1"),
                "output_format": inputs.get("output_format", "png"),
            }
            if is_edit:
                market_input["image_urls"] = [kie_client.resolve_media(value, api_key) for value in images]

            extra = inputs.get("extra_input")
            if isinstance(extra, dict):
                market_input.update(extra)

            task_id = kie_client.create_task(
                kie_model, market_input, api_key, callback_url=inputs.get("callback_url")
            )
            urls = kie_client.poll_task(
                task_id,
                api_key,
                interval=float(inputs.get("poll_interval", 2.0)),
                timeout=float(inputs.get("poll_timeout", 300.0)),
            )
            requested = Path(inputs.get("output_path") or "kie_image_output.png")
            output_paths: list[Path] = []
            for index, url in enumerate(urls):
                output_path = (
                    requested if index == 0 else requested.with_name(f"{requested.stem}_{index + 1}{requested.suffix}")
                )
                kie_client.download(url, output_path)
                output_paths.append(output_path)
        except (kie_client.KieError, ValueError, KeyError) as exc:
            return ToolResult(success=False, error=f"KIE AI image generation failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"KIE AI image generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "kie",
                "model": kie_model,
                "prompt": inputs.get("prompt", ""),
                "generation_mode": "edit" if is_edit else "generate",
                "output": str(output_paths[0]),
                "output_path": str(output_paths[0]),
                "outputs": [str(path) for path in output_paths],
                "task_id": task_id,
                "source_url": urls[0],
                "source_urls": urls,
                "request_params": market_input,
            },
            artifacts=[str(path) for path in output_paths],
            cost_usd=None,
            duration_seconds=round(time.time() - started, 2),
            model=kie_model,
        )
