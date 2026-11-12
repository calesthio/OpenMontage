"""HeyGen catalog speech. Catalog IDs are distinct from native clone IDs."""

import json
import tempfile
from pathlib import Path
import requests
from jsonschema import validate
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolResult
from tools.provider_jobs import download


class HeyGenCatalogTTS(SpeechAPI):
    name = "heygen_catalog_tts"
    provider = "heygen"
    credential = "HEYGEN_API_KEY"
    dependencies = ["env:HEYGEN_API_KEY"]
    install_instructions = (
        "Configure HEYGEN_API_KEY; use a catalog voice from /v3/voices."
    )
    contract = json.loads(
        (
            Path(__file__).parents[1] / "provider_contracts/heygen_catalog.json"
        ).read_text()
    )
    input_schema = {
        "type": "object",
        "properties": {
            **contract["properties"],
            "output_path": {"type": "string"},
            "operation": {"enum": ["generate", "list_voices"]},
        },
    }

    def generate(self, inputs, key):
        headers = {"X-Api-Key": key}
        if inputs.get("operation") == "list_voices":
            r = requests.get(
                "https://api.heygen.com/v3/voices", headers=headers, timeout=30
            )
            r.raise_for_status()
            return ToolResult(
                success=True, data={"voices": r.json(), "provider": self.provider}
            )
        if inputs.get("output_path") and Path(
            inputs["output_path"]
        ).suffix.lower() not in {".mp3", ".wav"}:
            raise ValueError("Catalog output_path must use .mp3 or .wav")
        payload = {k: v for k, v in inputs.items() if k in self.contract["properties"]}
        validate(payload, self.contract)
        # Require an explicit engine to prevent a saved preference changing the provider.
        if not payload.get("engine"):
            raise ValueError(
                "Choose engine explicitly: starfish, heygen_voice or elevenlabs"
            )
        r = requests.post(
            "https://api.heygen.com/v3/voices/speech",
            headers=headers,
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()["data"]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audio"
            download(data["audio_url"], p)
            content = p.read_bytes()
        suffix = ".wav" if content[:4] == b"RIFF" else ".mp3"
        resolved_inputs = dict(inputs)
        if inputs.get("output_path"):
            resolved_inputs["output_path"] = str(
                Path(inputs["output_path"]).with_suffix(suffix)
            )
        return self.save_audio(
            resolved_inputs,
            content,
            model=data["engine"],
            suffix=suffix,
            extra={
                "engine": data["engine"],
                "audio_duration": data["duration"],
                "word_timestamps": data.get("word_timestamps"),
                "request_id": data.get("request_id"),
            },
        )
