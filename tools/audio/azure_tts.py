"""Azure AI Speech text-to-speech provider tool.

Neural TTS served by Azure AI Speech via the REST v1 endpoint. This is an
optional cloud TTS provider; when ``AZURE_SPEECH_KEY`` + ``AZURE_SPEECH_REGION``
are configured the agent may prefer it for high-quality narration, while the
local ``piper_tts`` tool remains the default offline path.

Shares the same Speech resource credentials as the ``azure_stt`` transcription
tool (one key/region unlocks both directions). Uses the synchronous
``/cognitiveservices/v1`` endpoint with an SSML body — no token exchange, Blob
storage, or job polling required.

Docs: https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Output format tokens keyed by container. Chosen for compositing quality.
_MP3_FORMAT = "audio-48khz-192kbitrate-mono-mp3"
_WAV_FORMAT = "riff-48khz-16bit-mono-pcm"


class AzureTTS(BaseTool):
    name = "azure_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "azure"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    # Azure neural TTS is effectively deterministic for a fixed voice + SSML.
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    # Availability is decided by get_status() (env var check), mirroring the
    # azure_stt and elevenlabs_tts provider tools — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set your Azure AI Speech credentials (same resource as azure_stt):\n"
        "  export AZURE_SPEECH_KEY=your_speech_resource_key\n"
        "  export AZURE_SPEECH_REGION=eastus   # your Speech resource region\n"
        "Create a Speech resource in the Azure portal "
        "(https://portal.azure.com) — the key and region are on its "
        "'Keys and Endpoint' page. Optionally set AZURE_TTS_ENDPOINT to a full "
        "custom TTS host (e.g. https://<region>.tts.speech.microsoft.com)."
    )
    fallback = "piper_tts"
    fallback_tools = ["elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["azure-text-to-speech", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "ssml_support",
        "prosody_control",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "high-quality neural narration on Azure credentials",
        "calm, confident explainer / founder-register delivery",
        "cloud TTS that shares one key with azure_stt",
    ]
    not_good_for = [
        "fully offline production (use piper_tts)",
        "voice cloning (use elevenlabs_tts)",
    ]

    # A small curated shortlist of expressive en-US neural voices. Any valid
    # Azure voice short name may be passed via `voice`.
    RECOMMENDED_VOICES = {
        "andrew": "en-US-AndrewMultilingualNeural",  # warm, confident, conversational (founder)
        "brandon": "en-US-BrandonMultilingualNeural",  # deeper, measured
        "ava": "en-US-AvaMultilingualNeural",  # confident, bright female
        "guy": "en-US-GuyNeural",  # authoritative
        "jenny": "en-US-JennyNeural",  # friendly, clear
    }
    DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "description": (
                    "Azure voice short name (e.g. 'en-US-AndrewMultilingualNeural') "
                    "or a shortlist alias: andrew, brandon, ava, guy, jenny. "
                    "Default: en-US-AndrewMultilingualNeural."
                ),
            },
            "rate": {
                "type": "string",
                "description": (
                    "SSML prosody rate, e.g. '-8%', '0%', '+5%', or 'slow'/'medium'. "
                    "Default '0%'."
                ),
                "default": "0%",
            },
            "pitch": {
                "type": "string",
                "description": "SSML prosody pitch, e.g. '-2st', '0%', '+1st'. Default '0%'.",
                "default": "0%",
            },
            "style": {
                "type": "string",
                "description": (
                    "Optional express-as style for voices that support it "
                    "(e.g. 'narration-professional', 'calm', 'newscast'). Omit for neutral."
                ),
            },
            "locale": {
                "type": "string",
                "default": "en-US",
                "description": "BCP-47 locale for the SSML <speak> element.",
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "enum": ["mp3", "wav"],
                "default": "mp3",
                "description": "Container: 48kHz 192kbit mp3 or 48kHz 16-bit PCM wav.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "voice": {"type": "string"},
            "output": {"type": "string"},
            "format": {"type": "string"},
            "text_length": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        retryable_errors=["ConnectionError", "Timeout", "429", "503"],
    )
    idempotency_key_fields = ["text", "voice", "rate", "pitch", "style", "output_format"]
    side_effects = ["writes audio file to output_path", "sends text to Azure AI Speech"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    # Azure neural TTS Standard tier bills roughly $16 per 1M characters.
    COST_PER_CHAR = 16.0 / 1_000_000

    def get_status(self) -> ToolStatus:
        if os.environ.get("AZURE_SPEECH_KEY") and (
            os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("AZURE_TTS_ENDPOINT")
        ):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(len(inputs.get("text", "")) * self.COST_PER_CHAR, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Well under real-time for typical narration segments.
        return 10.0

    def _host(self) -> str:
        endpoint = os.environ.get("AZURE_TTS_ENDPOINT")
        if endpoint:
            return endpoint.rstrip("/")
        region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
        return f"https://{region}.tts.speech.microsoft.com"

    def _resolve_voice(self, inputs: dict[str, Any]) -> str:
        voice = (inputs.get("voice") or "").strip()
        if not voice:
            return self.DEFAULT_VOICE
        return self.RECOMMENDED_VOICES.get(voice.lower(), voice)

    def _build_ssml(self, inputs: dict[str, Any], voice: str) -> str:
        locale = inputs.get("locale", "en-US")
        rate = inputs.get("rate", "0%")
        pitch = inputs.get("pitch", "0%")
        style = inputs.get("style")
        text = escape(inputs["text"])

        inner = f'<prosody rate="{escape(rate)}" pitch="{escape(pitch)}">{text}</prosody>'
        if style:
            inner = (
                f'<mstts:express-as style="{escape(style)}">{inner}</mstts:express-as>'
            )
        return (
            f'<speak version="1.0" '
            f'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" '
            f'xml:lang="{locale}">'
            f'<voice name="{voice}">{inner}</voice></speak>'
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("AZURE_SPEECH_KEY")
        if not api_key or not (
            os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("AZURE_TTS_ENDPOINT")
        ):
            return ToolResult(
                success=False,
                error="Azure Speech is not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._synthesize(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _synthesize(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        voice = self._resolve_voice(inputs)
        container = inputs.get("output_format", "mp3")
        azure_format = _WAV_FORMAT if container == "wav" else _MP3_FORMAT
        ext = "wav" if container == "wav" else "mp3"

        ssml = self._build_ssml(inputs, voice)
        url = f"{self._host()}/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": azure_format,
            "User-Agent": "OpenMontage-azure-tts",
        }

        try:
            response = requests.post(
                url, headers=headers, data=ssml.encode("utf-8"), timeout=120
            )
        except requests.RequestException as exc:
            return ToolResult(success=False, error=f"Azure TTS request failed: {exc}")

        if response.status_code != 200:
            detail = response.text[:500] if response.text else ""
            return ToolResult(
                success=False,
                error=f"Azure TTS returned HTTP {response.status_code}: {detail}",
            )

        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": azure_format,
            },
            artifacts=[str(output_path)],
            model=f"azure-neural-tts:{voice}",
        )
