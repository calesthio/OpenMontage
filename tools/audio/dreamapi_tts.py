"""DreamAPI voice clone and text to speech."""

from __future__ import annotations

from tools.dreamapi_models import models_for
from tools.dreamapi_tool import DreamApiTool

_MODELS = sorted(models_for("tts"))


class DreamApiTts(DreamApiTool):
    name = "dreamapi_tts"

    def _dreamapi_concrete(self) -> None:
        return None
    capability = "tts"
    capabilities = ["text_to_speech", "voice_clone"]
    default_output = "dreamapi_voice.mp3"
    best_for = ["DreamAPI standard and pro voices", "cloned-voice speech after voice-clone returns clone_id"]
    fallback_tools = ["elevenlabs_tts", "openai_tts"]
    input_schema = {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string", "enum": _MODELS},
            "text": {"type": "string"},
            "lang": {"type": "string"},
            "audio_id": {"type": "string"},
            "clone_id": {"type": "string"},
            "voice_url": {"type": "string"},
            "output_path": {"type": "string"},
            "task_id": {"type": "string"},
        },
    }
