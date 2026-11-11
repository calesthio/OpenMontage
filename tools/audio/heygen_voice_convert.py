"""Timing-preserving HeyGen voice conversion; separate from realtime conversation."""

import base64
import mimetypes
from pathlib import Path
import requests
from tools.audio._speech_api import SpeechAPI


class HeyGenVoiceConvert(SpeechAPI):
    name = "heygen_voice_convert"
    capability = "voice_conversion"
    provider = "heygen"
    credential = "HEYGEN_API_KEY"
    dependencies = ["env:HEYGEN_API_KEY"]
    install_instructions = (
        "Configure HEYGEN_API_KEY; use an ACTIVE workspace instant voice."
    )
    capabilities = ["speech_to_speech"]
    input_schema = {
        "type": "object",
        "required": ["voice_id"],
        "properties": {
            "voice_id": {"type": "string", "minLength": 1},
            "audio_path": {"type": "string"},
            "audio_url": {"type": "string", "pattern": "^https://"},
            "asset_id": {"type": "string"},
            "remove_background_noise": {"type": "boolean"},
            "seed": {"type": "integer", "minimum": 0, "maximum": 4294967295},
            "idempotency_key": {
                "type": "string",
                "pattern": "^[A-Za-z0-9_:.-]{1,255}$",
            },
            "output_path": {"type": "string"},
        },
    }

    def generate(self, inputs, key):
        sources = [k for k in ("audio_path", "audio_url", "asset_id") if inputs.get(k)]
        if len(sources) != 1:
            raise ValueError("Supply exactly one audio_path, audio_url or asset_id")
        if sources[0] == "audio_path":
            p = Path(inputs["audio_path"])
            if not 0 < p.stat().st_size <= 16 * 1024 * 1024:
                raise ValueError("Inline audio must be nonempty and at most 16 MB")
            audio = {
                "type": "base64",
                "media_type": mimetypes.guess_type(p)[0] or "audio/wav",
                "data": base64.b64encode(p.read_bytes()).decode(),
            }
        elif sources[0] == "audio_url":
            audio = {"type": "url", "url": inputs["audio_url"]}
        else:
            audio = {"type": "asset_id", "asset_id": inputs["asset_id"]}
        payload = {
            "voice_id": inputs["voice_id"],
            "model_id": "heygen-voice-sts-0",
            "audio": audio,
        }
        for k in ("seed", "remove_background_noise"):
            if k in inputs:
                payload[k] = inputs[k]
        headers = {"X-Api-Key": key}
        if inputs.get("idempotency_key"):
            headers["Idempotency-Key"] = inputs["idempotency_key"]
        r = requests.post(
            "https://api.heygen.com/v3/models/audio/sts",
            headers=headers,
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()["data"]
        from tools.provider_jobs import download
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "speech.wav"
            download(data["audio_url"], p)
            content = p.read_bytes()
        return self.save_audio(
            inputs,
            content,
            model="heygen-voice-sts-0",
            suffix=".wav",
            extra={
                "audio_duration": data["duration"],
                "request_id": r.headers.get("X-Request-Id"),
            },
        )
