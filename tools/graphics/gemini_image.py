"""Google Gemini native image generation via the ``generateContent`` endpoint.

Distinct from ``google_imagen``: the Imagen family is served from Vertex AI's
``:predict`` endpoint and needs OAuth or a service account plus a project id.
The Gemini image models (``gemini-3-pro-image``, ``gemini-3.1-flash-image``,
``gemini-2.5-flash-image``, …) are served from the ordinary Gemini API and
accept a plain ``GOOGLE_API_KEY``, returning the image as inline base64 data
in the response parts. An AI Studio key that 404s on Imagen works here.
"""

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

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiImage(BaseTool):
    name = "gemini_image"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google"
    runtime = ToolRuntime.API
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    stability = ToolStability.BETA

    dependencies = []
    install_instructions = (
        "Set GOOGLE_API_KEY (or GEMINI_API_KEY) to a Google AI Studio key:\n"
        "  https://aistudio.google.com/apikey\n"
        "No project id or service account is needed — unlike google_imagen,\n"
        "which uses Vertex AI and requires GOOGLE_CLOUD_PROJECT plus OAuth or\n"
        "a service-account JSON. If Imagen returns 404 for your key, the model\n"
        "is not served on the Gemini API; use this tool instead."
    )
    fallback = "google_imagen"
    fallback_tools = ["google_imagen", "flux_image", "dashscope_image"]
    agent_skills = ["gemini-omni"]

    supports = {
        "multiple_outputs": True,
        "aspect_ratio": True,
        "negative_prompt": False,
        "reference_images": True,
        "conversational_editing": True,
        "seed": False,
    }
    best_for = [
        "image generation on a plain AI Studio key with no Vertex AI setup",
        "prompt-driven stills when Imagen is not served on the account",
        "editing or re-rendering an existing image by passing it as a reference",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "What to generate."},
            "model": {
                "type": "string",
                "default": "gemini-3-pro-image",
                "description": (
                    "Gemini image model id. Availability varies by account — "
                    "list them with GET /v1beta/models and look for names "
                    "containing 'image'."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "default": "16:9",
                "enum": ["1:1", "3:4", "4:3", "9:16", "16:9", "21:9"],
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Local images to condition on. Use for editing an existing "
                    "frame or holding a subject consistent across scenes."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "n"]
    side_effects = [
        "writes image file(s) to output_path",
        "calls the Google Gemini API (billed per generated image)",
    ]
    user_visible_verification = [
        "Open the generated image and confirm it matches the prompt",
        "Check that no unintended text or watermark was rendered",
    ]

    @staticmethod
    def _get_api_key() -> str | None:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Gemini image output is billed per image; treat this as an order-of-
        # magnitude figure and read the console for exact rates.
        return 0.04 * int(inputs.get("n", 1))

    def _resolve_output_paths(self, output_path: str, count: int) -> list[Path]:
        base = Path(output_path or "gemini_image.png")
        if count == 1:
            return [base]
        return [
            base.with_name(f"{base.stem}_{i + 1}{base.suffix}") for i in range(count)
        ]

    @staticmethod
    def _mime_for(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _build_parts(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"text": inputs["prompt"]}]
        for raw in inputs.get("image_paths") or []:
            path = Path(raw)
            if not path.is_file():
                raise FileNotFoundError(f"Reference image not found: {path}")
            parts.append(
                {
                    "inline_data": {
                        "mime_type": self._mime_for(path),
                        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                    }
                }
            )
        return parts

    @staticmethod
    def _extract_images(payload: dict[str, Any]) -> list[bytes]:
        """Pull inline base64 image blobs out of the candidates' parts."""
        images: list[bytes] = []
        for candidate in payload.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                blob = part.get("inline_data") or part.get("inlineData")
                if not blob:
                    continue
                data = blob.get("data")
                if data:
                    images.append(base64.b64decode(data))
        return images

    @staticmethod
    def _refusal_text(payload: dict[str, Any]) -> str:
        """A text-only answer means the model declined or misread the ask."""
        chunks = []
        for candidate in payload.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                if part.get("text"):
                    chunks.append(part["text"])
        return " ".join(chunks).strip()

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        key = self._get_api_key()
        if key:
            message = message.replace(key, "[REDACTED]")
        return message

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="GOOGLE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        model = inputs.get("model", "gemini-3-pro-image")
        n = int(inputs.get("n", 1))
        start = time.time()

        try:
            body = {
                "contents": [{"role": "user", "parts": self._build_parts(inputs)}],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "candidateCount": n,
                    "imageConfig": {
                        "aspectRatio": inputs.get("aspect_ratio", "16:9")
                    },
                },
            }
            response = requests.post(
                f"{BASE_URL}/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=300,
            )
            if response.status_code == 404:
                return ToolResult(
                    success=False,
                    error=(
                        f"Model '{model}' is not served on this account. List the "
                        f"models your key can reach with GET {BASE_URL}/models and "
                        "pick one whose name contains 'image'."
                    ),
                )
            response.raise_for_status()
            payload = response.json()

            images = self._extract_images(payload)
            if not images:
                refusal = self._refusal_text(payload)
                return ToolResult(
                    success=False,
                    error=(
                        "Gemini returned no image data."
                        + (f" Model said: {refusal[:300]}" if refusal else "")
                    ),
                )

            paths = self._resolve_output_paths(
                inputs.get("output_path", "gemini_image.png"), count=len(images)
            )
            for path, blob in zip(paths, images):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Gemini image generation failed: {self._safe_error(exc)}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "google",
                "model": model,
                "prompt": inputs["prompt"],
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "images_generated": len(images),
                "output": str(paths[0]),
                "outputs": [str(p) for p in paths],
                "reference_images": len(inputs.get("image_paths") or []),
                "usage": payload.get("usageMetadata", {}),
            },
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
        )
