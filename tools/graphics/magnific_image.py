"""Magnific image generation — Mystic plus the Flux / Seedream / Z-Image catalog.

Mystic is Magnific's own workflow and the default here: photoreal output up to
4K with structure and style references, and `@character` LoRA syntax in the
prompt. The other models are reached through the shared text-to-image endpoints.

Mystic's parameters are modelled in full. The other models each have their own
request schema, so only the parameters they all share are typed here — anything
model-specific goes through `params`, which is merged into the request body
verbatim.

API: https://docs.magnific.com/api-reference/mystic/mystic
"""

from __future__ import annotations

from typing import Any, NamedTuple

from tools import _magnific as mag
from tools._magnific import MagnificTool
from tools.base_tool import Determinism, ToolResult, ToolTier

_DEFAULT_MODEL = "mystic"

# 4K Mystic costs materially more, and takes longer, than 1k/2k.
_4K_MULTIPLIER = 2.0


class ImageModel(NamedTuple):
    """One model's endpoint and planning hints.

    `cost` is approximate USD per image and `runtime` approximate seconds.
    Magnific bills in credits with no published per-model USD rate, so these are
    planning estimates for budget gates, not invoice values.
    """

    path: str
    cost: float
    runtime: float


_MODELS: dict[str, ImageModel] = {
    _DEFAULT_MODEL: ImageModel("/v1/ai/mystic", 0.05, 45.0),
    "flux_2_pro": ImageModel("/v1/ai/text-to-image/flux-2-pro", 0.05, 30.0),
    "flux_2_turbo": ImageModel("/v1/ai/text-to-image/flux-2-turbo", 0.02, 12.0),
    "flux_dev": ImageModel("/v1/ai/text-to-image/flux-dev", 0.02, 20.0),
    "flux_kontext_pro": ImageModel("/v1/ai/text-to-image/flux-kontext-pro", 0.05, 30.0),
    "hyperflux": ImageModel("/v1/ai/text-to-image/hyperflux", 0.01, 8.0),
    "seedream_v5_pro": ImageModel("/v1/ai/text-to-image/seedream-v5-pro", 0.05, 30.0),
    "seedream_v5_lite": ImageModel("/v1/ai/text-to-image/seedream-v5-lite", 0.02, 15.0),
    "seedream_v4_5": ImageModel("/v1/ai/text-to-image/seedream-v4-5", 0.04, 25.0),
    "nano_banana_pro": ImageModel("/v1/ai/text-to-image/nano-banana-pro", 0.05, 30.0),
    "z_image": ImageModel("/v1/ai/text-to-image/z-image", 0.01, 10.0),
    "runway_t2i": ImageModel("/v1/ai/text-to-image/runway", 0.04, 25.0),
}

_ASPECT_RATIOS = [
    "square_1_1", "classic_4_3", "traditional_3_4", "widescreen_16_9",
    "social_story_9_16", "smartphone_horizontal_20_9", "smartphone_vertical_9_20",
    "standard_3_2", "portrait_2_3", "horizontal_2_1", "vertical_1_2",
    "social_5_4", "social_post_4_5",
]


