"""Kling official API text-to-speech provider."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools._kling.account import account_usage_hint_for_error, get_account_costs
from tools._kling.callbacks import validate_callback_url
from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError
from tools._kling.media import extension_from_url, numbered_output_path, output_path_with_suffix
from tools._kling.schemas import TTS_LANGUAGES, TTS_SPEED_MAX, TTS_SPEED_MIN
from tools.analysis.audio_probe import probe_duration
from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


class KlingTTS(BaseTool):
    name = "kling_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kling_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KLING_API_KEY"]
    install_instructions = (
        "Set KLING_API_KEY in .env for the official Kling API. "
        "Pass voice_id explicitly; OpenMontage does not guess Kling voice IDs."
    )
    agent_skills = ["kling-official", "text-to-speech"]

    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "multilingual": True,
        "voice_selection": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "official Kling text-to-speech",
        "Chinese or English narration when a Kling voice_id is known",
        "keeping narration provider provenance inside the Kling official account",
    ]
    not_good_for = [
        "fully offline narration",
        "voice cloning without a configured official voice_id",
        "auto-discovering voices",
    ]
    fallback_tools = ["doubao_tts", "elevenlabs_tts", "openai_tts", "google_tts", "piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text", "voice_id"],
        "properties": {
            "text": {"type": "string"},
            "voice_id": {
                "type": "string",
                "description": "Official Kling voice ID. Required; do not rely on an unknown default.",
            },
            "voice_language": {"type": "string", "enum": TTS_LANGUAGES, "default": "en"},
            "voice_speed": {
                "type": "number",
                "minimum": TTS_SPEED_MIN,
                "maximum": TTS_SPEED_MAX,
                "default": 1.0,
            },
            "callback_url": {"type": "string"},
            "external_task_id": {"type": "string"},
            "include_account_usage": {
                "type": "boolean",
                "default": False,
                "description": "Optional low-frequency account usage diagnostic; not used by default.",
            },
            "timeout_seconds": {"type": "integer", "default": 300},
            "poll_interval": {"type": "number", "default": 3.0},
            "output_path": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "output_path": {"type": "string"},
            "audio_paths": {"type": "array"},
            "task_id": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["1302", "1303", "5000", "5001", "5002"],
    )
    idempotency_key_fields = ["text", "voice_id", "voice_language", "voice_speed"]
    side_effects = ["paid remote generation via official Kling API", "writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for voice, language, and pacing"]
    quality_score = 0.78
    latency_p50_seconds = 20.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        text_length = len(str(inputs.get("text") or ""))
        return round(max(text_length, 1) * 0.000018, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        result.update(
            {
                "paid_api": True,
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative character-based OpenMontage estimate pending official account-usage reconciliation.",
            }
        )
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            self.check_dependencies()
        except DependencyError as exc:
            return ToolResult(success=False, error=str(exc))

        start = time.time()
        try:
            request = self._build_request(inputs)
            client = KlingClient()
            task_id, outputs = self._create_and_collect_audios(client, request, inputs)
            paths = self._download_audios(client, outputs, inputs)
            audio_duration = probe_duration(paths[0])
        except (KlingAPIError, TimeoutError, ValueError, KeyError, FileNotFoundError) as exc:
            data: dict[str, Any] = {"provider": self.provider}
            if isinstance(exc, KlingAPIError):
                data.update(
                    {
                        "error_code": exc.code,
                        "request_id": exc.request_id,
                        "http_status": exc.http_status,
                        "account_usage_diagnostic": account_usage_hint_for_error(exc),
                    }
                )
            return ToolResult(success=False, data=data, error=f"Kling official TTS failed: {exc}")
        except Exception as exc:
            return ToolResult(success=False, data={"provider": self.provider}, error=f"Kling official TTS failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "kling-official-tts",
                "task_id": task_id,
                "operation": "text_to_speech",
                "text_length": len(request["payload"]["text"]),
                "voice_id": request["payload"]["voice_id"],
                "voice_language": request["payload"].get("voice_language"),
                "voice_speed": request["payload"].get("voice_speed"),
                "remote_outputs": outputs,
                "output": str(paths[0]),
                "output_path": str(paths[0]),
                "audio_paths": [str(path) for path in paths],
                "format": paths[0].suffix.lstrip(".") or "mp3",
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative estimate pending official account-usage reconciliation.",
                **self._account_usage_result(inputs, client),
                **self._callback_result_data(inputs, task_id),
            },
            artifacts=[str(path) for path in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="kling-official-tts",
        )

    def _build_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        text = str(inputs.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")
        if len(text) > 5000:
            raise ValueError("text exceeds Kling TTS safety limit of 5000 characters")

        voice_id = str(inputs.get("voice_id") or "").strip()
        if not voice_id:
            raise ValueError("voice_id is required for Kling official TTS")

        voice_language = str(inputs.get("voice_language") or "en")
        if voice_language not in TTS_LANGUAGES:
            raise ValueError(f"voice_language must be one of: {', '.join(TTS_LANGUAGES)}")

        voice_speed = float(inputs.get("voice_speed", 1.0))
        if voice_speed < TTS_SPEED_MIN or voice_speed > TTS_SPEED_MAX:
            raise ValueError(f"voice_speed must be between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}")

        payload: dict[str, Any] = {
            "text": text,
            "voice_id": voice_id,
            "voice_language": voice_language,
            "voice_speed": voice_speed,
        }
        self._copy_common_task_fields(inputs, payload)
        return {
            "protocol": "classic",
            "path": "/v1/audio/tts",
            "payload": payload,
            "operation": "text_to_speech",
            "model": "kling-official-tts",
        }

    @staticmethod
    def _create_and_collect_audios(
        client: KlingClient,
        request: dict[str, Any],
        inputs: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Create a TTS task and return audio outputs.

        Official TTS may return a completed task and task_result.audios[]
        directly from POST /v1/audio/tts. Older/async behavior still requires
        polling GET /v1/audio/tts/{task_id}, so support both shapes.
        """
        if hasattr(client, "post"):
            data = client.post(request["path"], request["payload"])
            payload = data.get("data") or {}
            task_id = payload.get("task_id")
            if not task_id:
                raise KlingAPIError(f"Kling TTS create response missing data.task_id: {data}")

            task_result = payload.get("task_result") or {}
            outputs = task_result.get("audios")
            if outputs is not None:
                if not isinstance(outputs, list):
                    raise KlingAPIError("Kling TTS result path data.task_result.audios is not a list")
                return str(task_id), outputs

            status = payload.get("task_status") or payload.get("status")
            if status == "failed":
                message = payload.get("task_status_msg") or payload.get("message") or "Kling TTS task failed"
                raise KlingAPIError(str(message), code=payload.get("task_status"), response=data)

            return str(task_id), client.poll_classic(
                request["path"],
                str(task_id),
                "audios",
                timeout_seconds=int(inputs.get("timeout_seconds", 300)),
                poll_interval=float(inputs.get("poll_interval", 3.0)),
            )

        task_id = client.create_classic_task(request["path"], request["payload"])
        return task_id, client.poll_classic(
            request["path"],
            task_id,
            "audios",
            timeout_seconds=int(inputs.get("timeout_seconds", 300)),
            poll_interval=float(inputs.get("poll_interval", 3.0)),
        )

    def _download_audios(
        self,
        client: KlingClient,
        outputs: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> list[Path]:
        if not outputs:
            raise ValueError("Kling TTS response contained no audios")
        base_path = Path(inputs.get("output_path", "kling_tts.mp3"))
        paths: list[Path] = []
        for index, item in enumerate(outputs):
            url = self._output_url(item)
            suffix = extension_from_url(url, ".mp3")
            output_path = numbered_output_path(output_path_with_suffix(base_path, suffix), index, suffix)
            client.download(url, output_path)
            paths.append(output_path)
        return paths

    @staticmethod
    def _output_url(item: dict[str, Any]) -> str:
        url = item.get("url") or item.get("audio_url") or item.get("resource_url")
        if url:
            return str(url)
        resource = item.get("resource") or {}
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
        raise ValueError(f"Kling TTS response item contained no downloadable URL: {item}")

    @staticmethod
    def _copy_common_task_fields(inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            payload["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            payload["external_task_id"] = inputs["external_task_id"]

    @staticmethod
    def _callback_result_data(inputs: dict[str, Any], task_id: str) -> dict[str, Any]:
        callback_url = inputs.get("callback_url")
        if not callback_url:
            return {}
        return {
            "callback_url": str(callback_url),
            "callback_requested": True,
            "polling_used": True,
            "task_id": task_id,
        }

    @staticmethod
    def _account_usage_result(inputs: dict[str, Any], client: KlingClient) -> dict[str, Any]:
        if not inputs.get("include_account_usage"):
            return {}
        try:
            usage = get_account_costs(client=client)
            return {
                "account_usage": usage,
                "cost_source": "estimate_with_account_usage_context",
                "reconciled_cost_usd": None,
            }
        except Exception as exc:
            return {
                "account_usage_error": str(exc),
                "cost_source": "estimate",
                "reconciled_cost_usd": None,
            }
