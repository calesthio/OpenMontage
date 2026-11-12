"""ElevenLabs v3 speech through the MiniCut CLI (price first, then one yes)."""

from __future__ import annotations

from typing import Any

from tools.minicut_tool import APPROVAL_SCHEMA, RESUME_SCHEMA, MiniCutTool


class MiniCutTTS(MiniCutTool):
    name = "minicut_tts"
    capability = "tts"
    model = "elevenlabs-v3"
    default_output = "minicut_voice.mp3"
    agent_skills = ["elevenlabs"]

    capabilities = ["text_to_speech", "voice_selection"]
    supports = {"voice_cloning": False, "multilingual": True, "offline": False,
                "price_quote_before_run": True}
    best_for = [
        "ElevenLabs v3 narration on the same sign-in as MiniCut video, images and music",
        "paid runs that must show the price and wait for a yes",
    ]
    fallback_tools = ["piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "maxLength": 5000},
            "voice": {
                "type": "string",
                "description": "A voice name from `minicut voices elevenlabs-v3`. Empty: the model's default voice.",
            },
            "approval": APPROVAL_SCHEMA,
            "resume_job": RESUME_SCHEMA,
            "poll_timeout": {"type": "integer", "default": 900},
            "output_path": {"type": "string", "default": "minicut_voice.mp3"},
        },
    }
    idempotency_key_fields = ["text", "voice"]
    side_effects = [
        "writes an audio file to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Listen for every word said, in the chosen voice"]

    def _request(self, inputs: dict[str, Any]):
        # tts_selector passes the shared voice_id field; this model calls it voice.
        voice = inputs.get("voice") or inputs.get("voice_id")
        return inputs["text"], {"voice": voice}, []
