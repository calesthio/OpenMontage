"""Native HeyGen Voice speech, ordered SSE assembly and voice discovery."""

import base64
import io
import json
import time
import wave
from datetime import date
from pathlib import Path
import requests
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolResult
from tools.provider_pricing import PriceQuoteRequired


class HeyGenTTS(SpeechAPI):
    name = "heygen_tts"
    provider = "heygen"
    credential = "HEYGEN_API_KEY"
    dependencies = ["env:HEYGEN_API_KEY"]
    install_instructions = (
        "Configure HEYGEN_API_KEY from https://platform.heygen.com/api-keys."
    )
    best_for = ["HeyGen native voice narration and cloning"]
    supports = {"voice_cloning": True, "multilingual": True, "timestamps": True}
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"enum": ["generate", "list_voices"]},
            "model_id": {
                "enum": [
                    "heygen-voice-1",
                    "heygen-voice-1-turbo",
                    "heygen-voice-1-turbo-free",
                ]
            },
            "voice_id": {"type": "string", "minLength": 1},
            "voice_type": {"enum": ["public", "instant", "professional"]},
            "text": {"type": "string", "minLength": 1, "maxLength": 5000},
            "language": {"type": "string"},
            "expressiveness_boost": {"type": "number", "minimum": 0, "maximum": 1},
            "seed": {"type": "integer", "minimum": 0, "maximum": 4294967295},
            "speed": {"type": "number", "minimum": 0.75, "maximum": 1.25},
            "pitch_shift": {"type": "number", "minimum": -4, "maximum": 4},
            "pitch_variance": {"type": "number", "minimum": 0.5, "maximum": 2},
            "with_timestamps": {"type": "boolean"},
            "stream": {"type": "boolean"},
            "output_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs):
        if inputs.get(
            "model_id"
        ) == "heygen-voice-1-turbo-free" and date.today() <= date(2026, 11, 30):
            return 0.0
        raise PriceQuoteRequired(
            "HeyGen pricing requires a current quote; Turbo Free promotion ends 2026-11-30"
        )

    @staticmethod
    def _post(url, **kwargs):
        # Retry only explicit rate rejection, never an ambiguous paid timeout.
        for attempt in range(3):
            r = requests.post(url, timeout=180, **kwargs)
            if r.status_code != 429 or attempt == 2:
                r.raise_for_status()
                return r
            try:
                delay = float(r.headers.get("Retry-After", 2 ** (attempt + 1)))
            except ValueError:
                delay = 2 ** (attempt + 1)
            r.close()
            if delay > 30:
                raise ValueError(
                    f"Rate limited; retry after {delay:g} seconds with the same model"
                )
            time.sleep(max(0, delay))

    def generate(self, inputs, key):
        headers = {"X-Api-Key": key}
        if inputs.get("operation") == "list_voices":
            r = requests.get(
                "https://api.heygen.com/v3/models/audio/voices",
                headers=headers,
                params={"type": inputs.get("voice_type", "public")},
                timeout=30,
            )
            r.raise_for_status()
            return ToolResult(
                success=True, data={"voices": r.json(), "provider": self.provider}
            )
        if not inputs.get("text", "").strip() or not inputs.get("voice_id"):
            raise ValueError("text and an ACTIVE native voice_id are required")
        model = inputs.get("model_id", "heygen-voice-1")
        if inputs.get("model") and inputs["model"] != model:
            raise ValueError("Use model_id to select HeyGen Voice")
        if model.endswith("-free") and date.today() > date(2026, 11, 30):
            raise ValueError(
                "Turbo Free promotion expired; verify its terms before using a paid model"
            )
        if inputs.get("voice_type") == "professional":
            if "turbo" in model or "expressiveness_boost" in inputs:
                raise ValueError(
                    "Professional voices do not support Turbo or expressiveness_boost"
                )
        payload = {
            k: v
            for k, v in inputs.items()
            if k in self.input_schema["properties"]
            and k
            not in {"operation", "model_id", "voice_type", "stream", "output_path"}
        }
        payload["model"] = model
        streaming = inputs.get("stream", False)
        r = self._post(
            "https://api.heygen.com/v3/models/audio/tts"
            + ("/stream" if streaming else ""),
            headers=headers,
            json=payload,
            stream=streaming,
        )
        alignment = None
        try:
            if streaming:
                content, alignment = self._assemble_stream(r)
                extra = {}
            else:
                data = r.json()["data"]
                alignment = data.get("original_characters")
                from tools.provider_jobs import download
                import tempfile

                with tempfile.TemporaryDirectory() as d:
                    temp = Path(d) / "speech.wav"
                    download(data["audio_url"], temp)
                    content = temp.read_bytes()
                extra = {"audio_duration": data.get("duration")}
            if inputs.get("with_timestamps") and not alignment:
                raise ValueError("HeyGen returned no requested alignment")
            if alignment:
                from tools.audio.elevenlabs_tts import ElevenLabsTTS

                extra["word_timestamps"] = ElevenLabsTTS.words_from_alignment(
                    {
                        "characters": [c["text"] for c in alignment],
                        "character_start_times_seconds": [
                            c["start_time"] for c in alignment
                        ],
                        "character_end_times_seconds": [
                            c["end_time"] for c in alignment
                        ],
                    }
                )
            extra["request_id"] = r.headers.get("X-Request-Id")
            return self.save_audio(
                inputs,
                content,
                model=model,
                suffix=".wav",
                extra=extra,
                alignment=alignment,
            )
        finally:
            r.close()

    @staticmethod
    def _assemble_stream(response):
        parts = {}
        alignment = []
        done = False
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw == "[DONE]":
                done = True
                break
            event = json.loads(raw)
            if event.get("type") == "error":
                raise ValueError("HeyGen synthesis failed mid-stream")
            if event.get("type") == "audio":
                index = event["part_index"]
                if index in parts:
                    raise ValueError("Duplicate HeyGen audio part")
                parts[index] = base64.b64decode(event["audio"], validate=True)
            if event.get("type") == "character_alignment":
                alignment.extend(event.get("original_characters", []))
        if not done or not parts or sorted(parts) != list(range(len(parts))):
            raise ValueError("Incomplete HeyGen speech stream")
        output = io.BytesIO()
        params = None
        with wave.open(output, "wb") as writer:
            for index in sorted(parts):
                with wave.open(io.BytesIO(parts[index]), "rb") as reader:
                    current = (
                        reader.getnchannels(),
                        reader.getsampwidth(),
                        reader.getframerate(),
                    )
                    if params is None:
                        params = current
                        writer.setnchannels(params[0])
                        writer.setsampwidth(params[1])
                        writer.setframerate(params[2])
                    if current != params:
                        raise ValueError("Inconsistent WAV parts")
                    writer.writeframes(reader.readframes(reader.getnframes()))
        return output.getvalue(), alignment or None
