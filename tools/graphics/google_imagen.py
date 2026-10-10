"""Google Imagen image generation via Gemini API."""

from __future__ import annotations

import base64
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
from tools.google_credentials import (
    get_access_token,
    resolve_google_location,
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
    agent_skills = ["provider-model-refresh"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": False,
        "seed": False,
        "custom_size": False,
        "aspect_ratio": True,
        "image_edit": True,
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
                    "gemini-2.5-flash-image",
                    "gemini-3-pro-image",
                    "gemini-3.1-flash-image",
                ],
                "default": "imagen-4.0-generate-001",
                "description": "Imagen model variant, or a Gemini image model "
                "(gemini-*) routed through generate_content. Use "
                "gemini-2.5-flash-image when the project has no Imagen access.",
            },
            "number_of_images": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 4,
            },
            "output_path": {"type": "string"},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"]},
            "image_path": {"type": "string"},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 14,
            },
            "resolution": {"type": "string", "enum": ["1K", "2K", "4K"]},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "aspect_ratio", "model"] + [
        "generation_mode",
        "image_path",
        "image_paths",
        "resolution",
        "number_of_images",
    ]
    side_effects = [
        "writes image file to output_path",
        "calls Google Generative AI API",
    ]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    @staticmethod
    def _output_paths(output_path: str | None, count: int) -> list[Path]:
        """Derive one output path per generated image.

        With a single image, honor the requested path as-is. With several,
        suffix each with `_1`, `_2`, … so no image overwrites another.
        """
        ext = ".png"
        if not output_path:
            return [Path(f"generated_image_{idx + 1}{ext}") for idx in range(count)]

        path = Path(output_path)
        suffix = path.suffix or ext
        if count == 1:
            return [path if path.suffix else path.with_suffix(suffix)]

        base = path.with_suffix("") if path.suffix else path
        return [base.parent / f"{base.name}_{idx + 1}{suffix}" for idx in range(count)]

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
        if model in {"gemini-3-pro-image", "gemini-3.1-flash-image"}:
            raise PriceQuoteRequired(
                "Gemini image pricing depends on input and output tokens/resolution; obtain a current quote"
            )
        if model.startswith("gemini-"):
            # ~1290 output tokens per image at $30/1M tokens
            return 0.039 * n
        if "ultra" in model:
            return 0.06 * n
        if "fast" in model:
            return 0.02 * n
        return 0.04 * n

    def _resolve_aspect_ratio(self, inputs: dict[str, Any]) -> str:
        """Explicit aspect_ratio > derived from width/height > default 1:1."""
        if "aspect_ratio" in inputs:
            return inputs["aspect_ratio"]
        if "width" in inputs and "height" in inputs:
            import logging

            aspect_ratio = _dims_to_aspect_ratio(inputs["width"], inputs["height"])
            logging.getLogger(__name__).info(
                "google_imagen: remapped %sx%s to nearest supported aspect ratio %s",
                inputs["width"],
                inputs["height"],
                aspect_ratio,
            )
            return aspect_ratio
        return "1:1"

    def _execute_gemini(self, inputs: dict[str, Any], model: str) -> ToolResult:
        """Generate via a Gemini image model (e.g. gemini-2.5-flash-image).

        These models use generate_content with an image_config instead of the
        Imagen :predict endpoint, and work on both auth paths (API key and
        Vertex service account) through the shared genai client.
        """
        start = time.time()
        try:
            from google.genai import types
            from tools.google_credentials import get_genai_client

            client = get_genai_client()
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to initialize Google GenAI client: {e}",
            )

        if (
            inputs.get("image_url")
            or inputs.get("image_urls")
            or inputs.get("mask_url")
        ):
            return ToolResult(
                success=False,
                error="This direct Gemini adapter accepts local image_path/image_paths, not image URLs or masks",
            )
        prompt = inputs["prompt"]
        aspect_ratio = self._resolve_aspect_ratio(inputs)
        number_of_images = inputs.get("number_of_images", 1)
        image_config = {"aspect_ratio": aspect_ratio}
        if inputs.get("resolution"):
            if model == "gemini-2.5-flash-image":
                return ToolResult(
                    success=False,
                    error="Resolution control requires Gemini 3 image models",
                )
            image_config["image_size"] = inputs["resolution"]
        config = types.GenerateContentConfig(
            image_config=types.ImageConfig(**image_config)
        )
        contents = [prompt]
        try:
            import mimetypes

            paths = list(inputs.get("image_paths") or [])
            if inputs.get("image_path"):
                paths.insert(0, inputs["image_path"])
            if len(paths) > 14:
                raise ValueError("At most 14 reference images")
            if inputs.get("generation_mode") == "edit" and not paths:
                raise ValueError("Edit requires source images")
            if inputs.get("generation_mode") == "generate" and paths:
                raise ValueError("Use edit for source images")
            contents.extend(
                types.Part.from_bytes(
                    data=Path(p).read_bytes(),
                    mime_type=mimetypes.guess_type(p)[0] or "image/png",
                )
                for p in paths
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

        image_bytes: list[bytes] = []
        try:
            for _ in range(number_of_images):
                response = client.models.generate_content(
                    model=model,
                    contents=contents if len(contents) > 1 else prompt,
                    config=config,
                )
                for part in response.candidates[0].content.parts or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        image_bytes.append(inline.data)
                        break
        except Exception as e:
            return ToolResult(
                success=False, error=f"Gemini image generation failed: {e}"
            )

        if not image_bytes:
            return ToolResult(
                success=False,
                error=f"No image data returned by {model} (text-only response).",
            )

        output_paths = self._output_paths(inputs.get("output_path"), len(image_bytes))
        outputs: list[str] = []
        for data, out_path in zip(image_bytes, output_paths):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            outputs.append(str(out_path))

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
                "cost_status": "unquoted"
                if model in {"gemini-3-pro-image", "gemini-3.1-flash-image"}
                else "estimated",
            },
            artifacts=outputs,
            cost_usd=self.estimate_cost(inputs)
            if model not in {"gemini-3-pro-image", "gemini-3.1-flash-image"}
            else None,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # Gemini image models go through generate_content via the shared genai
        # client, which resolves auth (API key or Vertex service account) itself.
        model = inputs.get("model", "imagen-4.0-generate-001")
        if model not in self.input_schema["properties"]["model"]["enum"]:
            return ToolResult(
                success=False, error=f"Unsupported Google image model: {model}"
            )
        if model.startswith("gemini-"):
            return self._execute_gemini(inputs, model)
        if (
            inputs.get("image_path")
            or inputs.get("image_paths")
            or inputs.get("generation_mode") == "edit"
        ):
            return ToolResult(
                success=False,
                error="Imagen generation does not accept source images; choose a Gemini image model",
            )

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
        prompt = inputs["prompt"]

        aspect_ratio = self._resolve_aspect_ratio(inputs)
        number_of_images = inputs.get("number_of_images", 1)

        parameters: dict[str, Any] = {
            "sampleCount": number_of_images,
            "aspectRatio": aspect_ratio,
        }

        if bearer_token:
            location = resolve_google_location()
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

            output_paths = self._output_paths(
                inputs.get("output_path"), len(predictions)
            )
            outputs: list[str] = []
            for prediction, out_path in zip(predictions, output_paths):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(base64.b64decode(prediction["bytesBase64Encoded"]))
                outputs.append(str(out_path))

        except Exception as e:
            return ToolResult(success=False, error=f"Imagen generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
                "cost_status": "unquoted"
                if model in {"gemini-3-pro-image", "gemini-3.1-flash-image"}
                else "estimated",
            },
            artifacts=outputs,
            cost_usd=self.estimate_cost(inputs)
            if model not in {"gemini-3-pro-image", "gemini-3.1-flash-image"}
            else None,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
