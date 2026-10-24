"""ModelRunner text-to-speech across Kokoro, Gemini TTS, ElevenLabs, and Chatterbox."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import modelrunner_client
from tools.modelrunner_models import (
    CHARS_PER_SECOND_OF_SPEECH,
    CHATTERBOX_LANGUAGES,
    PRICING_SNAPSHOT,
    TTS_MODELS,
)
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

_DEFAULT_MODEL = "hexgrad/kokoro-82m"

# Friendly names accepted in `model_id` (the tts_selector vocabulary) and
# `model`, resolved to exact live endpoint ids.
_MODEL_ALIASES = {
    "kokoro": "hexgrad/kokoro-82m",
    "kokoro-82m": "hexgrad/kokoro-82m",
    "gemini-tts": "google/gemini-3.1-flash-tts",
    "gemini-3.1-flash-tts": "google/gemini-3.1-flash-tts",
    "elevenlabs": "elevenlabs/tts/multilingual-v2",
    "multilingual-v2": "elevenlabs/tts/multilingual-v2",
    "eleven_multilingual_v2": "elevenlabs/tts/multilingual-v2",
    "chatterbox": "resemble-ai/chatterbox/text-to-speech/multilingual",
    "chatterbox-multilingual": "resemble-ai/chatterbox/text-to-speech/multilingual",
}


class ModelRunnerTTS(BaseTool):
    """Speech synthesis through the ModelRunner gateway.

    Accepts the tts_selector's capability-level vocabulary. Controls a route
    does not support (e.g. `stability` on Kokoro, `pitch` anywhere) are
    ignored rather than rejected, because the selector passes its full input
    set through to whichever provider wins — the route tables in
    get_info()["model_catalog"] say which controls each route honors.
    """

    name = "modelrunner_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "modelrunner"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MODELRUNNER_KEY"]
    install_instructions = modelrunner_client.INSTALL_INSTRUCTIONS
    agent_skills = ["modelrunner", "text-to-speech"]

    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "multilingual": True,
        "voice_cloning": False,
        "offline": False,
        "style_direction": True,  # Gemini TTS takes plain-language delivery direction
        "multi_model_gateway": True,
    }
    best_for = [
        "sub-cent Kokoro narration in 46 voices across 6 languages",
        "Gemini TTS delivery directed in plain language (whisper, newscast, excited)",
        "ElevenLabs Multilingual v2 narration through an existing ModelRunner key",
        "one key shared with ModelRunner image, video, and music generation",
    ]
    not_good_for = [
        "offline generation",
        "voice cloning from a reference recording",
        "real-time streaming synthesis (returns a finished file)",
    ]
    fallback_tools = ["elevenlabs_tts", "google_tts", "openai_tts", "piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to speak."},
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "enum": sorted({*TTS_MODELS, *_MODEL_ALIASES}),
                "description": "Live ModelRunner TTS endpoint id, or one of the friendly aliases.",
            },
            "model_id": {
                "type": "string",
                "description": "Alias for model, for compatibility with tts_selector (kokoro, gemini-tts, multilingual-v2, chatterbox also accepted).",
            },
            "voice": {"type": "string", "description": "Route-specific voice name (Kokoro af_bella, Gemini Kore, ElevenLabs Rachel, ...). Validated by the API before billing."},
            "voice_id": {"type": "string", "description": "Alias for voice, for compatibility with tts_selector."},
            "speed": {"type": "number", "description": "Speaking speed on routes that support it (Kokoro 0.1-5, ElevenLabs 0.7-1.2)."},
            "speaking_rate": {"type": "number", "description": "Alias for speed."},
            "instructions": {"type": "string", "description": "Plain-language delivery direction (Gemini TTS only), e.g. 'Say the following in a warm, calm way'."},
            "language_code": {"type": "string", "description": "Language hint: a Gemini locale (en-us), ElevenLabs ISO 639-1 code, or Chatterbox language."},
            "stability": {"type": "number", "minimum": 0, "maximum": 1, "description": "ElevenLabs voice stability."},
            "similarity_boost": {"type": "number", "minimum": 0, "maximum": 1, "description": "ElevenLabs similarity boost."},
            "style": {"type": "number", "minimum": 0, "maximum": 1, "description": "ElevenLabs style exaggeration."},
            "apply_text_normalization": {"type": "string", "enum": ["auto", "on", "off"], "description": "ElevenLabs text normalization mode."},
            "exaggeration": {"type": "number", "description": "Chatterbox emotional intensity (0.25-2)."},
            "seed": {"type": "integer"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 2.0},
            "poll_timeout": {"type": "number", "default": 300.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=50, network_required=True)
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "model", "model_id", "voice", "voice_id", "speed", "language_code", "seed"]
    side_effects = ["writes an audio file to output_path", "submits one paid ModelRunner API request"]
    user_visible_verification = [
        "Listen to the generated voice sample before approving full narration",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if modelrunner_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["pricing_snapshot"] = PRICING_SNAPSHOT
        info["model_catalog"] = {
            model_id: {
                "family": spec["family"],
                "billing": spec["billing"],
                "cost_per_audio_second": spec.get("cost_per_audio_second"),
                "default_voice": spec["default_voice"],
                "voice_note": spec["voice_note"],
                "languages": spec["languages"],
                "max_text_length": spec["max_text_length"],
                "controls": list(spec["optional_fields"]),
                "output_format": spec["output_format"],
            }
            for model_id, spec in TTS_MODELS.items()
        }
        return info

    def _resolve_model(self, inputs: dict[str, Any]) -> str:
        requested = str(inputs.get("model") or inputs.get("model_id") or _DEFAULT_MODEL)
        model = _MODEL_ALIASES.get(requested, requested)
        if model not in TTS_MODELS:
            choices = ", ".join(sorted(TTS_MODELS))
            raise ValueError(f"Unsupported ModelRunner TTS endpoint {requested!r}. Choose one of: {choices}")
        return model

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            spec = TTS_MODELS[self._resolve_model(inputs)]
            audio_seconds = max(len(str(inputs.get("text", ""))) / CHARS_PER_SECOND_OF_SPEECH, 1.0)
            if spec["billing"] == "compute_time":
                return round(
                    max(audio_seconds * spec["estimated_cost_per_audio_second"], spec["minimum_estimate"]), 6
                )
            return round(audio_seconds * spec["cost_per_audio_second"], 6)
        except Exception:  # noqa: BLE001 - estimates must never raise
            return 0.01

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        spec = TTS_MODELS[model]
        text = str(inputs.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")

        payload: dict[str, Any] = {}
        if spec["text_key"] == "prompt":
            # Gemini TTS carries the delivery direction and the words in one
            # field, as "{style instruction}: {text}".
            instructions = str(inputs.get("instructions") or "").strip()
            payload["prompt"] = f"{instructions.rstrip(':')}: {text}" if instructions else text
        else:
            payload["text"] = text

        # The route's length cap applies to the field actually sent — for
        # Gemini that is the assembled direction+text prompt, not `text` alone.
        maximum = spec["max_text_length"]
        sent = payload[spec["text_key"]]
        if maximum and len(sent) > maximum:
            raise ValueError(
                f"{model} accepts at most {maximum} characters per call "
                f"(got {len(sent)} including any delivery instructions); "
                f"split the script into shorter chunks"
            )

        voice = inputs.get("voice") or inputs.get("voice_id")
        if model.startswith("resemble-ai/chatterbox") and not voice:
            # On this route `voice` selects the language, so an ISO code in
            # language_code is the natural way callers express it.
            language = str(inputs.get("language_code") or "").lower()
            voice = CHATTERBOX_LANGUAGES.get(language.split("-", 1)[0]) if language else None
        if voice:
            payload["voice"] = voice

        speed = inputs.get("speed", inputs.get("speaking_rate"))
        if speed is not None and spec["speed_range"]:
            low, high = spec["speed_range"]
            speed = float(speed)
            if not low <= speed <= high:
                raise ValueError(f"speed={speed} is not supported; {model} accepts {low}-{high}")
            payload["speed"] = speed

        for field in spec["optional_fields"]:
            if inputs.get(field) is not None:
                payload[field] = inputs[field]

        return modelrunner_client.merge_extra_params(payload, inputs.get("extra_params"))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = modelrunner_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="MODELRUNNER_KEY not set. " + self.install_instructions)

        started = time.time()
        queue: dict[str, Any] = {}
        try:
            poll_interval, poll_timeout = modelrunner_client.parse_poll_controls(inputs, 2.0, 300.0)
            model = self._resolve_model(inputs)
            payload = self._build_payload(inputs, model)
            queue = modelrunner_client.submit(model, payload, api_key)
            modelrunner_client.poll(
                queue["status_url"], api_key,
                interval=poll_interval,
                timeout=poll_timeout,
            )
            result = modelrunner_client.get_result(queue["response_url"], api_key)
            source_url = modelrunner_client.extract_outputs(result, "single")[0]
            output_path = Path(
                inputs.get("output_path") or f"modelrunner_tts.{TTS_MODELS[model]['output_format']}"
            )
            modelrunner_client.download(source_url, output_path)
        except (modelrunner_client.ModelRunnerError, ValueError, KeyError) as exc:
            return self._failure(exc, queue, started)
        except Exception as exc:  # noqa: BLE001
            return self._failure(exc, queue, started)

        return ToolResult(
            success=True,
            data={
                "provider": "modelrunner", "model": model,
                "voice": payload.get("voice", TTS_MODELS[model]["default_voice"]),
                "text_length": len(str(inputs.get("text", ""))),
                "output": str(output_path), "output_path": str(output_path),
                "request_id": queue["request_id"], "source_url": source_url,
                "format": TTS_MODELS[model]["output_format"], "request_params": payload,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost({**inputs, "model": model}),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )

    def _failure(self, exc: Exception, queue: dict[str, Any], started: float) -> ToolResult:
        known = queue or getattr(exc, "queue", {})
        data: dict[str, Any] = {}
        if known:
            data = {**known, "billing_status": "possibly_billed"}
        return ToolResult(
            success=False,
            error=f"ModelRunner speech synthesis failed: {exc}",
            data=data,
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
        )
