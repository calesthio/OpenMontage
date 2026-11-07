"""Inworld TTS-2 and Flash, synchronous synthesis with usage metadata."""

import base64
import os
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolResult,
    ResourceProfile,
)
from tools.provider_jobs import request_json


class InworldTTS(BaseTool):
    name = "inworld_tts"
    provider = "inworld"
    capability = "tts"
    tier = ToolTier.VOICE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    dependencies = ["env:INWORLD_API_KEY"]
    install_instructions = (
        "Configure INWORLD_API_KEY with the Base64 credential from the Inworld Portal."
    )
    agent_skills = ["provider-model-refresh"]
    capabilities = [
        "text_to_speech",
        "multilingual",
        "word_timestamps",
        "wav_output",
    ]
    best_for = ["TTS-2 narration with expressive delivery and alignment metadata"]
    resource_profile = ResourceProfile(network_required=True)
    idempotency_key_fields = [
        "text",
        "voice_id",
        "model_id",
        "format",
        "sample_rate_hertz",
        "language",
        "delivery_mode",
        "timestamp_type",
        "apply_text_normalization",
    ]
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "voice_id": {"type": "string", "minLength": 1, "default": "Dennis"},
            "model_id": {
                "type": "string",
                "enum": ["inworld-tts-2", "inworld-tts-2-flash"],
                "default": "inworld-tts-2",
            },
            "format": {
                "type": "string",
                "enum": ["mp3", "wav"],
                "default": "mp3",
            },
            "sample_rate_hertz": {
                "type": "integer",
                "minimum": 8000,
                "maximum": 48000,
                "default": 48000,
            },
            "language": {"type": ["string", "null"]},
            "delivery_mode": {
                "type": "string",
                "enum": ["STABLE", "BALANCED", "CREATIVE"],
                "default": "BALANCED",
            },
            "timestamp_type": {
                "type": "string",
                "enum": ["TIMESTAMP_TYPE_UNSPECIFIED", "WORD", "CHARACTER"],
                "default": "WORD",
            },
            "timestamps": {"type": "boolean", "default": True},
            "apply_text_normalization": {
                "type": "string",
                "enum": ["auto", "on", "off"],
                "default": "auto",
            },
            "output_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs):
        chars = len(inputs.get("text", "").encode("utf-16-le")) // 2
        model = inputs.get("model_id") or inputs.get("model") or "inworld-tts-2"
        return (
            chars
            * (15 if model == "inworld-tts-2-flash" else 25)
            / 1_000_000
        )

    @staticmethod
    def _timestamp_type(inputs: dict[str, Any]) -> str:
        if inputs.get("timestamp_type") is not None:
            return str(inputs["timestamp_type"]).upper()
        if "timestamps" in inputs:
            return "WORD" if inputs["timestamps"] else "TIMESTAMP_TYPE_UNSPECIFIED"
        return "WORD"

    @staticmethod
    def _normalization_mode(inputs: dict[str, Any]) -> str:
        value = str(inputs.get("apply_text_normalization", "auto")).upper()
        return {
            "AUTO": "APPLY_TEXT_NORMALIZATION_UNSPECIFIED",
            "APPLY_TEXT_NORMALIZATION_UNSPECIFIED": (
                "APPLY_TEXT_NORMALIZATION_UNSPECIFIED"
            ),
            "ON": "ON",
            "OFF": "OFF",
        }.get(value, "APPLY_TEXT_NORMALIZATION_UNSPECIFIED")

    @classmethod
    def _effective_inputs(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        output_path = Path(str(inputs.get("output_path", "")))
        inferred_format = "wav" if output_path.suffix.lower() == ".wav" else "mp3"
        return {
            "text": str(inputs.get("text", "")),
            "voice_id": inputs.get("voice_id") or inputs.get("voice") or "Dennis",
            "model_id": (
                inputs.get("model_id") or inputs.get("model") or "inworld-tts-2"
            ),
            "format": str(inputs.get("format", inferred_format)).lower(),
            "sample_rate_hertz": int(inputs.get("sample_rate_hertz", 48000)),
            "language": inputs.get("language") or inputs.get("language_code"),
            "delivery_mode": str(inputs.get("delivery_mode", "BALANCED")).upper(),
            "timestamp_type": cls._timestamp_type(inputs),
            "apply_text_normalization": cls._normalization_mode(inputs),
        }

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        return super().idempotency_key(self._effective_inputs(inputs))

    def execute(self, inputs):
        try:
            from jsonschema import validate

            effective = self._effective_inputs(inputs)
            validation_inputs = {
                **inputs,
                "text": effective["text"],
                "voice_id": effective["voice_id"],
                "model_id": effective["model_id"],
                "format": effective["format"],
                "sample_rate_hertz": effective["sample_rate_hertz"],
                "language": effective["language"],
                "delivery_mode": effective["delivery_mode"],
                "timestamp_type": effective["timestamp_type"],
                "apply_text_normalization": str(
                    inputs.get("apply_text_normalization", "auto")
                ).lower(),
            }
            validate(validation_inputs, self.input_schema)
            if len(effective["text"].encode("utf-16-le")) // 2 > 2000:
                raise ValueError(
                    "Inworld synchronous TTS accepts at most 2000 UTF-16 code units; split the script"
                )
            key = os.environ["INWORLD_API_KEY"]
            encoding = "LINEAR16" if effective["format"] == "wav" else "MP3"
            audio_config = {
                "audioEncoding": encoding,
                "sampleRateHertz": effective["sample_rate_hertz"],
            }
            payload = {
                "text": effective["text"],
                "voiceId": effective["voice_id"],
                "modelId": effective["model_id"],
                "deliveryMode": effective["delivery_mode"],
                "timestampType": effective["timestamp_type"],
                "applyTextNormalization": effective["apply_text_normalization"],
                "audioConfig": audio_config,
            }
            if effective["language"]:
                payload["language"] = effective["language"]
            result = request_json(
                "POST",
                "https://api.inworld.ai/tts/v1/voice",
                headers={"Authorization": f"Basic {key}"},
                json=payload,
            )
            audio = base64.b64decode(result["audioContent"], validate=True)
            if not audio:
                raise ValueError("Empty Inworld audio")
            path = Path(
                inputs.get("output_path", f"inworld_tts.{effective['format']}")
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": effective["model_id"],
                    "voice": effective["voice_id"],
                    "format": effective["format"],
                    "output": str(path),
                    "usage": result.get("usage"),
                    "timestamps": result.get("timestampInfo"),
                    "cost_status": "estimated",
                },
                artifacts=[str(path)],
                model=effective["model_id"],
                cost_usd=self.estimate_cost(inputs),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
