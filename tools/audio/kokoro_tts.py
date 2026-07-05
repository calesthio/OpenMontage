"""Kokoro local text-to-speech provider (free, CPU-capable, near-ElevenLabs quality).

Kokoro-82M (Apache 2.0) is a tiny, fast, natural-sounding TTS model. It runs on
CPU (no GPU required) at a fraction of realtime, so bulk/draft narration costs
$0 — reserve ElevenLabs for hero voiceover the audience scrutinizes.

Dependency-gated like piper_tts: reports UNAVAILABLE until the `kokoro` package
is installed, so it never disturbs existing flows — it joins the tts menu (via
tts_selector auto-discovery) once present.

    pip install kokoro soundfile   # plus espeak-ng on some platforms

The exact KPipeline call varies slightly across kokoro releases; it is isolated
in `_synthesize` and marked `ponytail:` as the one knob to confirm against the
installed version. WAV assembly (`_write_wav`) is stdlib-only and needs no model.
"""

from __future__ import annotations

import importlib.util
import struct
import time
import wave
from pathlib import Path
from typing import Any, Iterable

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

_SAMPLE_RATE = 24000  # Kokoro emits 24 kHz mono


class KokoroTTS(BaseTool):
    name = "kokoro_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kokoro"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL  # CPU-capable — no GPU required

    dependencies = ["py:kokoro"]
    install_instructions = (
        "Install Kokoro (Apache 2.0, ~free local TTS):\n"
        "  pip install kokoro soundfile\n"
        "On some platforms also install espeak-ng (phonemizer backend):\n"
        "  macOS: brew install espeak-ng   |   Debian/Ubuntu: apt install espeak-ng"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
    }
    # best_for signals the cheap/bulk lane to the scorer (draft tier routes here).
    best_for = [
        "free local narration at scale",
        "bulk and draft voiceover",
        "natural offline text-to-speech",
        "privacy-sensitive local-only workflows",
    ]
    not_good_for = [
        "voice clone matching a specific person",
        "the last 5% of expressive range for hero voiceover",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice_id": {
                "type": "string",
                "default": "af_heart",
                "description": "Kokoro voice, e.g. af_heart, af_bella, am_michael, bf_emma.",
            },
            "lang_code": {
                "type": "string",
                "default": "a",
                "description": "Kokoro language: a=American, b=British English, and others.",
            },
            "speed": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 2.0,
                "default": 1.0,
                "description": "Speaking rate multiplier.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=350, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "voice_id", "lang_code", "speed"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for intelligibility and prosody"]

    def get_status(self) -> ToolStatus:
        if importlib.util.find_spec("kokoro") is not None:
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # free local

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # ~1 char ≈ 60ms of speech; CPU runs a few× faster than realtime.
        chars = len(inputs.get("text", "") or "")
        return round(max(1.0, chars * 0.06 * 0.4), 1)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Kokoro TTS not available. " + self.install_instructions)
        if not (inputs.get("text") or "").strip():
            return ToolResult(success=False, error="kokoro_tts: 'text' is required and must be non-empty.")

        start = time.time()
        voice = inputs.get("voice_id") or "af_heart"
        lang = inputs.get("lang_code") or "a"
        speed = float(inputs.get("speed", 1.0) or 1.0)

        try:
            samples = self._synthesize(inputs["text"], voice, lang, speed)
        except Exception as exc:  # noqa: BLE001 - surface synth failure to the agent
            return ToolResult(success=False, error=f"Kokoro synthesis failed: {exc}")

        if not samples:
            return ToolResult(success=False, error="Kokoro produced no audio for the given text.")

        output_path = Path(inputs.get("output_path", "kokoro_tts.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(samples, output_path, _SAMPLE_RATE)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice_id": voice,
                "lang_code": lang,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
                "sample_rate": _SAMPLE_RATE,
            },
            artifacts=[str(output_path)],
            model="kokoro-82m",
            duration_seconds=round(time.time() - start, 2),
        )

    # ---- synthesis (model) ----

    @staticmethod
    def _synthesize(text: str, voice: str, lang_code: str, speed: float) -> list[float]:
        """Run Kokoro and return a flat list of float samples in [-1, 1].

        ponytail: the KPipeline surface shifts a little between kokoro releases —
        this is the one spot to confirm against the installed version. Everything
        downstream (WAV assembly) is version-agnostic stdlib.
        """
        from kokoro import KPipeline  # imported lazily; presence gated in get_status

        pipeline = KPipeline(lang_code=lang_code)
        samples: list[float] = []
        for _graphemes, _phonemes, audio in pipeline(text, voice=voice, speed=speed):
            if audio is None:
                continue
            # torch tensor or numpy array -> python floats, without a hard dep here.
            samples.extend(audio.tolist() if hasattr(audio, "tolist") else list(audio))
        return samples

    # ---- WAV writing (stdlib, model-free, testable) ----

    @staticmethod
    def _write_wav(samples: Iterable[float], path: Path, rate: int = _SAMPLE_RATE) -> None:
        """Write mono 16-bit PCM WAV from float samples in [-1, 1]."""
        ints = [max(-32768, min(32767, int(s * 32767))) for s in samples]
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(struct.pack("<%dh" % len(ints), *ints))
