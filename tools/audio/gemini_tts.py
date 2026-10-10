"""Gemini 3.8 TTS via Interactions, separate from Cloud Text-to-Speech."""

from __future__ import annotations
import base64
import os
from pathlib import Path
from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolResult,
    ResourceProfile,
)


class GeminiTTS(BaseTool):
    name = "gemini_tts"
    capability = "tts"
    provider = "gemini"
    tier = ToolTier.VOICE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    agent_skills = ["provider-model-refresh"]
    install_instructions = "Configure Gemini credentials and google-genai >= 2.25.0."
    capabilities = ["text_to_speech", "multi_speaker"]
    supports = {"multi_speaker": True, "style_control": True}
    best_for = ["Expressive single-speaker narration and directed dialogue"]
    resource_profile = ResourceProfile(network_required=True)
    idempotency_key_fields = [
        "model_id",
        "text",
        "voice_id",
        "style",
        "turns",
        "speakers",
    ]
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["generate", "list_voices"],
                "default": "generate",
            },
            "model_id": {
                "type": "string",
                "enum": ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"],
                "default": "gemini-3.8-flash-tts",
            },
            "text": {"type": "string", "minLength": 1},
            "voice_id": {"type": "string", "default": "Kore"},
            "style": {"type": "string"},
            "turns": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["speaker", "text"],
                    "properties": {
                        "speaker": {"type": "string"},
                        "text": {"type": "string", "minLength": 1},
                        "style": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "speakers": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["speaker", "voice"],
                    "properties": {
                        "speaker": {"type": "string"},
                        "voice": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "output_path": {"type": "string"},
        },
    }

    def get_status(self):
        from tools.google_credentials import has_google_credentials

        return (
            ToolStatus.AVAILABLE if has_google_credentials() else ToolStatus.UNAVAILABLE
        )

    def estimate_cost(self, inputs):
        if inputs.get("operation") == "list_voices":
            return 0.0
        raise PriceQuoteRequired(
            "Gemini TTS requires a current token-based price quote"
        )

    def build_request(self, inputs):
        from jsonschema import validate

        validate(inputs, self.input_schema)
        if bool(inputs.get("text")) == bool(inputs.get("turns")):
            raise ValueError("Provide text or turns, exclusively")
        if inputs.get("turns"):
            speakers = inputs.get("speakers", [])
            names = [s["speaker"] for s in speakers]
            if len(set(names)) != len(names) or any(
                t["speaker"] not in names for t in inputs["turns"]
            ):
                raise ValueError(
                    "Every turn requires a unique configured speaker voice"
                )
            turns = inputs["turns"]
            speech = {"speakers": speakers}
        else:
            turns = [{"text": inputs["text"], "style": inputs.get("style", "")}]
            speech = [{"voice": inputs.get("voice_id", "Kore")}]
        content = []
        for turn in turns:
            metadata = {
                "type": "speech_metadata",
                **{k: turn[k] for k in ("speaker", "style") if turn.get(k)},
            }
            content.append(
                {"type": "text", "text": turn["text"], "annotations": [metadata]}
            )
        return {
            "model": inputs.get("model_id", "gemini-3.8-flash-tts"),
            "input": [{"type": "user_input", "content": content}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": speech},
        }

    def execute(self, inputs):
        try:
            if inputs.get("operation") == "list_voices":
                from tools.provider_jobs import request_json

                key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                if not key:
                    raise ValueError(
                        "Voice library discovery requires a Gemini API key"
                    )
                voices = request_json(
                    "GET",
                    "https://generativelanguage.googleapis.com/v1beta/voices",
                    headers={"x-goog-api-key": key},
                )
                return ToolResult(success=True, data=voices)
            path = Path(inputs.get("output_path", "gemini_tts.wav"))
            if path.suffix.lower() != ".wav":
                raise ValueError(
                    "This adapter requests WAV; output_path must end in .wav"
                )
            request = self.build_request(inputs)
            from tools.google_credentials import get_genai_client

            result = get_genai_client().interactions.create(**request)
            audio = getattr(result, "output_audio", None)
            if not audio or not getattr(audio, "data", None):
                audio = next(
                    (
                        part
                        for step in (getattr(result, "steps", None) or [])
                        if getattr(step, "type", None) == "model_output"
                        for part in (getattr(step, "content", None) or [])
                        if getattr(part, "type", None) == "audio"
                        and getattr(part, "data", None)
                    ),
                    None,
                )
            if not audio:
                raise ValueError("Gemini returned no audio")
            data = (
                base64.b64decode(audio.data)
                if isinstance(audio.data, str)
                else audio.data
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": request["model"],
                    "output": str(path),
                    "format": "wav",
                    "cost_status": "unquoted",
                },
                artifacts=[str(path)],
                cost_usd=None,
                model=request["model"],
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
