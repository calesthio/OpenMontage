"""ModelRunner video generation with exact, discoverable live-model routes."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import modelrunner_client
from tools.modelrunner_models import PRICING_SNAPSHOT, VIDEO_MODELS, VIDEO_ROUTES
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

_DEFAULT_MODEL = "wan-video/wan/v2.7/text-to-video"
_OPERATIONS = ("text_to_video", "image_to_video")


def _is_remote(entry: str) -> bool:
    return str(entry).strip().lower().startswith(("http://", "https://", "data:", "asset://"))


class ModelRunnerVideo(BaseTool):
    name = "modelrunner_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "modelrunner"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MODELRUNNER_KEY"]
    install_instructions = modelrunner_client.INSTALL_INSTRUCTIONS
    agent_skills = ["modelrunner", "ai-video-gen"]

    capabilities = list(_OPERATIONS)
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": True,  # every catalog route generates a soundtrack
        "custom_duration": True,
        "aspect_ratio": True,
        "multi_model_gateway": True,
    }
    provider_matrix = {
        family: dict(routes) for family, routes in VIDEO_ROUTES.items()
    }
    best_for = [
        "Wan 2.7 text and image-to-video with generated audio through one ModelRunner key",
        "Happy Horse 1.1 lip-synced dialogue shots straight from a text prompt",
        "Seedance 2.0 Mini budget drafting at roughly half the flagship price per second",
        "per-route rate tables (resolution-tiered pricing) and fail-before-billing validation",
    ]
    not_good_for = [
        "offline generation",
        "silent clips (every catalog route always generates audio except Seedance's toggle)",
        "clips longer than the selected route permits (15s ceiling across the catalog)",
    ]
    fallback_tools = ["atlas_video", "seedance_video", "kling_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "enum": sorted(VIDEO_MODELS),
                "description": "Exact live ModelRunner endpoint id. See get_info()['model_catalog'] for routes, rates, and limits.",
            },
            "operation": {"type": "string", "enum": list(_OPERATIONS), "default": "text_to_video"},
            "duration": {"type": "integer", "default": 5, "description": "Clip length in seconds; each route enforces its own range."},
            "resolution": {"type": "string", "description": "Route-specific resolution tier (e.g. 720P/1080P for Wan, 480p/720p for Seedance Mini). The billed per-second rate depends on it."},
            "aspect_ratio": {"type": "string", "description": "Frame shape. Ignored by image-to-video routes that inherit the source image's shape."},
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            "generate_audio": {"type": "boolean", "description": "Seedance routes only: set false for a silent clip (same price)."},
            "enable_prompt_expansion": {"type": "boolean", "description": "Wan routes only: LLM prompt rewrite before generation (default true upstream)."},
            # NOTE: `image_url` is deliberately NOT declared here even though
            # execute() accepts it as an alias. The video_selector fal-uploads
            # local reference images for tools that advertise `image_url`; this
            # tool hosts local media itself via ModelRunner storage (same
            # convention as seedance_ark).
            "image_path": {"type": "string", "description": "Local start frame; uploaded to ModelRunner storage (a hosted https URL is accepted here or via reference_image_url)."},
            "reference_image_url": {"type": "string", "description": "Hosted start-frame URL (the selector's canonical key; image_url is accepted as an alias on direct calls)."},
            "reference_image_path": {"type": "string"},
            "end_image_url": {"type": "string"},
            "end_image_path": {"type": "string"},
            "last_image_url": {"type": "string"},
            "last_image_path": {"type": "string"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 5.0},
            "poll_timeout": {"type": "number", "default": 1200.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=500, network_required=True)
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "resolution", "aspect_ratio", "seed"]
    side_effects = ["writes a video file to output_path", "submits one paid ModelRunner API request"]
    user_visible_verification = [
        "Watch the generated clip for prompt fidelity, motion coherence, and audio quality",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if modelrunner_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["pricing_snapshot"] = PRICING_SNAPSHOT
        info["model_catalog"] = {
            model_id: {
                "family": spec["family"],
                "operation": spec["operation"],
                "cost_per_second_by_resolution": dict(spec["rates_per_output_second"]),
                "durations": list(spec["durations"]),
                "resolutions": list(spec["resolutions"]),
                "default_resolution": spec["default_resolution"],
                "ratios": list(spec["ratios"]),
                "first_last_frame": bool(spec["end_image_key"]),
                "native_audio": spec["native_audio"],
            }
            for model_id, spec in VIDEO_MODELS.items()
        }
        return info

    def is_operation_available(self, operation: str) -> bool:
        return operation in _OPERATIONS

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            model = self._resolve_model(
                str(inputs.get("model", _DEFAULT_MODEL)),
                self._resolve_operation(inputs),
            )
            spec = VIDEO_MODELS[model]
            resolution = str(inputs.get("resolution") or spec["default_resolution"])
            rate = spec["rates_per_output_second"].get(resolution, spec["default_rate"])
            duration = int(inputs.get("duration", spec["default_duration"]))
            return round(rate * max(duration, 0), 4)
        except Exception:  # noqa: BLE001 - estimates must never raise
            return 0.75  # default route (wan 2.7) at its 1080P rate for 5s

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 240.0

    @staticmethod
    def _resolve_operation(inputs: dict[str, Any]) -> str:
        """The effective operation for this call.

        An explicit `operation` always wins. When it is omitted but the caller
        pinned an exact endpoint, the endpoint's own operation is used — the
        schema default (text_to_video) must never silently rewrite an
        explicitly chosen image-to-video route to its text sibling.
        """
        operation = inputs.get("operation")
        if operation:
            return str(operation)
        pinned = inputs.get("model")
        if pinned and str(pinned) in VIDEO_MODELS:
            return str(VIDEO_MODELS[str(pinned)]["operation"])
        return "text_to_video"

    def _resolve_model(self, model: str, operation: str) -> str:
        if model not in VIDEO_MODELS:
            raise ValueError(
                f"Unsupported ModelRunner video endpoint {model!r}. "
                f"Use get_info()['model_catalog'] for the live routes."
            )
        spec = VIDEO_MODELS[model]
        if spec["operation"] == operation:
            return model
        resolved = VIDEO_ROUTES.get(spec["family"], {}).get(operation)
        if not resolved:
            raise ValueError(
                f"{spec['family']} does not expose operation={operation!r} on ModelRunner"
            )
        return resolved

    @staticmethod
    def _validate_choice(name: str, value: Any, allowed: tuple[Any, ...]) -> Any:
        if allowed and value not in allowed:
            raise ValueError(f"{name}={value!r} is not supported; choose one of {list(allowed)}")
        return value

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        spec = VIDEO_MODELS[model]
        payload: dict[str, Any] = {}

        prompt = str(inputs.get("prompt") or "").strip()
        if prompt:
            payload["prompt"] = prompt
        elif spec["prompt_required"]:
            raise ValueError(f"{model} requires a non-empty prompt")

        low, high = spec["durations"]
        duration = int(inputs.get("duration", spec["default_duration"]))
        if not low <= duration <= high:
            raise ValueError(f"duration={duration} is not supported; {model} accepts {low}-{high} seconds")
        payload["duration"] = duration

        resolution = str(inputs.get("resolution") or spec["default_resolution"])
        payload["resolution"] = self._validate_choice("resolution", resolution, spec["resolutions"])

        if spec["ratio_key"]:
            ratio = inputs.get("aspect_ratio") or spec["default_ratio"]
            payload[spec["ratio_key"]] = self._validate_choice("aspect_ratio", ratio, spec["ratios"])

        image = inputs.get("image_url")
        if spec["image_key"]:
            if not image:
                raise ValueError(
                    "image_to_video requires image_url, image_path, or reference_image_path"
                )
            payload[spec["image_key"]] = image
            end_image = inputs.get("end_image_url")
            if end_image:
                if not spec["end_image_key"]:
                    raise ValueError(f"{model} does not accept a closing frame (end_image_url)")
                payload[spec["end_image_key"]] = end_image
        elif image or inputs.get("end_image_url"):
            raise ValueError(
                f"{model} is a text-to-video route and accepts no image input; "
                f"use operation='image_to_video'"
            )

        for field in spec["optional_fields"]:
            if inputs.get(field) is not None:
                payload[field] = inputs[field]

        return modelrunner_client.merge_extra_params(payload, inputs.get("extra_params"))

    @staticmethod
    def _upload_value(value: str | None, api_key: str) -> str | None:
        if not value or _is_remote(value):
            return value
        return modelrunner_client.upload_media(value, api_key)

    @staticmethod
    def _resolve_aliases(inputs: dict[str, Any]) -> dict[str, Any]:
        """Normalize the image-input aliases onto the canonical keys (no uploads)."""
        resolved = dict(inputs)
        aliases = {
            "image_url": ("image_url", "reference_image_url", "image_path", "reference_image_path"),
            "end_image_url": ("end_image_url", "last_image_url", "end_image_path", "last_image_path"),
        }
        for target, sources in aliases.items():
            value = next((resolved.get(key) for key in sources if resolved.get(key)), None)
            if value:
                resolved[target] = str(value)
        return resolved

    def _upload_local_media(self, payload: dict[str, Any], spec: dict[str, Any], api_key: str) -> None:
        """Upload any local media in the validated payload to ModelRunner storage.

        Runs AFTER payload validation so an invalid call never leaves an
        orphaned upload behind.
        """
        for key in (spec["image_key"], spec["end_image_key"]):
            if key and payload.get(key):
                payload[key] = self._upload_value(str(payload[key]), api_key)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = modelrunner_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="MODELRUNNER_KEY not set. " + self.install_instructions)

        started = time.time()
        operation = self._resolve_operation(inputs)
        queue: dict[str, Any] = {}
        try:
            poll_interval, poll_timeout = modelrunner_client.parse_poll_controls(inputs, 5.0, 1200.0)
            model = self._resolve_model(str(inputs.get("model", _DEFAULT_MODEL)), operation)
            payload = self._build_payload(self._resolve_aliases(inputs), model)
            self._upload_local_media(payload, VIDEO_MODELS[model], api_key)
            queue = modelrunner_client.submit(model, payload, api_key)
            data = modelrunner_client.poll(
                queue["status_url"], api_key,
                interval=poll_interval,
                timeout=poll_timeout,
            )
            result = modelrunner_client.get_result(queue["response_url"], api_key)
            source_url = modelrunner_client.extract_outputs(result, "single")[0]
            output_path = Path(inputs.get("output_path") or f"modelrunner_video.{VIDEO_MODELS[model]['output_format']}")
            modelrunner_client.download(source_url, output_path)
        except (modelrunner_client.ModelRunnerError, ValueError, KeyError) as exc:
            return self._failure(exc, queue, started)
        except Exception as exc:  # noqa: BLE001
            return self._failure(exc, queue, started)

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        cost_inputs = {**inputs, "model": model, "resolution": payload["resolution"], "duration": payload["duration"]}
        return ToolResult(
            success=True,
            data={
                "provider": "modelrunner", "model": model, "prompt": inputs.get("prompt", ""),
                "operation": operation, "output": str(output_path), "output_path": str(output_path),
                "request_id": queue["request_id"], "source_url": source_url,
                "format": output_path.suffix.lstrip("."), "request_params": payload, **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(cost_inputs),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )

    def _failure(self, exc: Exception, queue: dict[str, Any], started: float) -> ToolResult:
        """Failed result with honest billing provenance.

        Pre-submit failures cost nothing. After a submit the job exists
        server-side, so the queue coordinates and a billing caveat ride along
        (the request may still complete and bill; never auto-resubmit).
        """
        known = queue or getattr(exc, "queue", {})
        data: dict[str, Any] = {}
        if known:
            data = {**known, "billing_status": "possibly_billed"}
        return ToolResult(
            success=False,
            error=f"ModelRunner video generation failed: {exc}",
            data=data,
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
        )
