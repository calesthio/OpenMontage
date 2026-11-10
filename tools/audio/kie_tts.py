"""KIE AI text-to-speech gateway.

KIE AI (https://kie.ai) is a multi-model aggregator. This tool defaults to
Gemini 3.8 Flash TTS -- a single-speaker-friendly dialogue model with broad
language support (verified working for Vietnamese) -- and exposes a generic
`extra_input` passthrough plus `kie_model` override so other KIE Market TTS
models (ElevenLabs multilingual v2, turbo 2.5, ...) can be called without a
code change. Check https://kie.ai/market for the exact `input` fields of a
given model before switching `kie_model`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import kie_client
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
from tools.provider_pricing import PriceQuoteRequired

_DEFAULT_MODEL = "google/gemini-3-8-flash-tts"
_DEFAULT_VOICE = "Kore"


class KieTTS(BaseTool):
    name = "kie_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kie"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KIE_API_KEY"]
    install_instructions = kie_client.INSTALL_INSTRUCTIONS

    capabilities = ["text_to_speech"]
    supports = {
        "multilingual": True,
        "multi_speaker_dialogue": True,
        "tone_tags": True,
        "multi_model_gateway": True,
    }
    best_for = [
        "Narration in languages/voices a configured provider doesn't cover (verified for Vietnamese)",
        "Trying other KIE Market TTS models (ElevenLabs multilingual v2, turbo 2.5) via kie_model + extra_input",
    ]
    not_good_for = ["offline generation", "guaranteed pricing without checking kie.ai/pricing"]
    fallback_tools = ["google_tts", "openai_tts", "gemini_tts"]
    quality_score = 0.78

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "kie_model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "KIE AI Market TTS model id for createTask's top-level 'model' field.",
            },
            "voice_name": {
                "type": "string",
                "default": _DEFAULT_VOICE,
                "description": "Only used when kie_model == default (Gemini 3.8 Flash TTS). One of the model's 70 named voices.",
            },
            "temperature": {"type": "number", "minimum": 0, "maximum": 2, "default": 1},
            "extra_input": {
                "type": "object",
                "description": "Raw fields merged into the Market 'input' object -- use for non-default kie_model schemas (e.g. ElevenLabs 'voice' id).",
            },
            "callback_url": {"type": "string"},
            "poll_interval": {"type": "number", "default": 3.0},
            "poll_timeout": {"type": "number", "default": 180.0},
            "output_path": {"type": "string"},
            "resume_task_id": {
                "type": "string",
                "description": (
                    "A taskId from a previous call whose submission succeeded but polling or "
                    "download failed (surfaced in that failed ToolResult's data.task_id). When "
                    "set, this call skips createTask entirely and only polls/downloads that "
                    "existing task -- it never submits a new (paid) generation."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=50, network_required=True)
    # "timeout" is deliberately NOT retryable -- see kie_video.py for the rationale. Recover with
    # resume_task_id instead of blindly re-calling execute().
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit"])
    idempotency_key_fields = ["text", "kie_model", "voice_name"]
    side_effects = ["writes audio file to output_path", "calls KIE AI API"]
    user_visible_verification = ["Listen to the narration for pronunciation and pacing"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "KIE AI TTS pricing varies by model -- see https://kie.ai/pricing"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 15.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = kie_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="KIE_API_KEY not set. " + self.install_instructions)

        kie_model = str(inputs.get("kie_model", _DEFAULT_MODEL))
        started = time.time()
        market_input: dict[str, Any] | None = None

        resume_task_id = inputs.get("resume_task_id")
        if resume_task_id:
            task_id = str(resume_task_id)
        else:
            try:
                if kie_model == _DEFAULT_MODEL:
                    market_input = {
                        "temperature": float(inputs.get("temperature", 1)),
                        "speakers": [{"speaker_id": "Speaker 1", "voice_name": inputs.get("voice_name", _DEFAULT_VOICE)}],
                        "dialogue_turns": [{"speaker_id": "Speaker 1", "text": inputs["text"]}],
                    }
                else:
                    market_input = {"text": inputs.get("text", "")}
                extra = inputs.get("extra_input")
                if isinstance(extra, dict):
                    market_input.update(extra)

                task_id = kie_client.create_task(
                    kie_model, market_input, api_key, callback_url=inputs.get("callback_url")
                )
            except (kie_client.KieError, ValueError, KeyError) as exc:
                return ToolResult(
                    success=False,
                    error=(
                        f"KIE AI TTS task submission failed: {exc}. If this was a network/timeout "
                        f"error rather than a clear rejection, check https://kie.ai/logs before "
                        f"retrying -- the job may have been created and billed even though this call "
                        f"never saw a taskId."
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                return ToolResult(success=False, error=f"KIE AI TTS task submission failed unexpectedly: {exc}")

        try:
            urls = kie_client.poll_task(
                task_id,
                api_key,
                interval=float(inputs.get("poll_interval", 3.0)),
                timeout=float(inputs.get("poll_timeout", 180.0)),
            )
            output_path = Path(inputs.get("output_path") or "kie_tts_output.wav")
            kie_client.download(urls[0], output_path)
        except (kie_client.KieError, ValueError, KeyError) as exc:
            return ToolResult(
                success=False,
                error=(
                    f"KIE AI TTS task {task_id} was accepted but polling/download failed: {exc}. "
                    f"The job may still complete (and may already be billed) -- do NOT resubmit. "
                    f"Call this tool again with resume_task_id={task_id!r} to retry polling/download "
                    f"for this exact job without creating a new one."
                ),
                data={"provider": "kie", "model": kie_model, "task_id": task_id},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"KIE AI TTS task {task_id} polling/download failed unexpectedly: {exc}",
                data={"provider": "kie", "model": kie_model, "task_id": task_id},
            )

        return ToolResult(
            success=True,
            data={
                "provider": "kie",
                "model": kie_model,
                "text": inputs.get("text", ""),
                "output": str(output_path),
                "output_path": str(output_path),
                "task_id": task_id,
                "source_url": urls[0],
                "request_params": market_input,
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - started, 2),
            model=kie_model,
        )
