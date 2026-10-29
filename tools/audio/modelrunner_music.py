"""ModelRunner music generation across Lyria 2, Lyria 3 Clip, and Stable Audio 2.5."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import modelrunner_client
from tools.modelrunner_models import MUSIC_MODELS, PRICING_SNAPSHOT
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

_DEFAULT_MODEL = "google/lyria2"

_MODEL_ALIASES = {
    "lyria2": "google/lyria2",
    "lyria-2": "google/lyria2",
    "lyria3": "google/lyria-3/clip",
    "lyria-3": "google/lyria-3/clip",
    "lyria-3-clip": "google/lyria-3/clip",
    "stable-audio": "stability-ai/stable-audio-2.5/text-to-audio",
    "stable-audio-2.5": "stability-ai/stable-audio-2.5/text-to-audio",
}


class ModelRunnerMusic(BaseTool):
    name = "modelrunner_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "modelrunner"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MODELRUNNER_KEY"]
    install_instructions = modelrunner_client.INSTALL_INSTRUCTIONS
    agent_skills = ["modelrunner", "music"]

    capabilities = ["generate_background_music"]
    supports = {
        "instrumental": True,
        "vocals": True,  # Lyria 3 Clip sings generated or supplied lyrics
        "style_control": True,
        "long_form": True,  # Stable Audio 2.5 reaches ~190s in one call
        "multi_model_gateway": True,
    }
    best_for = [
        "Lyria 2 instrumental beds at a flat $0.06 per ~30s clip",
        "Lyria 3 Clip sung jingles and hooks with generated or supplied lyrics",
        "Stable Audio 2.5 long-form tracks and ambience up to ~190 seconds",
        "one ModelRunner key shared with image, video, and speech generation",
    ]
    not_good_for = [
        "offline generation",
        "sub-5-second sound effects (per-second SFX models are cheaper)",
        "stems or multi-track output (every route returns one mixed file)",
    ]
    fallback_tools = ["music_gen", "google_music", "suno_music"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Music description (genre, mood, instruments, tempo). Lyria 3 sings lyrics by default; say 'instrumental only, no vocals' to suppress them.",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "enum": sorted({*MUSIC_MODELS, *_MODEL_ALIASES}),
                "description": "Live ModelRunner endpoint id, or a friendly alias (lyria2, lyria-3-clip, stable-audio, ...).",
            },
            "duration_seconds": {
                "type": "number",
                "description": "Target length. Only Stable Audio 2.5 has duration control (1-190s); the Lyria routes produce fixed ~30s clips and reject other values.",
            },
            "negative_prompt": {"type": "string", "description": "What to exclude (Lyria 2 only)."},
            "seed": {"type": "integer"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 3.0},
            "poll_timeout": {"type": "number", "default": 600.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=100, network_required=True)
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "duration_seconds", "seed"]
    side_effects = ["writes an audio file to output_path", "submits one paid ModelRunner API request"]
    user_visible_verification = [
        "Listen to the generated track for style, structure, and loopability",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if modelrunner_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["pricing_snapshot"] = PRICING_SNAPSHOT
        info["model_catalog"] = {
            model_id: {
                "family": spec["family"],
                "cost_per_output": spec["cost_per_output"],
                "fixed_duration_seconds": spec["fixed_duration_seconds"],
                "duration_range": list(spec["duration_range"]) if spec["duration_range"] else None,
                "vocals": spec["vocals"],
                "output_format": spec["output_format"],
            }
            for model_id, spec in MUSIC_MODELS.items()
        }
        return info

    def _resolve_model(self, inputs: dict[str, Any]) -> str:
        requested = str(inputs.get("model") or _DEFAULT_MODEL)
        model = _MODEL_ALIASES.get(requested, requested)
        if model not in MUSIC_MODELS:
            choices = ", ".join(sorted(MUSIC_MODELS))
            raise ValueError(f"Unsupported ModelRunner music endpoint {requested!r}. Choose one of: {choices}")
        return model

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            return float(MUSIC_MODELS[self._resolve_model(inputs)]["cost_per_output"])
        except Exception:  # noqa: BLE001 - estimates must never raise
            return 0.06

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        spec = MUSIC_MODELS[model]
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        payload: dict[str, Any] = {"prompt": prompt}

        duration = inputs.get("duration_seconds")
        if duration is not None:
            duration = int(float(duration))
            if spec["duration_key"]:
                low, high = spec["duration_range"]
                if not low <= duration <= high:
                    raise ValueError(
                        f"duration_seconds={duration} is not supported; {model} accepts {low}-{high}"
                    )
                payload[spec["duration_key"]] = duration
            elif duration != spec["fixed_duration_seconds"]:
                raise ValueError(
                    f"{model} produces fixed ~{spec['fixed_duration_seconds']}s clips with no "
                    f"duration control; for an exact length use "
                    f"stability-ai/stable-audio-2.5/text-to-audio (1-190s)"
                )

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
            poll_interval, poll_timeout = modelrunner_client.parse_poll_controls(inputs, 3.0, 600.0)
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
                inputs.get("output_path") or f"modelrunner_music.{MUSIC_MODELS[model]['output_format']}"
            )
            modelrunner_client.download(source_url, output_path)
        except (modelrunner_client.ModelRunnerError, ValueError, KeyError) as exc:
            return self._failure(exc, queue, started)
        except Exception as exc:  # noqa: BLE001
            return self._failure(exc, queue, started)

        return ToolResult(
            success=True,
            data={
                "provider": "modelrunner", "model": model, "prompt": inputs.get("prompt", ""),
                "output": str(output_path), "output_path": str(output_path),
                "request_id": queue["request_id"], "source_url": source_url,
                "format": MUSIC_MODELS[model]["output_format"], "request_params": payload,
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
            error=f"ModelRunner music generation failed: {exc}",
            data=data,
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
        )
