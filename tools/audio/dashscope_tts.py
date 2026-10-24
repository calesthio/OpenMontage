"""DashScope (Alibaba Cloud Bailian) text-to-speech via Qwen-TTS models.

Two endpoint families are supported:

* ``qwen3-tts-*`` voices use the multimodal-generation endpoint (same shape as
  image generation) with named system voices such as "Cherry".
* ``qwen-audio-*`` and ``cosyvoice-*`` voices use the native TTS endpoint
  (``/services/audio/tts/SpeechSynthesizer``) and accept the cloned ``voice_id``
  returned by `dashscope_voice_clone`.

Both responses contain a temporary audio URL (valid ~24h) that must be
downloaded separately — unlike OpenAI TTS which returns raw audio bytes.
"""

from __future__ import annotations

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


class DashscopeTTS(BaseTool):
    name = "dashscope_tts"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/"
    )
    fallback = "piper_tts"
    fallback_tools = [
        "doubao_tts",
        "elevenlabs_tts",
        "openai_tts",
        "piper_tts",
    ]
    agent_skills = ["dashscope"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "voice_cloning",
        "voice_id_synthesis",
        "multilingual",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "natural Mandarin and multilingual narration via Qwen-TTS",
        "cost-effective TTS via Alibaba Cloud",
        "Chinese-language voiceover production",
        "narrating with a Qwen-cloned voice created by dashscope_voice_clone",
    ]
    not_good_for = [
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to convert to speech "
                    "(max 600 chars for qwen3-tts-flash)."
                ),
            },
            "model": {
                "type": "string",
                "enum": [
                    "qwen3-tts-flash",
                    "qwen3-tts-instruct-flash",
                    "qwen-tts-2025-05-22",
                    "qwen-audio-3.1-tts-flash",
                    "qwen-audio-3.1-tts-plus",
                    "qwen-audio-3.0-tts-flash",
                    "qwen-audio-3.0-tts-plus",
                    "cosyvoice-v3.5-flash",
                    "cosyvoice-v3.5-plus",
                    "cosyvoice-v3-flash",
                    "cosyvoice-v3-plus",
                    "cosyvoice-v2",
                ],
                "default": "qwen3-tts-flash",
                "description": (
                    "qwen3-tts-* uses system voices. qwen-audio-* / cosyvoice-* "
                    "use the native TTS endpoint and are required for cloned "
                    "voice IDs (inferred automatically from voice_id)."
                ),
            },
            "model_id": {
                "type": "string",
                "description": (
                    "Alias for model, accepted because tts_selector exposes "
                    "model_id. model wins when both are set."
                ),
            },
            "voice": {
                "type": "string",
                "default": "Cherry",
                "description": (
                    'DashScope voice name. Examples: "Cherry", "Ethan", '
                    '"Chelsie". Ignored when voice_id is set.'
                ),
            },
            "voice_id": {
                "type": "string",
                "description": (
                    "Cloned voice ID from dashscope_voice_clone. Takes "
                    "precedence over voice and implies the model it was "
                    "enrolled with."
                ),
            },
            "language_type": {
                "type": "string",
                "default": "Auto",
                "enum": ["Auto", "Chinese", "English", "Japanese", "Korean"],
                "description": "Language hint for the TTS model.",
            },
            "instructions": {
                "type": "string",
                "description": (
                    "Natural language delivery instructions "
                    "(only for qwen3-tts-instruct-flash)."
                ),
            },
            "format": {
                "type": "string",
                "enum": ["wav", "mp3", "pcm"],
                "default": "wav",
                "description": (
                    "Output container for qwen-audio-* / cosyvoice-* models. "
                    "qwen3-tts-* always returns WAV."
                ),
            },
            "sample_rate": {
                "type": "integer",
                "enum": [16000, 24000, 48000],
                "default": 24000,
                "description": (
                    "Sample rate for qwen-audio-* / cosyvoice-* models. "
                    "Ignored for qwen3-tts-*."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "text",
        "voice",
        "voice_id",
        "model",
        "language_type",
        "instructions",
        "format",
        "sample_rate",
    ]
    side_effects = [
        "writes audio file to output_path",
        "calls DashScope (Alibaba Cloud) TTS API",
    ]
    user_visible_verification = [
        "Listen to generated audio for naturalness and pacing"
    ]

    ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )
    NATIVE_ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/"
        "SpeechSynthesizer"
    )

    QWEN3_MODELS = [
        "qwen3-tts-flash",
        "qwen3-tts-instruct-flash",
        "qwen-tts-2025-05-22",
    ]
    # Cloned voices (dashscope_voice_clone) are addressed through the native
    # SpeechSynthesizer endpoint; list order matters for prefix matching
    # (longest first).
    CLONED_VOICE_MODELS = [
        "qwen-audio-3.1-tts-flash",
        "qwen-audio-3.1-tts-plus",
        "qwen-audio-3.0-tts-flash",
        "qwen-audio-3.0-tts-plus",
        "cosyvoice-v3.5-flash",
        "cosyvoice-v3.5-plus",
        "cosyvoice-v3-flash",
        "cosyvoice-v3-plus",
        "cosyvoice-v2",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Conservative per-character estimate; DashScope bills by character.
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        from tools.analysis.audio_probe import probe_duration

        start = time.time()
        try:
            resolved = self._resolve_model(inputs)
            payload = self._build_payload(inputs, resolved=resolved)
            model, voice_id, model_inferred = resolved
            endpoint = self._endpoint_for(payload["model"])

            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            try:
                data = response.json()
            except Exception:
                response.raise_for_status()
                raise RuntimeError(
                    f"DashScope returned non-JSON (HTTP {response.status_code})"
                )

            if response.status_code >= 400 or data.get("code"):
                return ToolResult(
                    success=False,
                    error=(
                        "DashScope TTS error: "
                        + self._describe_response(data)
                    ),
                )

            audio_info = data.get("output", {}).get("audio", {})
            audio_url = audio_info.get("url")
            if not audio_url:
                return ToolResult(
                    success=False,
                    error=(
                        "DashScope TTS returned no audio URL: "
                        + self._describe_response(data)
                    ),
                )

            # Download the audio from the temporary URL (valid ~24h).
            download = requests.get(audio_url, timeout=120)
            download.raise_for_status()

            output_path = Path(
                inputs.get("output_path", "dashscope_tts.wav")
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)

            audio_duration = probe_duration(output_path)
            usage = data.get("usage", {})

        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DashScope TTS failed: {self._safe_error(e)}",
            )

        data_payload: dict[str, Any] = {
            "provider": "dashscope",
            "model": payload["model"],
            "voice": payload["input"].get("voice"),
            "language_type": payload["input"].get("language_type"),
            "text_length": len(inputs["text"]),
            "audio_duration_seconds": (
                round(audio_duration, 2) if audio_duration else None
            ),
            "output": str(output_path),
            "audio_url": audio_url,
            "usage": usage,
            "endpoint": (
                "native_tts" if endpoint == self.NATIVE_ENDPOINT
                else "multimodal_generation"
            ),
        }
        if voice_id:
            data_payload["voice_id"] = voice_id
            data_payload["model_inferred_from_voice_id"] = model_inferred
        if endpoint == self.NATIVE_ENDPOINT:
            data_payload["format"] = payload["input"].get("format")
            data_payload["sample_rate"] = payload["input"].get("sample_rate")

        return ToolResult(
            success=True,
            data=data_payload,
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )

    # ------------------------------------------------------------------
    # Model / endpoint resolution
    # ------------------------------------------------------------------

    def _resolve_model(
        self, inputs: dict[str, Any]
    ) -> tuple[str, str | None, bool]:
        """Return (model, voice_id, model_inferred_from_voice_id).

        Cloned voice IDs embed their enrollment model as a prefix
        (``{target_model}-{prefix}-{hash}``), so a bare voice_id is enough to
        route to the right endpoint. A conflicting explicit model is an error:
        the API would reject the request because clones are model-bound.
        """
        voice_id = str(inputs.get("voice_id") or "").strip() or None
        explicit = inputs.get("model") or inputs.get("model_id")
        inferred = self.infer_model_from_voice_id(voice_id) if voice_id else None

        if explicit is None:
            if voice_id:
                if not inferred:
                    raise ValueError(
                        f"Could not infer the target model from voice_id "
                        f"{voice_id!r}. Pass model explicitly — one of: "
                        f"{', '.join(self.CLONED_VOICE_MODELS)}"
                    )
                return inferred, voice_id, True
            return "qwen3-tts-flash", None, False

        model = str(explicit)
        if voice_id and not self._is_native_model(model):
            raise ValueError(
                f"voice_id {voice_id!r} is a cloned voice and cannot be used "
                f"with {model!r}. Cloned voices require a qwen-audio-* or "
                "cosyvoice-* model."
            )
        if inferred and model != inferred:
            raise ValueError(
                f"voice_id {voice_id!r} was enrolled with {inferred!r} and "
                f"cannot be synthesized with {model!r}. Cloned voices are "
                "bound to their enrollment model; re-enroll with "
                "dashscope_voice_clone to use a different one."
            )
        return model, voice_id, False

    @classmethod
    def infer_model_from_voice_id(cls, voice_id: str | None) -> str | None:
        if not voice_id:
            return None
        for model in cls.CLONED_VOICE_MODELS:
            if voice_id.startswith(model + "-"):
                return model
        return None

    @classmethod
    def _is_native_model(cls, model: str) -> bool:
        return any(
            model.startswith(prefix) for prefix in ("qwen-audio-", "cosyvoice-")
        )

    def _endpoint_for(self, model: str) -> str:
        return self.NATIVE_ENDPOINT if self._is_native_model(model) else self.ENDPOINT

    def _build_payload(
        self,
        inputs: dict[str, Any],
        *,
        resolved: tuple[str, str | None, bool] | None = None,
    ) -> dict[str, Any]:
        model, voice_id, _ = resolved or self._resolve_model(inputs)

        if self._is_native_model(model):
            voice = voice_id or inputs.get("voice")
            if not voice:
                raise ValueError(
                    f"Model {model!r} needs a voice. Pass voice_id (cloned "
                    "voice from dashscope_voice_clone) or voice (system voice "
                    "name)."
                )
            return {
                "model": model,
                "input": {
                    "text": inputs["text"],
                    "voice": voice,
                    "format": inputs.get("format", "wav"),
                    "sample_rate": int(inputs.get("sample_rate", 24000)),
                },
            }

        input_data: dict[str, Any] = {
            "text": inputs["text"],
            "voice": inputs.get("voice", "Cherry"),
            "language_type": inputs.get("language_type", "Auto"),
        }
        if inputs.get("instructions"):
            input_data["instructions"] = inputs["instructions"]
            input_data["optimize_instructions"] = True

        return {
            "model": model,
            "input": input_data,
        }

    @staticmethod
    def _describe_response(data: dict[str, Any]) -> str:
        parts = [
            str(data[key])
            for key in ("code", "message", "request_id")
            if data.get(key)
        ]
        output = data.get("output") or {}
        if not parts and isinstance(output, dict):
            for key in ("finish_reason", "message"):
                if output.get(key):
                    parts.append(str(output[key]))
        return " | ".join(parts) or str(data)[:300]

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(
            os.environ.get("DASHSCOPE_API_KEY", ""), "[redacted]"
        )