class MagnificImage(MagnificTool):
    """Generate a still image through the Magnific API."""

    name = "magnific_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    determinism = Determinism.STOCHASTIC
    agent_skills = ["flux-best-practices", "visual-style", "bfl-api"]

    capabilities = ["text_to_image", "style_transfer", "structure_reference"]
    supports = {
        "text_to_image": True,
        "style_reference": True,
        "structure_reference": True,
        "character_lora": True,
        "up_to_4k": True,
        "multi_model_routing": True,
        "fixed_generation": True,
    }
    best_for = [
        "photoreal stills at 4K with a house style locked by a style_reference image",
        "editorial-grade close-up portraits (model=mystic, mystic_model=editorial_portraits)",
        "turning a sketch or 3D blockout into a finished frame via structure_reference",
        "reaching Flux 2, Seedream 5, and Nano Banana Pro on one Magnific key",
    ]
    not_good_for = ["offline generation", "precise text rendering at small sizes", "vector output"]
    fallback_tools = ["flux_image", "seedream_image", "image_gen", "openai_image"]
    quality_score = 0.9

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Scene description. Mystic also accepts @character or @character::strength LoRA syntax.",
            },
            "model": {"type": "string", "enum": sorted(_MODELS), "default": _DEFAULT_MODEL},
            "output_path": {"type": "string", "default": "magnific_image.png"},
            "aspect_ratio": {"type": "string", "enum": _ASPECT_RATIOS, "default": "square_1_1"},

            # --- mystic only ---
            "mystic_model": {
                "type": "string",
                "enum": ["realism", "fluid", "zen", "flexible", "super_real", "editorial_portraits"],
                "default": "realism",
                "description": "Mystic sub-model. fluid/flexible/super_real/editorial_portraits ignore LoRAs.",
            },
            "resolution": {"type": "string", "enum": ["1k", "2k", "4k"], "default": "2k"},
            "engine": {
                "type": "string",
                "enum": ["automatic", "magnific_illusio", "magnific_sharpy", "magnific_sparkle"],
                "default": "automatic",
            },
            "structure_reference": {"type": "string", "description": "Image whose shapes guide the result. Disables LoRAs."},
            "structure_strength": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
            "style_reference": {"type": "string", "description": "Image whose aesthetic guides the result. Disables LoRAs."},
            "adherence": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
            "hdr": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
            "creative_detailing": {"type": "integer", "minimum": 0, "maximum": 100, "default": 33},
            "fixed_generation": {"type": "boolean", "default": False, "description": "Same settings -> same image."},

            "filter_nsfw": {"type": "boolean", "default": True},
            "params": {
                "type": "object",
                "description": "Model-specific body fields merged verbatim into the request.",
            },
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"output_path": {"type": "string"}, "output_paths": {"type": "array"}},
    }

    idempotency_key_fields = ["prompt", "model", "mystic_model", "resolution", "aspect_ratio"]
    side_effects = ["writes image files to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = ["Check hands, faces, and any rendered text before approving the frame"]

    @staticmethod
    def _multiplier(inputs: dict[str, Any]) -> float:
        # `resolution` is only sent for Mystic; scaling anything else by it would
        # quote (and reserve budget for) 2x a request that never changes.
        is_mystic = inputs.get("model", _DEFAULT_MODEL) == _DEFAULT_MODEL
        return _4K_MULTIPLIER if is_mystic and inputs.get("resolution") == "4k" else 1.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        spec = _MODELS.get(inputs.get("model", _DEFAULT_MODEL))
        if spec is None:
            return 0.0
        return round(spec.cost * self._multiplier(inputs), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        spec = _MODELS.get(inputs.get("model", _DEFAULT_MODEL))
        return 0.0 if spec is None else spec.runtime * self._multiplier(inputs)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not mag.api_key():
            return self._unconfigured()

        model = inputs.get("model", _DEFAULT_MODEL)
        spec = _MODELS.get(model)
        if spec is None:
            return ToolResult(
                success=False,
                error=f"Unknown Magnific image model {model!r}. Known: {', '.join(sorted(_MODELS))}",
            )

        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "aspect_ratio": mag.normalize_ratio(inputs.get("aspect_ratio"), _ASPECT_RATIOS),
        }
        extra: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "aspect_ratio": inputs.get("aspect_ratio", "square_1_1"),
        }

        if model == _DEFAULT_MODEL:
            payload.update({
                "model": inputs.get("mystic_model"),
                "resolution": inputs.get("resolution"),
                "engine": inputs.get("engine"),
                "structure_strength": inputs.get("structure_strength") if inputs.get("structure_reference") else None,
                "adherence": inputs.get("adherence") if inputs.get("style_reference") else None,
                "hdr": inputs.get("hdr") if inputs.get("style_reference") else None,
                "creative_detailing": inputs.get("creative_detailing"),
                "fixed_generation": inputs.get("fixed_generation"),
                "filter_nsfw": inputs.get("filter_nsfw"),
            })
            try:
                for field in ("structure_reference", "style_reference"):
                    if inputs.get(field):
                        payload[field] = mag.as_input(inputs[field])
            except Exception as e:
                return ToolResult(success=False, error=f"Could not read a reference image: {e}")
            extra["mystic_model"] = inputs.get("mystic_model", "realism")
            extra["resolution"] = inputs.get("resolution", "2k")

        else:
            ignored = [f for f in ("structure_reference", "style_reference") if inputs.get(f)]
            if ignored:
                return ToolResult(
                    success=False,
                    error=(
                        f"{', '.join(ignored)} only applies to model='mystic'; "
                        f"{model!r} would silently ignore it and still cost credits."
                    ),
                )

        if isinstance(inputs.get("params"), dict):
            payload.update(inputs["params"])

        return self._generate(
            inputs, spec.path, payload, model=model, data_extra=extra, saves=None
        )
