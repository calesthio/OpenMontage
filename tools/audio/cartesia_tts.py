"""Cartesia Sonic 3.6 synthesis."""

import os
from pathlib import Path
import requests
from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolResult,
    ResourceProfile,
)


class CartesiaTTS(BaseTool):
    name = "cartesia_tts"
    provider = "cartesia"
    capability = "tts"
    tier = ToolTier.VOICE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    dependencies = ["env:CARTESIA_API_KEY"]
    install_instructions = "Configure CARTESIA_API_KEY from the Cartesia dashboard."
    agent_skills = ["provider-model-refresh"]
    capabilities = ["text_to_speech"]
    best_for = ["Sonic 3.6 multilingual narration"]
    resource_profile = ResourceProfile(network_required=True)
    idempotency_key_fields = ["text", "voice_id", "model_id", "language", "speed"]
    input_schema = {
        "type": "object",
        "required": ["text", "voice_id"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "voice_id": {"type": "string", "minLength": 1},
            "model_id": {
                "type": "string",
                "enum": ["sonic-3.6"],
                "default": "sonic-3.6",
            },
            "language": {"type": "string"},
            "locale": {"type": "string"},
            "speed": {"type": "number", "minimum": 0.6, "maximum": 1.5},
            "output_path": {"type": "string"},
            "api_version": {
                "type": "string",
                "default": "2026-08-14",
                "enum": ["2026-08-14"],
            },
        },
    }

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired(
            "Cartesia pricing depends on the account plan; quote before generation"
        )

    def execute(self, inputs):
        try:
            from jsonschema import validate

            validate(inputs, self.input_schema)
            if (
                Path(inputs.get("output_path", "cartesia_tts.wav")).suffix.lower()
                != ".wav"
            ):
                raise ValueError("Cartesia output_path must end in .wav")
            model = inputs.get("model_id", "sonic-3.6")
            payload = {
                "model_id": model,
                "transcript": inputs["text"],
                "voice": inputs["voice_id"],
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": 44100,
                },
            }
            for k in ("language", "locale"):
                if inputs.get(k):
                    payload[k] = inputs[k]
            if "speed" in inputs:
                payload["generation_config"] = {"speed": inputs["speed"]}
            response = requests.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "Authorization": f"Bearer {os.environ['CARTESIA_API_KEY']}",
                    "Cartesia-Version": inputs.get("api_version", "2026-08-14"),
                },
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            if not response.content:
                raise ValueError("Empty Cartesia audio")
            path = Path(inputs.get("output_path", "cartesia_tts.wav"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "output": str(path),
                    "format": "wav",
                    "cost_status": "unquoted",
                },
                artifacts=[str(path)],
                cost_usd=None,
                model=model,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
