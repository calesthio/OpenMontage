"""Voxtral 3 recorded-file transcription with segment timestamps and speakers."""

import json
from pathlib import Path
import requests
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolResult


class MistralSTT(SpeechAPI):
    name = "mistral_stt"
    capability = "analysis"
    capabilities = ["speech_to_text", "speaker_diarization", "segment_timestamps"]
    provider = "mistral"
    credential = "MISTRAL_API_KEY"
    dependencies = ["env:MISTRAL_API_KEY"]
    install_instructions = "Configure MISTRAL_API_KEY from https://console.mistral.ai/."
    input_schema = {
        "type": "object",
        "required": ["audio_path"],
        "properties": {
            "audio_path": {"type": "string"},
            "output_path": {"type": "string"},
            "model": {
                "enum": ["voxtral-mini-transcribe-3-0", "voxtral-small-transcribe-3-0"]
            },
            "language": {"type": "string"},
            "diarize": {"type": "boolean"},
            "timestamps": {"type": "boolean"},
            "context_bias": {"type": "array", "items": {"type": "string"}},
        },
    }

    def generate(self, inputs, key):
        model = inputs.get("model", "voxtral-mini-transcribe-3-0")
        p = Path(inputs["audio_path"])
        data = [("model", model)]
        if inputs.get("language"):
            data.append(("language", inputs["language"]))
        if inputs.get("timestamps", True) or inputs.get("diarize"):
            data.append(("timestamp_granularities", "segment"))
        if inputs.get("diarize"):
            data.append(("diarize", "true"))
        data.extend(("context_bias", v) for v in inputs.get("context_bias", []))
        with p.open("rb") as audio:
            r = requests.post(
                "https://api.mistral.ai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data=data,
                files={"file": (p.name, audio)},
                timeout=600,
            )
        r.raise_for_status()
        body = r.json()
        if "text" not in body:
            raise ValueError("Transcription response has no text")
        out = Path(inputs.get("output_path") or "mistral_transcript.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf8")
        return ToolResult(
            success=True,
            data={
                **body,
                "provider": self.provider,
                "model": model,
                "output": str(out),
                "cost_status": "unquoted",
            },
            artifacts=[str(out)],
            model=model,
            cost_usd=None,
        )
