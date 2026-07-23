"""Generate music using Google Lyria via Google GenAI SDK.

Generate background music and audio tracks for video production using lyria-3-pro-preview.
"""

from __future__ import annotations

import base64
import mimetypes
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


class GoogleMusic(BaseTool):
    name = "google_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "google"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Configure Google credentials:\n"
        "  - Set GEMINI_API_KEY (or GOOGLE_API_KEY) in environment.\n"
        "  - Or set GOOGLE_APPLICATION_CREDENTIALS for Vertex AI service account."
    )
    fallback_tools = ["music_gen"]
    agent_skills = ["lyria"]

    capabilities = [
        "generate_background_music",
    ]
    supports = {
        "instrumental": True,
        "vocals": True,
        "custom_lyrics": True,
        "style_control": True,
        "long_form": True,
    }
    best_for = [
        "high-quality instrumental background music",
        "genre-specific music guided by rich text prompts",
        "Google ecosystem integration",
    ]
    not_good_for = [
        "offline generation",
        "sub-5-second sound effects",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Music description (mood, genre, instruments, tempo)",
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": 184,
                "default": 30,
                "description": "Target duration in seconds (model hard limit is 184s)",
            },
            "image_url": {
                "type": "string",
                "description": "Reference image URL for visual music conditioning",
            },
            "image_path": {
                "type": "string",
                "description": "Local reference image path for visual music conditioning",
            },
            "auto_fix": {"type": "boolean", "default": True},
            "output_path": {
                "type": "string",
                "default": "music_output.mp3",
                "description": "Path where the generated MP3 file should be written",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "duration_seconds", "image_url", "image_path"]
    side_effects = [
        "writes audio file to output_path",
        "calls Google Gemini/Vertex API",
    ]
    user_visible_verification = [
        "Listen to generated music for style and quality",
    ]

    def _get_google_credentials_status(self) -> bool:
        """Check whether Google API keys or Vertex AI service account credentials are set."""
        from tools.google_credentials import has_google_credentials

        return has_google_credentials()

    def get_status(self) -> ToolStatus:
        """Determine whether the tool is available based on configured credentials."""
        if self._get_google_credentials_status():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate the generation cost in USD."""
        # Lyria 3 Pro is a flat $0.08 per generation request
        return 0.08

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the music generation tool using the Google GenAI SDK."""
        if not self._get_google_credentials_status():
            return ToolResult(
                success=False,
                error="No Google credentials configured. " + self.install_instructions,
            )

        start = time.time()

        try:
            import requests
            from google.genai import types
            from tools.google_credentials import get_genai_client, GOOGLE_API_TIMEOUT_MS

            http_options = types.HttpOptions(timeout=GOOGLE_API_TIMEOUT_MS)
            client = get_genai_client(http_options=http_options)
        except ImportError as e:
            return ToolResult(
                success=False,
                error=f"Failed to import required Google libraries: {e}. Run 'uv pip install google-genai requests'",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to initialize Google GenAI Client: {e}",
            )

        prompt = inputs["prompt"]
        duration = float(inputs.get("duration_seconds", 30))
        auto_fix = inputs.get("auto_fix", True)
        output_path = inputs.get("output_path", "music_output.mp3")

        # Ensure minimum duration of 5 seconds
        if duration < 5:
            if auto_fix:
                import logging

                logging.getLogger(__name__).warning(
                    "Lyria 3 Pro requires a minimum duration of 5 seconds. Coercing duration_seconds to 5.0."
                )
                duration = 5.0
            else:
                return ToolResult(
                    success=False,
                    error="lyria-3-pro-preview minimum duration is 5 seconds.",
                )

        # Cap at 184 seconds
        if duration > 184:
            if auto_fix:
                import logging

                logging.getLogger(__name__).warning(
                    "Lyria 3 Pro supports up to 184 seconds of audio. Coercing duration_seconds to 184."
                )
                duration = 184.0
            else:
                return ToolResult(
                    success=False,
                    error="lyria-3-pro-preview maximum duration is 184 seconds.",
                )

        # Helper to load reference image bytes + mime type
        def _get_image_data(
            url: str | None, path: str | None
        ) -> tuple[str, str] | None:
            if path:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Local reference image not found: {path}")
                img_bytes = Path(path).read_bytes()
                mime, _ = mimetypes.guess_type(path)
                if not mime:
                    mime = "image/png"
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                return b64, mime
            if url:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                mime = resp.headers.get("Content-Type")
                if not mime or "image" not in mime:
                    mime = "image/png"
                b64 = base64.b64encode(resp.content).decode("utf-8")
                return b64, mime
            return None

        # Build payload input incorporating target duration instructions
        timed_prompt = f"{prompt}\n\n[Target Duration: {int(duration)} seconds]"
        input_list: list[dict[str, Any]] = [{"type": "text", "text": timed_prompt}]
        try:
            image_data = _get_image_data(
                inputs.get("image_url"), inputs.get("image_path")
            )
            if image_data:
                b64, mime = image_data
                input_list.append({"type": "image", "mime_type": mime, "data": b64})
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to load visual conditioning image: {e}",
            )

        model_name = "lyria-3-pro-preview"

        try:
            # Create parent dirs if needed
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            interaction = client.interactions.create(model=model_name, input=input_list)

            if hasattr(interaction, "status") and interaction.status in (
                "failed",
                "cancelled",
            ):
                return ToolResult(
                    success=False,
                    error=f"Google Lyria music generation failed. Status: {interaction.status}",
                )

            audio_data = None
            if hasattr(interaction, "output_audio") and interaction.output_audio:
                audio_data = getattr(interaction.output_audio, "data", None)

            # Fall back to outputs list
            outputs = getattr(interaction, "outputs", None)
            if not audio_data and isinstance(outputs, list):
                for output in outputs:
                    if hasattr(output, "inline_data") and output.inline_data:
                        audio_data = getattr(output.inline_data, "data", None)
                        if audio_data:
                            break

            # Fall back to step traversal
            steps = getattr(interaction, "steps", None)
            if not audio_data and isinstance(steps, list):
                for step in steps:
                    if (
                        hasattr(step, "type")
                        and step.type == "model_output"
                        and hasattr(step, "content")
                        and step.content
                    ):
                        for content_part in step.content:
                            if (
                                hasattr(content_part, "type")
                                and content_part.type == "audio"
                            ):
                                audio_data = getattr(content_part, "data", None)
                                break
                        if audio_data:
                            break

            if not audio_data:
                return ToolResult(
                    success=False,
                    error=f"No audio data returned by model {model_name}.",
                )

            # Decode and save output file
            if isinstance(audio_data, str):
                audio_bytes = base64.b64decode(audio_data)
            else:
                # If it's already bytes, it could be raw audio or base64 bytes
                if audio_data.startswith(b"ID3") or (
                    len(audio_data) > 2
                    and audio_data[0] == 0xFF
                    and (audio_data[1] & 0xE0) == 0xE0
                ):
                    audio_bytes = audio_data
                else:
                    try:
                        audio_bytes = base64.b64decode(audio_data)
                    except Exception:
                        audio_bytes = audio_data

            Path(output_path).write_bytes(audio_bytes)

        except Exception as e:
            return ToolResult(
                success=False, error=f"Google Lyria music generation failed: {e}"
            )

        duration_seconds = round(time.time() - start, 2)
        cost_usd = self.estimate_cost(inputs)

        return ToolResult(
            success=True,
            data={
                "provider": "google",
                "model": model_name,
                "prompt": prompt,
                "duration_seconds": duration,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp3",
            },
            artifacts=[str(output_path)],
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
            model=model_name,
        )
