"""Edge-TTS provider: free online TTS via Microsoft Edge TTS service.

No API key required. Uses the same service powering Microsoft Edge's
"Read Aloud" feature, providing natural-sounding Chinese voices.

Warning: This is a free experimental online workflow, not an official
production SLA-backed API. For formal publishing, prefer manual voiceover,
Doubao, Google TTS, Azure TTS, ElevenLabs, or OpenAI TTS depending on
budget and usage rights.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

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


class EdgeTTS(BaseTool):
    name = "edge_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "edge_tts"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["python:edge-tts"]
    install_instructions = (
        "Install edge-tts:\n"
        "  pip install edge-tts\n"
        "\n"
        "No API key required. edge-tts uses Microsoft Edge's free TTS service.\n"
        "\n"
        "Recommended Chinese voices:\n"
        "  zh-CN-XiaoxiaoNeural  (female, default)\n"
        "  zh-CN-YunxiNeural     (male)\n"
        "  zh-CN-XiaoyiNeural    (female, expressive)\n"
        "  zh-HK-HiuGaaiNeural   (Cantonese, female)"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "multilingual",
        "subtitle_output",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "subtitles": True,
    }
    best_for = [
        "free Chinese voiceover for MVP/testing",
        "no-API-key Chinese narration",
        "quick prototyping with natural voices",
    ]
    not_good_for = [
        "production SLA-backed publishing",
        "best-in-class expressive voice quality",
        "fully offline production",
        "voice clone matching",
    ]
    fallback_tools = ["doubao_tts", "google_tts", "openai_tts", "piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "default": "zh-CN-XiaoxiaoNeural",
                "description": "Edge TTS voice name (e.g. zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural)",
            },
            "rate": {
                "type": "string",
                "default": "+0%",
                "description": "Speaking rate adjustment (e.g. +0%, -20%, +50%)",
            },
            "volume": {
                "type": "string",
                "default": "+0%",
                "description": "Volume adjustment (e.g. +0%, -50%, +100%)",
            },
            "pitch": {
                "type": "string",
                "default": "+0Hz",
                "description": "Pitch adjustment (e.g. +0Hz, -50Hz, +100Hz)",
            },
            "output_path": {
                "type": "string",
                "description": "Path for the generated MP3 file",
            },
            "subtitle_path": {
                "type": "string",
                "description": "Optional path for SRT subtitle output",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "subtitle_path": {"type": "string"},
            "voice": {"type": "string"},
            "rate": {"type": "string"},
            "text_length": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["timeout", "connection", "rate_limit"],
    )
    idempotency_key_fields = ["text", "voice", "rate", "volume", "pitch"]
    side_effects = [
        "writes audio file to output_path",
        "calls Microsoft Edge TTS service (free, no API key)",
    ]
    user_visible_verification = [
        "Listen to generated audio for Mandarin naturalness and pacing",
        "Check subtitle timing if subtitle_path was provided",
    ]
    quality_score = 0.75

    def get_status(self) -> ToolStatus:
        try:
            import edge_tts  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="edge-tts not installed. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = asyncio.run(self._generate(inputs))
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Edge TTS failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    async def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        import edge_tts

        text = inputs["text"]
        voice = inputs.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = inputs.get("rate", "+0%")
        volume = inputs.get("volume", "+0%")
        pitch = inputs.get("pitch", "+0Hz")
        output_path = Path(inputs.get("output_path", "edge_tts_output.mp3"))
        subtitle_path = inputs.get("subtitle_path")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            boundary="WordBoundary",
        )

        if subtitle_path:
            sub_path = Path(subtitle_path)
            sub_path.parent.mkdir(parents=True, exist_ok=True)
            sub_maker = edge_tts.SubMaker()
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
                elif chunk["type"] == "WordBoundary":
                    sub_maker.feed(chunk)
            output_path.write_bytes(audio_data)
            srt_content = sub_maker.get_srt()
            if srt_content:
                sub_path.write_text(srt_content, encoding="utf-8")
            artifacts = [str(output_path), str(sub_path)]
        else:
            await communicate.save(str(output_path))
            artifacts = [str(output_path)]

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice,
                "rate": rate,
                "volume": volume,
                "pitch": pitch,
                "text_length": len(text),
                "output": str(output_path),
                "subtitle_path": str(subtitle_path) if subtitle_path else None,
            },
            artifacts=artifacts,
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        msg = str(exc)
        if "TTS request failed" in msg and "caused by ConnectorError" in msg:
            return "Network error: cannot reach Edge TTS service. Check internet connection."
        if "connect" in msg.lower() and "fail" in msg.lower():
            return "Connection failed: Edge TTS service unreachable. Check internet/proxy."
        if "timeout" in msg.lower():
            return "Request timed out. The text may be too long or the service is slow."
        return msg
