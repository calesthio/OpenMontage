"""MiniMax image generation through the first-party API."""

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
    ToolTier,
)


MODELS = ["image-01", "image-01-live"]
DEFAULT_MODEL = "image-01"
DEFAULT_REGION = "global"
# Official global pay-as-you-go rate for image-01/image-01-live.
PRICE_PER_IMAGE_USD = 0.0035
REGION_BASE_URLS = {
    "global": "https://api.minimax.io",
    "global_en": "https://api.minimax.io",
    "cn": "https://api.minimaxi.com",
    "cn_zh": "https://api.minimaxi.com",
}


class MiniMaxImage(BaseTool):
    name = "minimax_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "minimax"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:MINIMAX_API_KEY"]
    install_instructions = (
        "Set MINIMAX_API_KEY to your MiniMax API key. "
        "Optionally set MINIMAX_REGION to global or cn."
    )
    # MiniMax is not a FLUX model. Use the provider-neutral visual direction
    # skill until a dedicated MiniMax prompting skill is available.
    agent_skills = ["visual-style"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "multiple_outputs": True,
        "aspect_ratio": True,
        "custom_dimensions": True,
        "seed": True,
        "subject_reference": True,
        "url_response": True,
        "base64_response": True,
    }
    best_for = [
        "first-party MiniMax image generation",
        "seeded multi-image generation",
        "global and mainland China API routing",
    ]
    not_good_for = ["offline generation"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "maxLength": 1500},
            "model": {
                "type": "string",
                "enum": MODELS,
                "default": DEFAULT_MODEL,
            },
            "subject_reference": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["type", "image_file"],
                    "properties": {
                        "type": {"type": "string", "enum": ["character"]},
                        "image_file": {"type": "string"},
                    },
                },
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"],
                "default": "1:1",
            },
            "width": {"type": "integer", "minimum": 512, "maximum": 2048, "multipleOf": 8},
            "height": {"type": "integer", "minimum": 512, "maximum": 2048, "multipleOf": 8},
            "response_format": {
                "type": "string",
                "enum": ["url", "base64"],
                "default": "url",
            },
            "seed": {"type": "integer"},
            "n": {"type": "integer", "minimum": 1, "maximum": 9, "default": 1},
            "prompt_optimizer": {"type": "boolean", "default": False},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "prompt",
        "model",
        "subject_reference",
        "aspect_ratio",
        "width",
        "height",
        "response_format",
        "seed",
        "n",
        "prompt_optimizer",
    ]
    side_effects = [
        "writes image files to output_path",
        "calls the MiniMax image generation API",
    ]
    user_visible_verification = [
        "Inspect generated images for prompt adherence and visual quality"
    ]

    @staticmethod
    def _region() -> str:
        region = os.environ.get("MINIMAX_REGION", DEFAULT_REGION).strip().lower()
        return region if region in REGION_BASE_URLS else DEFAULT_REGION

    def _base_url(self) -> str:
        override = os.environ.get("MINIMAX_BASE_URL")
        if override:
            return override.rstrip("/")
        return REGION_BASE_URLS[self._region()]

    @staticmethod
    def _base_resp_error(data: dict[str, Any]) -> str | None:
        base_resp = data.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        if status_code in (None, 0):
            return None
        status_msg = base_resp.get("status_msg") or "unknown error"
        return f"MiniMax API error {status_code}: {status_msg}"

    @staticmethod
    def _output_paths(output_path: str | None, count: int) -> list[Path]:
        path = Path(output_path or "minimax_image.png")
        if not path.suffix:
            path = path.with_suffix(".png")
        if count == 1:
            return [path]
        return [
            path.with_name(f"{path.stem}_{index}{path.suffix}")
            for index in range(1, count + 1)
        ]

    @staticmethod
    def _build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
        model = inputs.get("model", DEFAULT_MODEL)
        if model not in MODELS:
            raise ValueError(f"Unsupported MiniMax image model '{model}'.")

        prompt = inputs.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("MiniMax image generation requires 'prompt'.")
        if len(prompt) > 1500:
            raise ValueError("MiniMax image prompt must not exceed 1500 characters.")

        width = inputs.get("width")
        height = inputs.get("height")
        if (width is None) != (height is None):
            raise ValueError("MiniMax image width and height must be set together.")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "response_format": inputs.get("response_format", "url"),
            "n": inputs.get("n", 1),
            "prompt_optimizer": inputs.get("prompt_optimizer", False),
        }
        for field in (
            "subject_reference",
            "aspect_ratio",
            "width",
            "height",
            "seed",
        ):
            if inputs.get(field) is not None:
                payload[field] = inputs[field]
        return payload

    @staticmethod
    def _decode_base64_image(value: str) -> bytes:
        encoded = value.split(",", 1)[1] if value.startswith("data:") else value
        return base64.b64decode(encoded)

    @staticmethod
    def _safe_error(exc: Exception, api_key: str) -> str:
        return str(exc).replace(api_key, "[redacted]") if api_key else str(exc)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return PRICE_PER_IMAGE_USD * int(inputs.get("n", 1))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not api_key:
            return ToolResult(
                success=False,
                error="MINIMAX_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        try:
            payload = self._build_payload(inputs)
            response = requests.post(
                f"{self._base_url()}/v1/image_generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

            base_error = self._base_resp_error(data)
            if base_error:
                return ToolResult(success=False, error=base_error)

            response_format = payload["response_format"]
            data_object = data.get("data") or {}
            image_values = data_object.get(
                "image_base64" if response_format == "base64" else "image_urls"
            ) or []
            if not image_values:
                return ToolResult(
                    success=False,
                    error=f"MiniMax returned no {response_format} image outputs.",
                )

            output_paths = self._output_paths(
                inputs.get("output_path"), len(image_values)
            )
            for path, value in zip(output_paths, image_values):
                path.parent.mkdir(parents=True, exist_ok=True)
                if response_format == "base64":
                    path.write_bytes(self._decode_base64_image(value))
                else:
                    download = requests.get(value, timeout=120)
                    download.raise_for_status()
                    path.write_bytes(download.content)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=(
                    "MiniMax image generation failed: "
                    f"{self._safe_error(exc, api_key)}"
                ),
            )

        outputs = [str(path) for path in output_paths]
        return ToolResult(
            success=True,
            data={
                "provider": "minimax",
                "model": payload["model"],
                "prompt": payload["prompt"],
                "region": self._region(),
                "response_format": payload["response_format"],
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
                "metadata": data.get("metadata") or {},
                "request_id": data.get("id"),
            },
            artifacts=outputs,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )
