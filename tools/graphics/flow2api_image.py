"""Google Gemini / Imagen image generation via Flow2API (local gateway).

Supports Gemini 3.0 Pro, Gemini 3.1 Flash, and Imagen 4.0 through a local
Flow2API proxy that bridges to Google ImageFX / Vertex AI.
"""

from __future__ import annotations

import os
import time
import uuid
import base64
import mimetypes
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


class Flow2ApiImage(BaseTool):
    name = "flow2api_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "flow2api"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FLOW2API_API_KEY to your Flow2API API key.\n"
        "  Set FLOW2API_BASE_URL to your Flow2API server address (default http://127.0.0.1:8000)"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "seed": False,
        "custom_size": True,
        "aspect_ratio": True,
        "image_size": True,
    }
    best_for = [
        "high quality images via Google Gemini 3.0/3.1",
        "Imagen 4.0 photorealistic generation",
        "free daily quota (1000 credits/day via Flow2API)",
        "multiple aspect ratios (landscape, portrait, square, 4:3, 3:4)",
        "2K and 4K resolution output",
    ]
    not_good_for = ["offline generation", "seed-based reproducibility"]
    fallback_tools = ["flux_image", "openai_image", "google_imagen"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["gemini-3.0-pro-image", "gemini-3.1-flash-image", "imagen-4.0-generate-preview"],
                "default": "gemini-3.0-pro-image",
                "description": "Gemini for general use, Imagen for photorealism",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["landscape", "portrait", "square", "four-three", "three-four"],
                "default": "landscape",
            },
            "image_size": {
                "type": "string",
                "enum": ["default", "2k", "4k"],
                "default": "default",
                "description": "Output resolution tier (4k may use more credits)",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "image_size"]
    side_effects = ["writes image file to output_path", "calls Flow2API server"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FLOW2API_API_KEY")

    def _get_base_url(self) -> str:
        return os.environ.get("FLOW2API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Flow2API uses credits. Image gen ≈ 1-3 credits depending on size
        image_size = inputs.get("image_size", "default")
        if image_size == "4k":
            return 0.03
        elif image_size == "2k":
            return 0.02
        return 0.01

    def _resolve_model_name(self, model: str, aspect_ratio: str, image_size: str) -> str:
        """Build the Flow2API model name from parameters."""
        # Imagen only supports landscape and portrait
        if model.startswith("imagen"):
            if aspect_ratio == "portrait":
                return f"{model}-portrait"
            return f"{model}-landscape"

        # Gemini models support all aspect ratios + size suffix
        parts = [model, aspect_ratio]
        if image_size and image_size != "default":
            parts.append(image_size)
        return "-".join(parts)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FLOW2API_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        base_url = self._get_base_url()
        prompt = inputs["prompt"]
        model = inputs.get("model", "gemini-3.0-pro-image")
        aspect_ratio = inputs.get("aspect_ratio", "landscape")
        image_size = inputs.get("image_size", "default")

        model_name = self._resolve_model_name(model, aspect_ratio, image_size)

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        image_timeout = int(os.environ.get("FLOW2API_IMAGE_TIMEOUT", "120"))

        try:
            response = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=image_timeout,
            )

            if response.status_code == 503:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", response.text[:500])
                return ToolResult(
                    success=False,
                    error=f"Flow2API token unavailable (503): {error_msg}. "
                          "Google token may be expired — refresh via Chrome extension or configure captcha solver.",
                )

            response.raise_for_status()
            data = response.json()

            # Parse response: image URL or base64 data
            image_url = None
            image_b64 = None
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content", "")

                if isinstance(content, str):
                    if content.startswith("http"):
                        image_url = content.strip()
                    elif content.startswith("data:image"):
                        image_b64 = content
                elif isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        if part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("http"):
                                image_url = url
                            elif url.startswith("data:"):
                                image_b64 = url
                        elif part.get("type") == "output_url":
                            image_url = part.get("output_url")
                        elif "url" in part:
                            u = part["url"]
                            if isinstance(u, str) and u.startswith("http"):
                                image_url = u
                        elif "inlineData" in part:
                            inline = part["inlineData"]
                            image_b64 = f"data:{inline.get('mimeType', 'image/png')};base64,{inline.get('data', '')}"

            # Also check top-level fields
            if not image_url and not image_b64:
                image_url = data.get("image") or data.get("url") or data.get("output")

            if not image_url and not image_b64:
                return ToolResult(
                    success=False,
                    error=f"Flow2API returned no image. Response: {str(data)[:1000]}",
                )

            output_path = Path(inputs.get("output_path", f"flow2api_image_{uuid.uuid4().hex[:8]}.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if image_b64:
                # Decode base64 data URI
                if "," in image_b64:
                    raw_b64 = image_b64.split(",", 1)[1]
                else:
                    raw_b64 = image_b64
                output_path.write_bytes(base64.b64decode(raw_b64))
            else:
                # Download from URL
                img_response = requests.get(image_url, timeout=60)
                img_response.raise_for_status()
                output_path.write_bytes(img_response.content)

        except requests.exceptions.Timeout:
            return ToolResult(
                success=False,
                error=f"Flow2API image generation timed out after {image_timeout}s.",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Flow2API image generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "flow2api",
                "model": model_name,
                "prompt": prompt,
                "output": str(output_path),
                "aspect_ratio": aspect_ratio,
                "image_size": image_size,
                "image_url": image_url,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_name,
        )
