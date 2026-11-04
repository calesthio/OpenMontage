"""Atlas Cloud image generation and editing with exact model schemas."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import atlas_client
from tools.atlas_models import IMAGE_MODELS, IMAGE_ROUTES
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

_DEFAULT_MODEL = "bytedance/seedream-v5.0-pro/text-to-image"
_DEFAULT_COST = 0.04
_COMMON_RATIOS = ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]


def _is_remote(entry: str) -> bool:
    return str(entry).strip().lower().startswith(("http://", "https://", "data:", "asset://"))


class AtlasImage(BaseTool):
    name = "atlas_image"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "atlascloud"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:ATLASCLOUD_API_KEY"]
    install_instructions = atlas_client.INSTALL_INSTRUCTIONS
    agent_skills = ["atlas-cloud", "flux-best-practices"]

    capabilities = ["generate_image", "text_to_image", "image_edit", "layer_decomposition"]
    supports = {
        "custom_size": True, "aspect_ratio": True, "image_edit": True,
        "multiple_reference_images": True, "layer_decomposition": True,
        "multi_model_gateway": True,
    }
    provider_matrix = {
        family: {key: value for key, value in routes.items()}
        for family, routes in IMAGE_ROUTES.items()
    }
    best_for = [
        "Seedream 5.0 Pro generation, multi-image editing, and layer decomposition",
        "GPT Image 2 generation and editing with arbitrary supported dimensions",
        "Nano Banana 2 generation and editing up to 4K with as many as 14 references",
    ]
    not_good_for = ["offline generation", "assuming one parameter schema fits every Atlas model"]
    fallback_tools = ["flux_image", "google_imagen", "openai_image", "recraft_image"]
    quality_score = 0.86

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "default": _DEFAULT_MODEL, "enum": sorted(IMAGE_MODELS)},
            "generation_mode": {"type": "string", "enum": ["generate", "edit", "decompose"], "default": "generate"},
            "width": {"type": "integer", "default": 2048},
            "height": {"type": "integer", "default": 2048},
            "aspect_ratio": {"type": "string"},
            "resolution": {"type": "string"},
            "quality": {"type": "string", "enum": ["low", "medium", "high"]},
            "thinking": {"type": "string", "enum": ["enabled", "disabled"]},
            "prompt_optimization_mode": {"type": "string", "enum": ["standard", "fast"]},
            "thinking_level": {"type": "string", "enum": ["default", "high", "minimal"]},
            "media_resolution": {"type": "string", "enum": ["default", "low", "medium", "high"]},
            "enable_web_search": {"type": "boolean"},
            "enable_image_search": {"type": "boolean"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "output_format": {"type": "string", "enum": ["default", "jpeg", "png"], "default": "png"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 2.0},
            "poll_timeout": {"type": "number", "default": 600.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=250, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "generation_mode", "width", "height", "aspect_ratio"]
    side_effects = ["writes image files to output_path", "calls Atlas Cloud API"]
    user_visible_verification = ["Inspect generated images for prompt fidelity and edit consistency"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if atlas_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["model_catalog"] = {
            model_id: {
                "family": spec["family"], "operation": spec["operation"],
                "cost_per_image": spec["cost_per_image"], "size_style": spec["size_style"],
                "media_style": spec["media_style"], "max_images": spec.get("max_images"),
            }
            for model_id, spec in IMAGE_MODELS.items()
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            model = self._resolve_model(
                str(inputs.get("model", _DEFAULT_MODEL)),
                str(inputs.get("generation_mode", "generate")),
            )
        except ValueError:
            return _DEFAULT_COST
        return float(IMAGE_MODELS[model]["cost_per_image"])

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    def _resolve_model(self, model: str, operation: str) -> str:
        if model not in IMAGE_MODELS:
            raise ValueError(
                f"Unsupported Atlas image model id {model!r}. Use get_info()['model_catalog'] for live routes."
            )
        family = IMAGE_MODELS[model]["family"]
        route = IMAGE_ROUTES.get(family, {}).get(operation)
        if not route:
            raise ValueError(f"{family} does not expose generation_mode={operation!r} on Atlas Cloud")
        return route

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        spec = IMAGE_MODELS[model]
        payload: dict[str, Any] = {"model": model, "prompt": inputs.get("prompt", "")}
        width = int(inputs.get("width", 2048))
        height = int(inputs.get("height", 2048))
        style = spec["size_style"]

        if style == "star":
            payload["size"] = f"{width}*{height}"
        elif style == "x":
            payload["size"] = f"{width}x{height}"
        elif style == "ratio":
            payload["aspect_ratio"] = inputs.get("aspect_ratio") or atlas_client.aspect_ratio_from_size(
                width, height, _COMMON_RATIOS
            )
        elif style == "tier":
            payload["size"] = inputs.get("resolution", "auto")

        images = list(inputs.get("image_urls") or [])
        if inputs.get("image_url"):
            images.insert(0, inputs["image_url"])
        media_style = spec["media_style"]
        if media_style == "images":
            maximum = int(spec["max_images"])
            if not images:
                raise ValueError(f"{spec['operation']} requires at least one source image")
            if len(images) > maximum:
                raise ValueError(f"{model} accepts at most {maximum} source images")
            payload["images"] = images
        elif media_style == "image":
            if len(images) != 1:
                raise ValueError("layer decomposition requires exactly one source image")
            payload["image"] = images[0]

        for field in spec.get("optional_fields", ()):
            if inputs.get(field) is not None:
                payload[field] = inputs[field]
        if inputs.get("output_format") and inputs["output_format"] != "default":
            payload["output_format"] = inputs["output_format"]

        extra = inputs.get("extra_params")
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    @staticmethod
    def _upload_value(value: str, api_key: str) -> str:
        return value if _is_remote(value) else atlas_client.upload_media(value, api_key)

    def _resolve_media(self, inputs: dict[str, Any], api_key: str) -> dict[str, Any]:
        resolved = dict(inputs)
        urls = [str(value) for value in resolved.get("image_urls", [])]
        paths = [str(value) for value in resolved.get("image_paths", [])]
        if resolved.get("image_url"):
            urls.insert(0, str(resolved["image_url"]))
        if resolved.get("image_path"):
            paths.insert(0, str(resolved["image_path"]))
        resolved["image_urls"] = [self._upload_value(value, api_key) for value in [*urls, *paths]]
        resolved.pop("image_url", None)
        return resolved

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = atlas_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="ATLASCLOUD_API_KEY not set. " + self.install_instructions)

        started = time.time()
        operation = str(inputs.get("generation_mode", "generate"))
        try:
            model = self._resolve_model(str(inputs.get("model", _DEFAULT_MODEL)), operation)
            resolved = self._resolve_media(inputs, api_key)
            payload = self._build_payload(resolved, model)
            prediction_id = atlas_client.submit(atlas_client.GENERATE_IMAGE_ENDPOINT, payload, api_key)
            data = atlas_client.poll(
                prediction_id, api_key,
                interval=float(inputs.get("poll_interval", 2.0)),
                timeout=float(inputs.get("poll_timeout", 600.0)),
            )
            outputs = list(data["outputs"])
            requested = Path(inputs.get("output_path") or "atlas_image.png")
            output_paths: list[Path] = []
            for index, url in enumerate(outputs):
                output_path = requested if index == 0 else requested.with_name(f"{requested.stem}_{index + 1}{requested.suffix}")
                atlas_client.download(url, output_path)
                output_paths.append(output_path)
        except (atlas_client.AtlasError, ValueError, KeyError) as exc:
            return ToolResult(success=False, error=f"Atlas Cloud image generation failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"Atlas Cloud image generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "atlascloud", "model": model, "prompt": inputs.get("prompt", ""),
                "generation_mode": operation, "output": str(output_paths[0]),
                "output_path": str(output_paths[0]), "outputs": [str(path) for path in output_paths],
                "prediction_id": prediction_id, "source_url": outputs[0], "source_urls": outputs,
                "request_params": payload,
            },
            artifacts=[str(path) for path in output_paths], cost_usd=self.estimate_cost({**inputs, "model": model}),
            duration_seconds=round(time.time() - started, 2), model=model,
        )
