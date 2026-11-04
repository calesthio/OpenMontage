"""Inworld TTS-2 and Flash, synchronous synthesis with usage metadata."""

import base64
import os
from pathlib import Path
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
    capabilities = ["text_to_speech"]
    best_for = ["TTS-2 narration with expressive text cues"]
    resource_profile = ResourceProfile(network_required=True)
    idempotency_key_fields = ["text", "voice_id", "model_id"]
    input_schema = {
        "type": "object",
        "required": ["text", "voice_id"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "voice_id": {"type": "string", "minLength": 1},
            "model_id": {
                "type": "string",
                "enum": ["inworld-tts-2", "inworld-tts-2-flash"],
                "default": "inworld-tts-2",
            },
            "output_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs):
        chars = len(inputs.get("text", "").encode("utf-16-le")) // 2
        return (
            chars
            * (15 if inputs.get("model_id") == "inworld-tts-2-flash" else 25)
            / 1_000_000
        )

    def execute(self, inputs):
        try:
            from jsonschema import validate

            validate(inputs, self.input_schema)
            if len(inputs["text"].encode("utf-16-le")) // 2 > 2000:
                raise ValueError(
                    "Inworld synchronous TTS accepts at most 2000 UTF-16 code units; split the script"
                )
            key = os.environ["INWORLD_API_KEY"]
            model = inputs.get("model_id", "inworld-tts-2")
            result = request_json(
                "POST",
                "https://api.inworld.ai/tts/v1/voice",
                headers={"Authorization": f"Basic {key}"},
                json={
                    "text": inputs["text"],
                    "voiceId": inputs["voice_id"],
                    "modelId": model,
                    "audioConfig": {"audioEncoding": "MP3"},
                },
            )
            audio = base64.b64decode(result["audioContent"], validate=True)
            if not audio:
                raise ValueError("Empty Inworld audio")
            path = Path(inputs.get("output_path", "inworld_tts.mp3"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "output": str(path),
                    "usage": result.get("usage"),
                    "timestamps": result.get("timestampInfo"),
                    "cost_status": "estimated",
                },
                artifacts=[str(path)],
                model=model,
                cost_usd=self.estimate_cost(inputs),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
