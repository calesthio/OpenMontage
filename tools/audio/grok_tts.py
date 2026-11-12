"""xAI narration TTS (distinct from Grok Voice realtime)."""

import base64
import requests
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolResult


class GrokTTS(SpeechAPI):
    name = "grok_tts"
    provider = "grok"
    credential = "XAI_API_KEY"
    dependencies = ["env:XAI_API_KEY"]
    install_instructions = "Configure XAI_API_KEY from https://console.x.ai/."
    supports = {"native_audio": True, "multilingual": True, "timestamps": True}
    best_for = ["Expressive xAI narration with character alignment"]
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"enum": ["generate", "list_voices"]},
            "text": {"type": "string", "minLength": 1, "maxLength": 60000},
            "voice_id": {"type": "string"},
            "language": {"type": "string"},
            "output_path": {"type": "string"},
            "output_format": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "codec": {"enum": ["mp3", "wav"]},
                    "sample_rate": {"enum": [8000, 16000, 22050, 24000, 44100, 48000]},
                    "bit_rate": {"enum": [32000, 64000, 96000, 128000, 192000]},
                },
            },
            "speed": {"type": "number", "minimum": 0.7, "maximum": 1.5},
            "optimize_streaming_latency": {"enum": [0, 1, 2]},
            "text_normalization": {"type": "boolean"},
            "with_timestamps": {"type": "boolean"},
            "replace": {"type": "object", "additionalProperties": {"type": "string"}},
        },
    }

    def generate(self, inputs, key):
        headers = {"Authorization": f"Bearer {key}"}
        if inputs.get("operation") == "list_voices":
            r = requests.get(
                "https://api.x.ai/v1/tts/voices", headers=headers, timeout=30
            )
            r.raise_for_status()
            return ToolResult(
                success=True, data={"voices": r.json(), "provider": self.provider}
            )
        if not inputs.get("text", "").strip():
            raise ValueError("text is required")
        if inputs.get("model") or inputs.get("model_id"):
            raise ValueError(
                "xAI /v1/tts does not accept a model selector; Grok Voice uses realtime_audio"
            )
        payload = {
            k: v
            for k, v in inputs.items()
            if k in self.input_schema["properties"]
            and k not in {"operation", "output_path"}
        }
        payload.setdefault("language", "auto")
        payload.setdefault("voice_id", "eve")
        fmt = payload.get("output_format", {})
        if "bit_rate" in fmt and fmt.get("codec", "mp3") != "mp3":
            raise ValueError("bit_rate is MP3-only")
        r = requests.post(
            "https://api.x.ai/v1/tts", headers=headers, json=payload, timeout=180
        )
        r.raise_for_status()
        alignment = None
        if inputs.get("with_timestamps"):
            body = r.json()
            content = base64.b64decode(body["audio"], validate=True)
            alignment = body["audio_timestamps"]
            from tools.audio.elevenlabs_tts import ElevenLabsTTS

            chars, times = alignment["graph_chars"], alignment["graph_times"]
            if len(chars) != len(times):
                raise ValueError("Invalid timestamp lengths")
            words = ElevenLabsTTS.words_from_alignment(
                {
                    "characters": chars,
                    "character_start_times_seconds": [t[0] for t in times],
                    "character_end_times_seconds": [t[1] for t in times],
                }
            )
        else:
            content = r.content
            words = None
        return self.save_audio(
            inputs,
            content,
            model="xai-tts",
            suffix="." + fmt.get("codec", "mp3"),
            alignment=alignment,
            extra={"voice_id": payload["voice_id"], "word_timestamps": words},
        )
