"""Voxtral 3 file speech synthesis via Mistral."""

import base64
from pathlib import Path
import requests
from tools.audio._speech_api import SpeechAPI


class MistralTTS(SpeechAPI):
    name = "mistral_tts"
    provider = "mistral"
    credential = "MISTRAL_API_KEY"
    dependencies = ["env:MISTRAL_API_KEY"]
    install_instructions = "Configure MISTRAL_API_KEY from https://console.mistral.ai/."
    best_for = ["Voxtral expressive narration with preset or reference voices"]
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "model_id": {
                "enum": ["voxtral-mini-tts-3-0"],
                "default": "voxtral-mini-tts-3-0",
            },
            "voice_id": {"type": "string"},
            "reference_audio_path": {"type": "string"},
            "output_format": {"enum": ["mp3", "wav", "flac", "opus"]},
            "output_path": {"type": "string"},
            "expressiveness": {"type": "number", "minimum": 1, "maximum": 5},
            "phoneme_hints": {"type": "object"},
            "conversation_history": {"type": "array", "minItems": 1},
        },
    }

    def generate(self, inputs, key):
        if bool(inputs.get("voice_id")) == bool(inputs.get("reference_audio_path")):
            raise ValueError("Supply exactly one voice_id or reference_audio_path")
        if inputs.get("conversation_history") and inputs.get("reference_audio_path"):
            raise ValueError("conversation_history requires a preset voice")
        model = inputs.get("model_id", "voxtral-mini-tts-3-0")
        fmt = inputs.get("output_format", "mp3")
        payload = {"model": model, "input": inputs["text"], "response_format": fmt}
        for k in (
            "voice_id",
            "expressiveness",
            "phoneme_hints",
            "conversation_history",
        ):
            if k in inputs:
                payload[k] = inputs[k]
        if inputs.get("reference_audio_path"):
            payload["ref_audio"] = base64.b64encode(
                Path(inputs["reference_audio_path"]).read_bytes()
            ).decode()
        r = requests.post(
            "https://api.mistral.ai/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        content = base64.b64decode(r.json()["audio_data"], validate=True)
        return self.save_audio(inputs, content, model=model, suffix="." + fmt)
