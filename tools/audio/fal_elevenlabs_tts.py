"""Generate ElevenLabs speech through fal.ai using the shared FAL credential."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.provider_pricing import PriceQuoteRequired

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
    ResumeSupport,
)


class FalElevenLabsTTS(BaseTool):
    """Generate expressive narration with ElevenLabs models hosted by fal.ai."""

    name = "fal_elevenlabs_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "fal.ai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:FAL_KEY"]
    install_instructions = (
        "Set FAL_KEY to a fal.ai API key. No separate ElevenLabs key is needed. "
        "Get a fal.ai key at https://fal.ai/dashboard/keys"
    )
    fallback_tools = ["google_tts", "piper_tts", "elevenlabs_tts"]
    agent_skills = ["elevenlabs"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "expressive_delivery",
        "multilingual",
        "word_timestamps",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "inline_audio_tags": True,
        "word_timestamps": True,
    }
    best_for = [
        "expressive ElevenLabs narration through an existing fal.ai connection",
        "emotionally directed voiceover with Eleven v3 audio tags",
        "multilingual narration without a separate ElevenLabs credential",
    ]
    not_good_for = [
        "offline generation",
        "voice cloning or private custom ElevenLabs voices",
    ]

    resume_support = ResumeSupport.FROM_CHECKPOINT

    _MODELS = {
        "eleven-v4": "elevenlabs/tts/eleven-v4",
        "eleven-v3": "fal-ai/elevenlabs/tts/eleven-v3",
        "multilingual-v2": "fal-ai/elevenlabs/tts/multilingual-v2",
        "turbo-v2.5": "fal-ai/elevenlabs/tts/turbo-v2.5",
    }
    _MODEL_ALIASES = {
        "eleven_v4": "eleven-v4",
        "eleven_v3": "eleven-v3",
        "eleven_multilingual_v2": "multilingual-v2",
        "multilingual_v2": "multilingual-v2",
        "eleven_turbo_v2_5": "turbo-v2.5",
        "turbo_v2_5": "turbo-v2.5",
        **{value: key for key, value in _MODELS.items()},
    }
    _PRICE_PER_CHARACTER = {
        "eleven-v3": 0.0001,
        "multilingual-v2": 0.0001,
        "turbo-v2.5": 0.00005,
    }
    _POLL_INTERVAL_SECONDS = 2
    _MAX_WAIT_SECONDS = 300

    input_schema = {
        "type": "object",
        "anyOf": [{"required": ["text"]}, {"required": ["resume_job"]}],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to speak. Eleven v3 supports inline tags such as [whispers].",
            },
            "voice": {
                "type": "string",
                "default": "Rachel",
                "description": "fal.ai ElevenLabs voice name or ID",
            },
            "voice_id": {
                "type": "string",
                "description": "Alias for voice, for compatibility with tts_selector",
            },
            "model_id": {
                "type": "string",
                "default": "eleven-v3",
                "description": "eleven-v3, multilingual-v2, or turbo-v2.5",
            },
            "stability": {
                "type": "number",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1,
            },
            "similarity_boost": {
                "type": "number",
                "default": 0.75,
                "minimum": 0,
                "maximum": 1,
            },
            "style": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.7,
                "maximum": 1.2,
            },
            "language_code": {
                "type": "string",
                "description": "Optional ISO 639-1 language code",
            },
            "timestamps": {
                "type": "boolean",
                "default": False,
            },
            "apply_text_normalization": {
                "type": "string",
                "default": "auto",
                "enum": ["auto", "on", "off"],
            },
            "output_format": {
                "type": "string",
                "default": "mp3_44100_128",
                "enum": [
                    "mp3_22050_32",
                    "mp3_44100_64",
                    "mp3_44100_96",
                    "mp3_44100_128",
                    "mp3_44100_192",
                    "pcm_16000",
                    "pcm_24000",
                    "pcm_44100",
                    "pcm_48000",
                    "opus_48000_64",
                    "opus_48000_96",
                    "opus_48000_128",
                    "opus_48000_192",
                ],
            },
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
            "resume_job": {"type": "object"},
            "job_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=50,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = [
        "text",
        "voice",
        "voice_id",
        "model_id",
        "stability",
        "similarity_boost",
        "style",
        "speed",
        "language_code",
        "seed",
    ]
    side_effects = [
        "writes an audio file to output_path",
        "submits one paid fal.ai ElevenLabs speech request",
    ]
    user_visible_verification = [
        "Listen to the generated voice sample before approving full narration",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._get_api_key() else ToolStatus.UNAVAILABLE

    def _resolve_model(self, requested: str | None) -> tuple[str, str]:
        model_name = requested or "eleven-v3"
        model_name = self._MODEL_ALIASES.get(model_name, model_name)
        if model_name not in self._MODELS:
            choices = ", ".join(self._MODELS)
            raise ValueError(f"model_id must be one of: {choices}")
        return model_name, self._MODELS[model_name]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model_name, _ = self._resolve_model(inputs.get("model_id"))
        if model_name == "eleven-v4":
            raise PriceQuoteRequired("Obtain current fal Eleven v4 price quote")
        return round(
            len(inputs.get("text", "")) * self._PRICE_PER_CHARACTER[model_name],
            4,
        )

    @staticmethod
    def _output_extension(output_format: str) -> str:
        return {
            "mp3": "mp3",
            "pcm": "pcm",
            "opus": "opus",
        }.get(output_format.split("_", 1)[0], "audio")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No fal.ai API key found. " + self.install_instructions,
            )

        if inputs.get("resume_job"):
            return self._run_job(inputs, api_key, None, dict(inputs["resume_job"]))
        text = str(inputs.get("text", "")).strip()
        if not text:
            return ToolResult(success=False, error="text is required")

        try:
            model_name, model_id = self._resolve_model(inputs.get("model_id"))
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        stability = float(inputs.get("stability", 0.5))
        similarity_boost = float(inputs.get("similarity_boost", 0.75))
        speed = float(inputs.get("speed", 1.0))
        if not 0 <= stability <= 1 or not 0 <= similarity_boost <= 1:
            return ToolResult(
                success=False,
                error="stability and similarity_boost must be between 0 and 1",
            )
        if not 0.7 <= speed <= 1.2:
            return ToolResult(success=False, error="speed must be between 0.7 and 1.2")

        output_format = inputs.get("output_format", "mp3_44100_128")
        voice = inputs.get("voice") or inputs.get("voice_id") or "Rachel"
        payload: dict[str, Any] = {
            "text": text,
            "voice": voice,
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": speed,
            "timestamps": bool(inputs.get("timestamps", False)),
            "apply_text_normalization": inputs.get("apply_text_normalization", "auto"),
            "output_format": output_format,
        }
        for optional in ("language_code", "seed", "style"):
            if inputs.get(optional) is not None:
                payload[optional] = inputs[optional]

        if model_name == "eleven-v4":
            if "speed" in inputs or "style" in inputs:
                return ToolResult(
                    success=False, error="fal Eleven v4 does not expose speed/style"
                )
            payload.pop("speed", None)
            from jsonschema import Draft202012Validator
            from tools.fal_media import CONTRACTS

            try:
                Draft202012Validator(CONTRACTS[model_id]["input_schema"]).validate(
                    payload
                )
            except Exception as exc:
                return ToolResult(success=False, error=str(exc))

        job = {
            "tool": self.name,
            "model": model_id,
            "model_name": model_name,
            "voice": voice,
            "text_length": len(text),
            "output_format": output_format,
            "timestamps": payload["timestamps"],
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": speed if model_name != "eleven-v4" else None,
            "estimated_cost": self.estimate_cost(inputs)
            if model_name != "eleven-v4"
            else None,
        }
        return self._run_job(inputs, api_key, payload, job)

    def _run_job(self, inputs, api_key, payload, job):
        import requests
        from urllib.parse import urlparse
        from tools.provider_jobs import save_job

        started = time.time()
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }
        try:
            if job.get("tool") != self.name or self._MODELS.get(
                job.get("model_name")
            ) != job.get("model"):
                raise ValueError("Invalid ElevenLabs fal resume job")
            if payload is not None:
                response = requests.post(
                    f"https://queue.fal.run/{job['model']}",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                submitted = response.json()
                job.update(
                    {key: submitted[key] for key in ("status_url", "response_url")}
                )
                job["request_id"] = submitted.get("request_id")
                save_job(inputs.get("job_path"), job)
            for field in ("status_url", "response_url"):
                url = urlparse(job[field])
                if url.scheme != "https" or url.netloc != "queue.fal.run":
                    raise ValueError("Invalid fal job URL")
            deadline = time.monotonic() + self._MAX_WAIT_SECONDS
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "fal.ai ElevenLabs speech timed out; resume the existing job"
                    )
                time.sleep(self._POLL_INTERVAL_SECONDS)
                response = requests.get(job["status_url"], headers=headers, timeout=20)
                response.raise_for_status()
                status = response.json().get("status", "UNKNOWN")
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(f"fal.ai ElevenLabs speech {status.lower()}")
            response = requests.get(job["response_url"], headers=headers, timeout=30)
            response.raise_for_status()
            result_data = response.json()
            response = requests.get(result_data["audio"]["url"], timeout=120)
            response.raise_for_status()
            if not response.content:
                raise ValueError("Empty fal audio output")
            output_format = job["output_format"]
            output_path = Path(
                inputs.get(
                    "output_path",
                    f"fal_elevenlabs_tts.{self._output_extension(output_format)}",
                )
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"fal.ai ElevenLabs speech failed: {str(exc).replace(api_key, '[REDACTED]')}",
                data={"resume_job": job} if job.get("status_url") else {},
                duration_seconds=round(time.time() - started, 2),
            )
        data = {
            "provider": self.provider,
            "model": job["model"],
            "voice": job["voice"],
            "text_length": job["text_length"],
            "stability": job["stability"],
            "similarity_boost": job["similarity_boost"],
            "speed": job["speed"],
            "output": str(output_path),
            "format": output_format,
            "resume_job": job,
            "cost_status": "unquoted" if job["estimated_cost"] is None else "estimated",
        }
        if job["timestamps"] and "timestamps" in result_data:
            data["timestamps"] = result_data["timestamps"]
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=job["estimated_cost"],
            duration_seconds=round(time.time() - started, 2),
            model=job["model"],
        )
