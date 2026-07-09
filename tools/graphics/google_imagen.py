"""Google Imagen image generation via Gemini API."""

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
from tools.google_credentials import (
    get_access_token,
    resolve_project_id,
    service_account_configured,
    has_google_credentials,
)

# Aspect ratio to approximate pixel dimensions (for cost/reporting only)
ASPECT_RATIOS = {
    "1:1": (1024, 1024),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "9:16": (768, 1344),
    "16:9": (1344, 768),
}


def _dims_to_aspect_ratio(width: int, height: int) -> str:
    """Convert width/height to the nearest supported aspect ratio."""
    target = width / height
    best = "1:1"
    best_diff = float("inf")
    for ratio, (w, h) in ASPECT_RATIOS.items():
        diff = abs(target - w / h)
        if diff < best_diff:
            best_diff = diff
            best = ratio
    return best


class GoogleImagen(BaseTool):
    name = "google_imagen"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google_imagen"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via env var
    install_instructions = (
        "Auth option A — API key (AI Studio): set GOOGLE_API_KEY (or GEMINI_API_KEY).\n"
        "  Get one at https://aistudio.google.com/apikey\n"
        "Auth option B — service account (Vertex AI): set GOOGLE_APPLICATION_CREDENTIALS\n"
        "  to a service-account JSON key (needs the 'google-auth' package), plus\n"
        "  GOOGLE_CLOUD_PROJECT and optionally GOOGLE_CLOUD_LOCATION (default us-central1).\n"
        "  Requires the Vertex AI API enabled and billing on the project."
    )
    agent_skills = []

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": False,
        "seed": False,
        "custom_size": False,
        "aspect_ratio": True,
    }
    best_for = [
        "high-quality photorealistic images",
        "Google ecosystem integration",
        "fast generation with multiple aspect ratios",
    ]
    not_good_for = [
        "negative prompt control (not supported)",
        "exact pixel dimensions (uses aspect ratios)",
        "offline generation",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image description (max 480 tokens)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "default": "1:1",
                "description": "Aspect ratio of generated image",
            },
            "width": {
                "type": "integer",
                "description": "Desired width in pixels — mapped to nearest aspect ratio",
            },
            "height": {
                "type": "integer",
                "description": "Desired height in pixels — mapped to nearest aspect ratio",
            },
            "model": {
                "type": "string",
                "enum": [
                    "imagen-4.0-generate-001",
                    "imagen-4.0-fast-generate-001",
                    "imagen-4.0-ultra-generate-001",
                ],
                "default": "imagen-4.0-generate-001",
                "description": "Imagen model variant",
            },
            "number_of_images": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 4,
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "aspect_ratio", "model"]
    side_effects = [
        "writes image file to output_path",
        "calls Google Generative AI API",
    ]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    def get_status(self) -> ToolStatus:
        # API key -> AI Studio endpoint; service-account JSON -> Vertex AI.
        if has_google_credentials():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "imagen-4.0-generate-001")
        n = inputs.get("number_of_images", 1)
        if "ultra" in model:
            return 0.06 * n
        if "fast" in model:
            return 0.02 * n
        return 0.04 * n

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # Two auth paths: an AI Studio API key, or a service-account JSON that
        # routes to Vertex AI (the AI Studio endpoint does not accept service
        # accounts). API key wins when both are present.
        api_key = self._get_api_key()
        bearer_token: str | None = None
        project_id: str | None = None
        if not api_key:
            if not service_account_configured():
                return ToolResult(
                    success=False,
                    error="No Google credentials found. " + self.install_instructions,
                )
            try:
                bearer_token, creds_project = get_access_token()
            except RuntimeError as exc:
                return ToolResult(success=False, error=str(exc))
            project_id = resolve_project_id(creds_project)
            if not project_id:
                return ToolResult(
                    success=False,
                    error=(
                        "Vertex AI needs a project id. Set GOOGLE_CLOUD_PROJECT "
                        "(or include project_id in the service-account key)."
                    ),
                )

        import requests

        start = time.time()
        model = inputs.get("model", "imagen-4.0-generate-001")
        prompt = inputs["prompt"]

        import logging

        logger = logging.getLogger(__name__)

        # Resolve aspect ratio: explicit > derived from width/height > default
        if "aspect_ratio" in inputs:
            aspect_ratio = inputs["aspect_ratio"]
        elif "width" in inputs and "height" in inputs:
            requested_ratio = f"{inputs['width']}x{inputs['height']}"
            aspect_ratio = _dims_to_aspect_ratio(inputs["width"], inputs["height"])
            logger.info(
                "google_imagen: remapped %s to nearest supported aspect ratio %s",
                requested_ratio,
                aspect_ratio,
            )
        else:
            aspect_ratio = "1:1"

        number_of_images = inputs.get("number_of_images", 1)

        parameters: dict[str, Any] = {
            "sampleCount": number_of_images,
            "aspectRatio": aspect_ratio,
        }

        if bearer_token:
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            url = (
                f"https://{location}-aiplatform.googleapis.com/v1/projects/"
                f"{project_id}/locations/{location}/publishers/google/models/"
                f"{model}:predict"
            )
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {bearer_token}",
            }
        else:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:predict"
            )
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key or "",
            }

        try:
            response = requests.post(
                url,
                headers=headers,
                json={
                    "instances": [{"prompt": prompt}],
                    "parameters": parameters,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            predictions = data.get("predictions", [])
            if not predictions:
                return ToolResult(
                    success=False, error="No images returned from Imagen API"
                )

            image_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])

            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

        except Exception as e:
            return ToolResult(success=False, error=f"Imagen generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": str(output_path),
                "images_generated": len(predictions),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
