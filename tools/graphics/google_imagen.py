"""Google image generation via Imagen (AI Studio / Vertex AI) and Gemini Pro/Flash."""

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

# Aspect ratio to approximate pixel dimensions (for cost/reporting only)
ASPECT_RATIOS = {
    "1:1": (1024, 1024),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "9:16": (768, 1344),
    "16:9": (1344, 768),
}

# Friendly model alias → actual API model ID
GEMINI_MODEL_ALIASES: dict[str, str] = {
    "gemini-pro": "gemini-2.0-pro-exp",
    "gemini-2.0-pro-exp": "gemini-2.0-pro-exp",
    "gemini-flash": "gemini-2.5-flash-latest",
    "gemini-2.5-flash": "gemini-2.5-flash-latest",
}

# All Imagen model IDs (passed through as-is to the Imagen predict endpoint)
IMAGEN_MODELS = {
    "imagen-3.0-generate-001",
    "imagen-4.0-generate-001",
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-ultra-generate-001",
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
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google_imagen"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via env var
    install_instructions = (
        "Google image generation supports three auth modes and three model families:\n\n"
        "AUTH MODES (priority order):\n"
        "  1. GEMINI_API_KEY  — AI Studio mode (recommended, free quota for Imagen 3)\n"
        "  2. GOOGLE_API_KEY  — AI Studio mode (same endpoint, alternative key name)\n"
        "  3. GOOGLE_APPLICATION_CREDENTIALS — Vertex AI mode (service account JSON path)\n\n"
        "Get an AI Studio key: https://aistudio.google.com/apikey\n"
        "Get a service account: https://console.cloud.google.com/iam-admin/serviceaccounts\n\n"
        "MODEL OPTIONS:\n"
        "  imagen-3.0-generate-001  (default) — Imagen 3 standard via AI Studio\n"
        "    Free quota on AI Studio; good photorealistic quality; fastest.\n"
        "  gemini-flash  — Gemini 2.5 Flash via AI Studio\n"
        "    Alias for gemini-2.5-flash-latest. Paid. Fast, high-fidelity, great for\n"
        "    prototyping. Recommended for bulk production runs.\n"
        "  gemini-pro  — Gemini 2.0 Pro Exp via AI Studio\n"
        "    Alias for gemini-2.0-pro-exp. Paid. Highest detail and instruction\n"
        "    following; slower. Best for hero images and complex compositions.\n\n"
        "VERTEX AI (GOOGLE_APPLICATION_CREDENTIALS):\n"
        "  Routes Imagen calls to us-central1-aiplatform.googleapis.com.\n"
        "  Gemini model aliases are not available in Vertex AI mode (use AI Studio instead)."
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
        "Gemini Pro for complex, detailed compositions",
        "Gemini Flash for fast high-fidelity prototyping",
    ]
    not_good_for = [
        "negative prompt control (not supported)",
        "exact pixel dimensions (uses aspect ratios)",
        "offline generation",
        "Gemini image generation is a paid feature",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Image description (max 480 tokens)"},
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
                    # Imagen models (AI Studio + Vertex AI)
                    "imagen-3.0-generate-001",
                    "imagen-4.0-generate-001",
                    "imagen-4.0-fast-generate-001",
                    "imagen-4.0-ultra-generate-001",
                    # Gemini aliases (AI Studio only)
                    "gemini-pro",
                    "gemini-2.0-pro-exp",
                    "gemini-flash",
                    "gemini-2.5-flash",
                ],
                "default": "imagen-3.0-generate-001",
                "description": (
                    "Model to use for image generation.\n"
                    "  imagen-3.0-generate-001 (default) — free quota on AI Studio, solid quality.\n"
                    "  imagen-4.0-generate-001 — Imagen 4 standard; sharper, better text.\n"
                    "  imagen-4.0-fast-generate-001 — Imagen 4 fast; lower cost.\n"
                    "  imagen-4.0-ultra-generate-001 — Imagen 4 ultra; highest quality, highest cost.\n"
                    "  gemini-pro / gemini-2.0-pro-exp — Gemini 2.0 Pro Exp; paid, slow, best detail.\n"
                    "  gemini-flash / gemini-2.5-flash — Gemini 2.5 Flash; paid, fast, high-fidelity."
                ),
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
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "aspect_ratio", "model"]
    side_effects = ["writes image file to output_path", "calls Google Generative AI API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_api_key(self) -> str | None:
        """Return AI Studio API key (GEMINI_API_KEY takes priority)."""
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def _detect_mode(self) -> str:
        """Return 'gemini_studio' or 'vertex_ai' based on available credentials."""
        if self._get_api_key():
            return "gemini_studio"
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return "vertex_ai"
        return "none"

    def get_status(self) -> ToolStatus:
        if self._detect_mode() != "none":
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "imagen-3.0-generate-001")
        n = inputs.get("number_of_images", 1)
        # Gemini models — paid per image (approximate)
        if model in ("gemini-pro", "gemini-2.0-pro-exp"):
            return 0.08 * n
        if model in ("gemini-flash", "gemini-2.5-flash"):
            return 0.04 * n
        # Imagen models
        if "ultra" in model:
            return 0.06 * n
        if "fast" in model:
            return 0.02 * n
        return 0.04 * n

    # ------------------------------------------------------------------
    # Imagen via AI Studio
    # ------------------------------------------------------------------

    def _generate_imagen_studio(
        self,
        prompt: str,
        model: str,
        n: int,
        aspect_ratio: str,
        output_path: Path,
        api_key: str,
    ) -> ToolResult:
        """Call the AI Studio Imagen predict endpoint."""
        import requests

        start = time.time()
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json={
                    "instances": [{"prompt": prompt}],
                    "parameters": {
                        "sampleCount": n,
                        "aspectRatio": aspect_ratio,
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            predictions = data.get("predictions", [])
            if not predictions:
                return ToolResult(success=False, error="No images returned from Imagen API")

            image_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

        except Exception as e:
            return ToolResult(success=False, error=f"Imagen (AI Studio) generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "mode": "gemini_studio",
                "model_used": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": str(output_path),
                "images_generated": len(predictions),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost({"model": model, "number_of_images": n}),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    # ------------------------------------------------------------------
    # Gemini image generation via AI Studio (Pro / Flash)
    # ------------------------------------------------------------------

    def _generate_gemini_image(
        self,
        prompt: str,
        model_id: str,
        n: int,
        aspect_ratio: str,
        output_path: Path,
        api_key: str,
    ) -> ToolResult:
        """Call the AI Studio Gemini generateContent endpoint for image output."""
        import requests

        start = time.time()
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "response_modalities": ["IMAGE", "TEXT"],
                        "numberOfImages": n,
                    },
                },
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return ToolResult(
                    success=False,
                    error=f"No candidates returned from Gemini image API (model={model_id})",
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            image_parts = [
                p for p in parts
                if p.get("inlineData", {}).get("mimeType", "").startswith("image/")
            ]

            if not image_parts:
                return ToolResult(
                    success=False,
                    error=(
                        f"Gemini returned no image parts (model={model_id}). "
                        "Ensure your API key has access to Gemini image generation (paid feature). "
                        f"Parts returned: {[list(p.keys()) for p in parts]}"
                    ),
                )

            image_bytes = base64.b64decode(image_parts[0]["inlineData"]["data"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

        except Exception as e:
            return ToolResult(success=False, error=f"Gemini image generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "mode": "gemini_studio",
                "model_used": model_id,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": str(output_path),
                "images_generated": len(image_parts),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost({"model": model_id, "number_of_images": n}),
            duration_seconds=round(time.time() - start, 2),
            model=model_id,
        )

    # ------------------------------------------------------------------
    # Vertex AI Imagen
    # ------------------------------------------------------------------

    def _get_vertex_access_token(self) -> str:
        """Obtain a short-lived access token from a service account JSON file."""
        import json
        import time as _time

        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not credentials_path or not Path(credentials_path).exists():
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS must point to a valid service account JSON file."
            )

        with open(credentials_path) as f:
            sa = json.load(f)

        # Build a JWT for the Google OAuth2 token endpoint
        import base64 as _b64
        import hashlib
        import hmac

        def _b64url(data: bytes) -> str:
            return _b64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header = _b64url(b'{"alg":"RS256","typ":"JWT"}')
        now = int(_time.time())
        claim = _b64url(
            (
                '{"iss":"%s","scope":"https://www.googleapis.com/auth/cloud-platform",'
                '"aud":"https://oauth2.googleapis.com/token","iat":%d,"exp":%d}'
                % (sa["client_email"], now, now + 3600)
            ).encode()
        )
        signing_input = f"{header}.{claim}".encode()

        # Use cryptography library if available, else fall back to subprocess openssl
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key = serialization.load_pem_private_key(
                sa["private_key"].encode(), password=None
            )
            signature = _b64url(
                private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
            )
        except ImportError:
            # fallback: use subprocess + openssl (available on macOS/Linux)
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tmp:
                tmp.write(sa["private_key"].encode())
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    ["openssl", "dgst", "-sha256", "-sign", tmp_path],
                    input=signing_input,
                    capture_output=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"openssl signing failed: {result.stderr.decode()}")
                signature = _b64url(result.stdout)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        jwt = f"{header}.{claim}.{signature}"

        import requests

        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt,
            },
            timeout=30,
        )
        token_resp.raise_for_status()
        return token_resp.json()["access_token"]

    def _generate_vertex(
        self,
        prompt: str,
        model: str,
        n: int,
        aspect_ratio: str,
        output_path: Path,
    ) -> ToolResult:
        """Call the Vertex AI Imagen endpoint using a service account access token."""
        import requests

        # Gemini aliases are not supported in Vertex AI mode
        if model in GEMINI_MODEL_ALIASES:
            return ToolResult(
                success=False,
                error=(
                    f"Model '{model}' (Gemini image generation) is only available in AI Studio mode. "
                    "Set GEMINI_API_KEY or GOOGLE_API_KEY to use Gemini models. "
                    "Vertex AI mode supports Imagen models only."
                ),
            )

        start = time.time()
        try:
            access_token = self._get_vertex_access_token()
        except Exception as e:
            return ToolResult(
                success=False,
                error=(
                    f"Vertex AI authentication failed: {e}. "
                    "Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid service account JSON "
                    "with roles/aiplatform.user granted in your GCP project."
                ),
            )

        # Derive project ID from the service account JSON
        try:
            import json

            with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]) as f:
                sa = json.load(f)
            project_id = sa.get("project_id", "")
            if not project_id:
                raise ValueError("project_id missing from service account JSON")
        except Exception as e:
            return ToolResult(success=False, error=f"Could not read project_id from credentials: {e}")

        endpoint = (
            f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}"
            f"/locations/us-central1/publishers/google/models/{model}:predict"
        )

        try:
            response = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json={
                    "instances": [{"prompt": prompt}],
                    "parameters": {
                        "sampleCount": n,
                        "aspectRatio": aspect_ratio,
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            predictions = data.get("predictions", [])
            if not predictions:
                return ToolResult(success=False, error="No images returned from Vertex AI Imagen API")

            image_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

        except Exception as e:
            return ToolResult(success=False, error=f"Vertex AI Imagen generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "google_imagen",
                "mode": "vertex_ai",
                "model_used": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output": str(output_path),
                "images_generated": len(predictions),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost({"model": model, "number_of_images": n}),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import logging

        logger = logging.getLogger(__name__)

        mode = self._detect_mode()
        if mode == "none":
            return ToolResult(
                success=False,
                error="No Google credentials found. " + self.install_instructions,
            )

        prompt = inputs["prompt"]
        model_input = inputs.get("model", "imagen-3.0-generate-001")

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

        n = inputs.get("number_of_images", 1)
        output_path = Path(inputs.get("output_path", "generated_image.png"))

        # Resolve model alias → actual model ID
        if model_input in GEMINI_MODEL_ALIASES:
            resolved_model = GEMINI_MODEL_ALIASES[model_input]
            is_gemini = True
        else:
            resolved_model = model_input
            is_gemini = False

        logger.info(
            "google_imagen: mode=%s model_input=%s resolved=%s",
            mode,
            model_input,
            resolved_model,
        )

        # Route by mode and model family
        if mode == "vertex_ai":
            return self._generate_vertex(prompt, resolved_model, n, aspect_ratio, output_path)

        # AI Studio path
        api_key = self._get_api_key()
        assert api_key  # guaranteed by _detect_mode()

        if is_gemini:
            return self._generate_gemini_image(
                prompt, resolved_model, n, aspect_ratio, output_path, api_key
            )
        else:
            return self._generate_imagen_studio(
                prompt, resolved_model, n, aspect_ratio, output_path, api_key
            )
