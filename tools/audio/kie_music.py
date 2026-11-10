"""KIE AI music generation gateway (Suno).

KIE AI (https://kie.ai) wraps Suno for text-to-music generation. Unlike most
Market models, the Suno endpoint answers with a divergent result shape
(``{"data": [{"audio_url": ...}, ...]}`` instead of ``{"resultUrls": [...]}``),
so this tool uses `kie_client.poll_task_raw` and parses it itself. Generation
typically returns 2 variations; this tool downloads the first by default.
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

_DEFAULT_MODEL = "ai-music-api/generate"


class KieMusic(BaseTool):
    name = "kie_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "kie"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KIE_API_KEY"]
    install_instructions = kie_client.INSTALL_INSTRUCTIONS

    capabilities = ["music_generation", "instrumental"]
    supports = {
        "instrumental": True,
        "custom_duration": True,
        "variations_per_call": 2,
        "multi_model_gateway": True,
    }
    best_for = [
        "Instrumental background music to a target duration, through a single KIE AI key",
    ]
    not_good_for = ["offline generation", "guaranteed pricing without checking kie.ai/pricing"]
    fallback_tools = ["music_gen", "google_music", "fal_elevenlabs_music"]
    quality_score = 0.8

    input_schema = {
        "type": "object",
        "required": ["style", "duration_seconds"],
        "properties": {
            "style": {"type": "string", "description": "Music style/mood/instrumentation description."},
            "title": {"type": "string", "default": "Background Track"},
            "duration_seconds": {"type": "number", "minimum": 10, "maximum": 360},
            "instrumental": {"type": "boolean", "default": True},
            "lyrics": {"type": "string"},
            "suno_model": {"type": "string", "default": "V6", "enum": ["V6", "V6_MINI", "V6_WILD"]},
            "variation_index": {"type": "integer", "default": 0, "minimum": 0, "maximum": 1},
            "callback_url": {"type": "string"},
            "poll_interval": {"type": "number", "default": 5.0},
            "poll_timeout": {"type": "number", "default": 240.0},
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

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=100, network_required=True)
    # "timeout" is deliberately NOT retryable -- see kie_video.py for the rationale. Recover with
    # resume_task_id instead of blindly re-calling execute().
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit"])
    idempotency_key_fields = ["style", "duration_seconds", "instrumental"]
    side_effects = ["writes audio file to output_path", "calls KIE AI API"]
    user_visible_verification = ["Listen for mood fit and that the duration roughly matches the video"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "KIE AI music pricing varies by model/duration -- see https://kie.ai/pricing"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 90.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = kie_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="KIE_API_KEY not set. " + self.install_instructions)

        started = time.time()
        market_input: dict[str, Any] | None = None

        resume_task_id = inputs.get("resume_task_id")
        if resume_task_id:
            task_id = str(resume_task_id)
        else:
            try:
                market_input = {
                    "custom_mode": True,
                    "instrumental": bool(inputs.get("instrumental", True)),
                    "model": inputs.get("suno_model", "V6"),
                    "title": str(inputs.get("title", "Background Track"))[:80],
                    "style": inputs["style"],
                    "duration": float(inputs["duration_seconds"]),
                }
                if inputs.get("lyrics"):
                    market_input["lyrics"] = inputs["lyrics"]

                task_id = kie_client.create_task(
                    _DEFAULT_MODEL, market_input, api_key, callback_url=inputs.get("callback_url")
                )
            except (kie_client.KieError, ValueError, KeyError) as exc:
                return ToolResult(
                    success=False,
                    error=(
                        f"KIE AI music task submission failed: {exc}. If this was a network/timeout "
                        f"error rather than a clear rejection, check https://kie.ai/logs before "
                        f"retrying -- the job may have been created and billed even though this call "
                        f"never saw a taskId."
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                return ToolResult(success=False, error=f"KIE AI music task submission failed unexpectedly: {exc}")

        try:
            parsed = kie_client.poll_task_raw(
                task_id,
                api_key,
                interval=float(inputs.get("poll_interval", 5.0)),
                timeout=float(inputs.get("poll_timeout", 240.0)),
            )
            tracks = parsed.get("data") or []
            if not tracks:
                return ToolResult(
                    success=False,
                    error=f"KIE AI music task {task_id} succeeded but returned no tracks: {parsed}",
                    data={"provider": "kie", "model": _DEFAULT_MODEL, "task_id": task_id},
                )
            index = min(int(inputs.get("variation_index", 0)), len(tracks) - 1)
            track = tracks[index]
            audio_url = track.get("audio_url")
            if not audio_url:
                return ToolResult(
                    success=False,
                    error=f"KIE AI music task {task_id} track had no audio_url: {track}",
                    data={"provider": "kie", "model": _DEFAULT_MODEL, "task_id": task_id},
                )

            output_path = Path(inputs.get("output_path") or "kie_music_output.mp3")
            kie_client.download(audio_url, output_path)
        except (kie_client.KieError, ValueError, KeyError) as exc:
            return ToolResult(
                success=False,
                error=(
                    f"KIE AI music task {task_id} was accepted but polling/download failed: {exc}. "
                    f"The job may still complete (and may already be billed) -- do NOT resubmit. "
                    f"Call this tool again with resume_task_id={task_id!r} to retry polling/download "
                    f"for this exact job without creating a new one."
                ),
                data={"provider": "kie", "model": _DEFAULT_MODEL, "task_id": task_id},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"KIE AI music task {task_id} polling/download failed unexpectedly: {exc}",
                data={"provider": "kie", "model": _DEFAULT_MODEL, "task_id": task_id},
            )

        return ToolResult(
            success=True,
            data={
                "provider": "kie",
                "model": _DEFAULT_MODEL,
                "style": inputs.get("style", ""),
                "output": str(output_path),
                "output_path": str(output_path),
                "task_id": task_id,
                "source_url": audio_url,
                "variations_available": len(tracks),
                "selected_variation": index,
                "track_duration_seconds": track.get("duration"),
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - started, 2),
            model=_DEFAULT_MODEL,
        )
