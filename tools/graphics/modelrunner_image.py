"""ModelRunner image generation with exact model schemas and rate tables."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import modelrunner_client
from tools.modelrunner_models import (
    IMAGE_MODELS,
    IMAGE_ROUTES,
    IMAGE_SIZE_PRESETS,
    PRICING_SNAPSHOT,
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

_DEFAULT_MODEL = "bytedance/seedream-v5/text-to-image"
_DEFAULT_COST = 0.035
_MIN_DIMENSION = 256


def _closest_wxh(width: int, height: int, allowed: tuple[str, ...]) -> str:
    """Snap canonical width/height to the nearest supported WxH enum value.

    Callers who pass the model-native `size` field get strict validation
    instead; this adaptation only applies to OpenMontage's canonical
    width/height inputs, preferring the closest aspect ratio and breaking
    ties on pixel area.
    """
    target_ratio = width / height if height > 0 else 1.0
    target_area = max(width, 1) * max(height, 1)

    def rank(value: str) -> tuple[float, float]:
        w_text, _, h_text = value.partition("x")
        w, h = int(w_text), int(h_text)
        return (abs((w / h) - target_ratio), abs(w * h - target_area))

    return min(allowed, key=rank)


class ModelRunnerImage(BaseTool):
    name = "modelrunner_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "modelrunner"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MODELRUNNER_KEY"]
    install_instructions = modelrunner_client.INSTALL_INSTRUCTIONS
    agent_skills = ["modelrunner"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "custom_size": True,
        "aspect_ratio": True,
        "in_image_text": True,  # Seedream and SD 3.5 both render legible typography
        "multi_model_gateway": True,
    }
    provider_matrix = {
        family: dict(routes) for family, routes in IMAGE_ROUTES.items()
    }
    best_for = [
        "Seedream 5.0 Lite/Pro 2K generation with accurate in-image text at flat per-image prices",
        "Recraft V4.1 design-led brand imagery and product shots up to 2048x2048",
        "Stable Diffusion 3.5 Large stylistic range billed per output megapixel",
        "one ModelRunner key across image, video, speech, and music generation",
    ]
    not_good_for = [
        "offline generation",
        "image editing or compositing from reference images (these routes are text-to-image only)",
        "assuming one size vocabulary fits every route (Seedream uses WxH enums, others presets)",
    ]
    fallback_tools = ["atlas_image", "flux_image", "recraft_image", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "default": _DEFAULT_MODEL, "enum": sorted(IMAGE_MODELS)},
            "width": {"type": "integer", "description": "Canonical width; adapted to the closest size the route supports."},
            "height": {"type": "integer", "description": "Canonical height; adapted to the closest size the route supports."},
            "size": {"type": "string", "description": "Seedream routes: exact WxH enum value (validated strictly, no snapping)."},
            "image_size": {"description": "Recraft/SD routes: preset name (square_hd, landscape_4_3, ...) or a {width, height} object."},
            "negative_prompt": {"type": "string"},
            "guidance_scale": {"type": "number"},
            "num_inference_steps": {"type": "integer"},
            "output_format": {"type": "string", "enum": ["jpeg", "png"]},
            "seed": {"type": "integer"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 2.0},
            "poll_timeout": {"type": "number", "default": 600.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=250, network_required=True)
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "width", "height", "size", "seed"]
    side_effects = ["writes image files to output_path", "submits one paid ModelRunner API request"]
    user_visible_verification = [
        "Inspect generated images for prompt fidelity, composition, and typography accuracy",
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
                "cost_per_image": spec.get("cost_per_image"),
                "cost_per_megapixel": spec.get("cost_per_megapixel"),
                "cost_per_image_by_size": dict(spec["size_rates"]) if spec.get("size_rates") else None,
                "size_style": spec["size_style"],
                "sizes": list(spec["sizes"]),
                "default_size": spec["default_size"],
            }
            for model_id, spec in IMAGE_MODELS.items()
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            model = str(inputs.get("model", _DEFAULT_MODEL))
            spec = IMAGE_MODELS[model]
            dims = self._requested_dims(inputs, spec)
            if spec.get("cost_per_megapixel") is not None:
                megapixels = (dims[0] * dims[1]) / 1_000_000 if dims else 0.79
                return round(spec["cost_per_megapixel"] * megapixels, 4)
            if spec.get("size_rates"):
                size = self._resolve_size_value(inputs, spec)
                return float(spec["size_rates"].get(size, spec["cost_per_image"]))
            return float(spec["cost_per_image"])
        except Exception:  # noqa: BLE001 - estimates must never raise
            return _DEFAULT_COST

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 45.0

    @staticmethod
    def _requested_dims(inputs: dict[str, Any], spec: dict[str, Any]) -> tuple[int, int] | None:
        if inputs.get("width") and inputs.get("height"):
            return int(inputs["width"]), int(inputs["height"])
        image_size = inputs.get("image_size")
        if isinstance(image_size, dict) and image_size.get("width") and image_size.get("height"):
            return int(image_size["width"]), int(image_size["height"])
        if isinstance(image_size, str) and image_size in IMAGE_SIZE_PRESETS:
            return IMAGE_SIZE_PRESETS[image_size]
        size = inputs.get("size") or (spec["default_size"] if spec["size_style"] == "wxh_enum" else None)
        if isinstance(size, str) and "x" in size:
            w_text, _, h_text = size.partition("x")
            if w_text.isdigit() and h_text.isdigit():
                return int(w_text), int(h_text)
        if spec["size_style"] == "preset_or_dims":
            return IMAGE_SIZE_PRESETS.get(spec["default_size"])
        return None

    def _resolve_size_value(self, inputs: dict[str, Any], spec: dict[str, Any]) -> str:
        """Resolve the Seedream-style `size` value for a wxh_enum route."""
        size = inputs.get("size")
        if size is not None:
            if size not in spec["sizes"]:
                raise ValueError(
                    f"size={size!r} is not supported; choose one of {list(spec['sizes'])}"
                )
            return str(size)
        if inputs.get("width") and inputs.get("height"):
            return _closest_wxh(int(inputs["width"]), int(inputs["height"]), spec["sizes"])
        return str(spec["default_size"])

    def _resolve_image_size_value(self, inputs: dict[str, Any], spec: dict[str, Any]) -> Any:
        """Resolve the preset-or-dims `image_size` value for the other routes."""
        image_size = inputs.get("image_size")
        maximum = int(spec.get("max_dimension") or 2048)
        if isinstance(image_size, str):
            if image_size not in spec["sizes"]:
                raise ValueError(
                    f"image_size={image_size!r} is not a supported preset; "
                    f"choose one of {list(spec['sizes'])} or pass a {{width, height}} object"
                )
            return image_size
        if isinstance(image_size, dict):
            width, height = int(image_size.get("width", 0)), int(image_size.get("height", 0))
        elif inputs.get("width") and inputs.get("height"):
            width, height = int(inputs["width"]), int(inputs["height"])
        else:
            return spec["default_size"]
        if not (_MIN_DIMENSION <= width <= maximum and _MIN_DIMENSION <= height <= maximum):
            raise ValueError(
                f"width/height {width}x{height} out of range; each side must be "
                f"{_MIN_DIMENSION}-{maximum} pixels for this route"
            )
        return {"width": width, "height": height}

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        spec = IMAGE_MODELS[model]
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"{model} requires a non-empty prompt")
        payload: dict[str, Any] = {"prompt": prompt}

        if spec["size_style"] == "wxh_enum":
            payload["size"] = self._resolve_size_value(inputs, spec)
        else:
            payload["image_size"] = self._resolve_image_size_value(inputs, spec)

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
            poll_interval, poll_timeout = modelrunner_client.parse_poll_controls(inputs, 2.0, 600.0)
            model = str(inputs.get("model", _DEFAULT_MODEL))
            if model not in IMAGE_MODELS:
                raise ValueError(
                    f"Unsupported ModelRunner image endpoint {model!r}. "
                    f"Use get_info()['model_catalog'] for the live routes."
                )
            payload = self._build_payload(inputs, model)
            # SD 3.5 honors a caller-selected output_format; the saved file's
            # name and the reported format must describe the actual bytes.
            output_format = str(payload.get("output_format") or IMAGE_MODELS[model]["output_format"])
            queue = modelrunner_client.submit(model, payload, api_key)
            modelrunner_client.poll(
                queue["status_url"], api_key,
                interval=poll_interval,
                timeout=poll_timeout,
            )
            result = modelrunner_client.get_result(queue["response_url"], api_key)
            source_urls = modelrunner_client.extract_outputs(result, "list")
            requested = Path(inputs.get("output_path") or f"modelrunner_image.{output_format}")
            output_paths: list[Path] = []
            for index, url in enumerate(source_urls):
                output_path = requested if index == 0 else requested.with_name(
                    f"{requested.stem}_{index + 1}{requested.suffix}"
                )
                modelrunner_client.download(url, output_path)
                output_paths.append(output_path)
        except (modelrunner_client.ModelRunnerError, ValueError, KeyError) as exc:
            return self._failure(exc, queue, started)
        except Exception as exc:  # noqa: BLE001
            return self._failure(exc, queue, started)

        return ToolResult(
            success=True,
            data={
                "provider": "modelrunner", "model": model, "prompt": inputs.get("prompt", ""),
                "operation": "text_to_image", "output": str(output_paths[0]),
                "output_path": str(output_paths[0]), "outputs": [str(path) for path in output_paths],
                "request_id": queue["request_id"], "source_url": source_urls[0],
                "source_urls": source_urls, "format": output_format,
                "request_params": payload,
            },
            artifacts=[str(path) for path in output_paths],
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
            error=f"ModelRunner image generation failed: {exc}",
            data=data,
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
        )
