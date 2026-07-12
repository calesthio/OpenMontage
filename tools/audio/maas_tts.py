"""DolphinLitePark MaaS platform TTS tool.

POST /v1/audio/speech — Gateway handles all provider differences, but NOT
uniformly: per docs/multimodal-call-guide-v4.md, leapfast/indextts is an
ASYNC job (the POST returns {"id": ..., "status": "processing"} immediately;
the actual WAV only appears after polling GET /v1/audio/jobs/{id} to
"succeeded" and downloading GET /v1/audio/jobs/{id}/result). This tool used
to always stream the raw POST response straight to disk regardless of
model — for indextts (this tool's own DEFAULT_MODEL) that meant writing the
small `{"id":...,"status":"processing"}` JSON envelope to disk *as if it
were the WAV file*, not the actual audio. cosyvoice-v3.5-flash and
qwen3-tts-flash aren't covered by this doc, so their request shape is left
as direct/synchronous — unconfirmed either way, but no evidence of a bug.

Models available (2026-06-28):
  leapfast/indextts       — Self-hosted IndexTTS on H100, Chinese+English, free, ASYNC
  cosyvoice-v3.5-flash — DashScope CosyVoice, Chinese multi-speaker, free
  qwen3-tts-flash     — DashScope Qwen3 TTS, ¥1.60/M tokens

Voice map for leapfast/indextts (OpenAI names work too):
  alloy   → zh_female_intellectual   (知性女声)
  echo    → zh_male_broadcaster      (播音男声)
  fable   → zh_female_youthful       (青春女声)
  onyx    → zh_male_deep             (浑厚男声)
  nova    → zh_female_warm           (温暖女声)
  shimmer → zh_female_soothing       (舒缓女声)
  Or pass an IndexTTS native voice name directly.

IndexTTS V3 emotion params (leapfast/indextts only — see input_schema):
  emo_alpha, use_emo_text, emo_text, interval_silence.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.maas_base import MaasBaseTool


class MaasTTS(MaasBaseTool):
    name = "maas_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "maas"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MAAS_API_KEY"]
    install_instructions = (
        "Set MAAS_API_KEY to your DolphinLitePark API key (sk-dlp-...).\n"
        "Optionally set MAAS_API_BASE to override the gateway URL\n"
        "(default: https://api.aiapbot.com)."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "text_to_speech": True,
        "multilingual": True,
        "chinese": True,
        "english": True,
        "voice_cloning": False,
        "offline": False,
        "streaming": False,
    }
    best_for = [
        "Chinese narration — IndexTTS H100 is optimized for Mandarin",
        "internal MaaS quota — no external TTS billing",
        "fast synthesis: leapfast/indextts and cosyvoice-v3.5-flash are free-tier",
    ]
    not_good_for = [
        "voice cloning",
        "offline / air-gapped environments",
    ]
    fallback_tools = ["elevenlabs_tts", "openai_tts", "piper_tts"]

    # TTS models on MaaS (sourced 2026-06-28)
    MODELS = {
        "leapfast/indextts":        {"lang": "zh+en", "price": "free",           "format": "wav"},
        "cosyvoice-v3.5-flash": {"lang": "zh",    "price": "free",           "format": "mp3"},
        "qwen3-tts-flash":      {"lang": "zh+en", "price": "¥1.60/M tokens", "format": "mp3"},
    }
    DEFAULT_MODEL = "leapfast/indextts"

    # OpenAI voice → IndexTTS native voice index
    VOICE_MAP = {
        "alloy":   "zh_female_intellectual",
        "echo":    "zh_male_broadcaster",
        "fable":   "zh_female_youthful",
        "onyx":    "zh_male_deep",
        "nova":    "zh_female_warm",
        "shimmer": "zh_female_soothing",
    }
    DEFAULT_VOICE = "alloy"

    # Only leapfast/indextts is confirmed async by docs/multimodal-call-guide-v4.md.
    _ASYNC_MODELS = {"leapfast/indextts"}

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize"},
            "model": {
                "type": "string",
                "description": (
                    "TTS model. Options: leapfast/indextts (default, free, zh+en), "
                    "cosyvoice-v3.5-flash (free, zh), qwen3-tts-flash (¥1.60/M tok, zh+en)"
                ),
                "default": "leapfast/indextts",
            },
            "voice": {
                "type": "string",
                "description": (
                    "Voice name. OpenAI names (alloy/echo/fable/onyx/nova/shimmer) are "
                    "auto-mapped to IndexTTS voices. Or pass a native voice index directly."
                ),
                "default": "alloy",
            },
            "format": {
                "type": "string",
                "enum": ["mp3", "wav"],
                "default": "mp3",
                "description": "Output audio format (leapfast/indextts defaults to wav)",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "description": "Speech rate (1.0 = normal)",
            },
            "emo_alpha": {
                "type": "number",
                "default": 1.0,
                "description": (
                    "leapfast/indextts only (V3). Emotion intensity, 0.0 (flat) to 1.0 "
                    "(strongest). 0.0 is a valid, meaningful value — do not treat as unset."
                ),
            },
            "use_emo_text": {
                "type": "boolean",
                "default": False,
                "description": "leapfast/indextts only (V3). Enable emo_text emotion guidance.",
            },
            "emo_text": {
                "type": "string",
                "description": "leapfast/indextts only (V3). Free-text emotion cue, e.g. 'excited', 'whispering'. Requires use_emo_text=true.",
            },
            "interval_silence": {
                "type": "integer",
                "default": 200,
                "description": "leapfast/indextts only (V3). Inter-sentence pause in milliseconds, 0-2000.",
            },
            "output_path": {"type": "string", "description": "Local path to save audio file"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=20, network_required=True
    )
    # Declarative only — execute() doesn't wrap the submit call with retries
    # honoring this policy; it hand-rolls its own poll-retry tolerance instead
    # (see _MAX_POLL_ERRORS below). Same is true of every other API tool in
    # this codebase today.
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["text", "model", "voice", "format"]
    side_effects = ["writes audio file to output_path", "calls MaaS gateway API"]
    user_visible_verification = ["Listen to generated audio for clarity and tone"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Return estimated cost in CNY (not USD — MaaS bills internally in CNY).

        leapfast/indextts and cosyvoice-v3.5-flash are free. qwen3-tts-flash
        is priced at ¥1.60/M tokens per docs/multimodal-call-guide-v4.md;
        there's no tokenizer available here, so approximate token count from
        the input text's character length (the same rough char-based
        heuristic estimate_runtime already uses below).
        """
        model = inputs.get("model", self.DEFAULT_MODEL)
        if model == "qwen3-tts-flash":
            tokens = len(inputs.get("text", ""))
            return round(tokens / 1_000_000 * 1.60, 6)
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        chars = len(inputs.get("text", ""))
        return max(5.0, chars / 20)  # rough: ~20 chars/s synthesis speed

    def _build_payload(self, inputs: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Build the /v1/audio/speech payload. Returns (payload, resolved_format)."""
        model = inputs.get("model", self.DEFAULT_MODEL)
        voice = inputs.get("voice", self.DEFAULT_VOICE)
        fmt = inputs.get("format", "mp3")
        text = inputs["text"]

        # OpenAI-style voice names are only meaningful as IndexTTS native
        # voice IDs (see VOICE_MAP above) — .get() falls back to the raw
        # value unchanged, so a caller passing an already-native voice ID
        # (or a voice name for a different model) still works.
        if model == "leapfast/indextts":
            voice = self.VOICE_MAP.get(voice, voice)

        # leapfast/indextts native format is WAV; honour caller's preference otherwise
        if model == "leapfast/indextts" and fmt == "mp3":
            fmt = "wav"

        payload: dict[str, Any] = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": fmt,
        }
        if inputs.get("speed") and inputs["speed"] != 1.0:
            payload["speed"] = inputs["speed"]

        if model == "leapfast/indextts":
            # V3 emotion/pause params — indextts-specific, per
            # docs/multimodal-call-guide-v4.md. emo_alpha=0.0 is a valid,
            # meaningful value (flattest delivery), so this must be an
            # `is not None` check, not a truthy one, or a caller deliberately
            # asking for a flat reading would silently get the default instead.
            if inputs.get("emo_alpha") is not None:
                payload["emo_alpha"] = inputs["emo_alpha"]
            # A caller who sets emo_text without also setting use_emo_text is
            # clearly asking for emotion-guided synthesis — auto-enable it
            # rather than silently dropping their emo_text.
            if inputs.get("use_emo_text") or inputs.get("emo_text"):
                payload["use_emo_text"] = True
                if inputs.get("emo_text"):
                    payload["emo_text"] = inputs["emo_text"]
            if inputs.get("interval_silence") is not None:
                payload["interval_silence"] = inputs["interval_silence"]

        return payload, fmt

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MAAS_API_KEY not set. " + self.install_instructions,
            )

        model = inputs.get("model", self.DEFAULT_MODEL)
        voice = inputs.get("voice", self.DEFAULT_VOICE)
        text = inputs["text"]
        payload, fmt = self._build_payload(inputs)

        output_path = Path(inputs.get("output_path", f"maas_tts_{int(time.time())}.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        start = time.time()
        if model in self._ASYNC_MODELS:
            try:
                submit = requests.post(
                    f"{self._base_url()}/v1/audio/speech",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                submit.raise_for_status()
            except Exception as e:
                return ToolResult(success=False, error=f"MaaS TTS submit failed: {e}")

            job_id = submit.json().get("id")
            if not job_id:
                return ToolResult(
                    success=False,
                    error=f"No job id in MaaS TTS submit response: {submit.json()}",
                )

            deadline = start + 60
            # Job is already submitted/billed — tolerate transient poll blips,
            # but cap them so a persistently broken poll endpoint fails fast
            # instead of spinning until the deadline (mirrors maas_video.py).
            poll_errors = 0
            _MAX_POLL_ERRORS = 5
            while time.time() < deadline:
                time.sleep(2)
                try:
                    poll = requests.get(
                        f"{self._base_url()}/v1/audio/jobs/{job_id}",
                        headers=headers,
                        timeout=15,
                    )
                    poll.raise_for_status()
                except Exception as e:
                    poll_errors += 1
                    if poll_errors >= _MAX_POLL_ERRORS:
                        return ToolResult(
                            success=False,
                            error=f"MaaS TTS poll failed {poll_errors}x (last: {e}); job_id={job_id}",
                        )
                    continue  # transient — retry on the next interval
                poll_errors = 0
                status = poll.json().get("status", "unknown")
                if status == "succeeded":
                    break
                if status in ("failed", "cancelled"):
                    return ToolResult(success=False, error=f"MaaS TTS job {status}: {poll.json()}")
            else:
                return ToolResult(success=False, error=f"MaaS TTS job timed out (job_id={job_id})")

            try:
                dl = requests.get(
                    f"{self._base_url()}/v1/audio/jobs/{job_id}/result",
                    headers=headers,
                    stream=True,
                    timeout=60,
                )
                dl.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as e:
                return ToolResult(success=False, error=f"MaaS TTS download failed: {e}")
        else:
            try:
                resp = requests.post(
                    f"{self._base_url()}/v1/audio/speech",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=120,
                )
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as e:
                return ToolResult(success=False, error=f"MaaS TTS failed: {e}")

        # Probe duration if possible
        audio_duration = None
        try:
            from tools.analysis.audio_probe import probe_duration
            audio_duration = probe_duration(output_path)
        except Exception:
            pass

        return ToolResult(
            success=True,
            data={
                "provider": "maas",
                "model": model,
                "voice": voice,
                "format": fmt,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "output_path": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),   # CNY; 0.0 for the free MaaS TTS models
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
