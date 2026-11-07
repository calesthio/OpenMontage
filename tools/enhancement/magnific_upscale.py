"""Magnific AI image upscaling (Creative and Precision engines).

Creative reimagines detail as it enlarges — prompt-guided, hallucinating texture
that was never in the source. Precision is faithful super-resolution: sharper
edges and micro-contrast with no invented content. Pick by `mode`.

API: https://docs.magnific.com/api-reference/image-upscaler-creative/image-upscaler
"""

from __future__ import annotations

from typing import Any

from tools import _magnific as mag
from tools._magnific import MagnificTool
from tools.base_tool import Determinism, ToolResult, ToolTier

_CREATIVE_PATH = "/v1/ai/image-upscaler"
_PRECISION_PATH = "/v1/ai/image-upscaler-precision"

# Approximate USD per call. Magnific bills in credits and does not publish a
# per-endpoint USD rate, so these are order-of-magnitude figures for planning and
# budget gates only — reconcile real spend against the Analytics API.
_COST_BY_SCALE = {"2x": 0.06, "4x": 0.12, "8x": 0.24, "16x": 0.48}
_RUNTIME_BY_SCALE = {"2x": 45.0, "4x": 90.0, "8x": 180.0, "16x": 360.0}
_PRECISION_COST = 0.05


class MagnificUpscale(MagnificTool):
    """Upscale a still image through the Magnific API."""

    name = "magnific_upscale"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "image_upscale"
    determinism = Determinism.STOCHASTIC
    agent_skills = ["flux-best-practices", "visual-style"]

    capabilities = ["image_upscale", "detail_enhancement"]
    supports = {
        "creative_upscale": True,
        "faithful_upscale": True,
        "prompt_guided": True,
        "up_to_16x": True,
        "style_presets": True,
    }
    best_for = [
        "rescuing low-resolution stills for large-format or 4K delivery",
        "adding believable texture to AI-generated images (reuse the original prompt)",
        "faithful super-resolution of logos, UI captures, and scans (mode=precision)",
    ]
    not_good_for = [
        "video frames in bulk (per-frame API cost and no temporal consistency)",
        "offline or free upscaling — use the local `upscale` tool for that",
    ]
    fallback_tools = ["upscale", "face_enhance"]
    quality_score = 0.92

    input_schema = {
        "type": "object",
        "required": ["image"],
        "properties": {
            "image": {
                "type": "string",
                "description": "Local file path, public https URL, or base64. A URL preserves the most quality.",
            },
            "mode": {
                "type": "string",
                "enum": ["creative", "precision"],
                "default": "creative",
                "description": "creative = prompt-guided detail invention; precision = faithful, no new content.",
            },
            "output_path": {"type": "string", "default": "magnific_upscaled.png"},

            # --- creative mode ---
            "scale_factor": {"type": "string", "enum": ["2x", "4x", "8x", "16x"], "default": "2x"},
            "optimized_for": {
                "type": "string",
                "enum": [
                    "standard", "soft_portraits", "hard_portraits", "art_n_illustration",
                    "videogame_assets", "nature_n_landscapes", "films_n_photography",
                    "3d_renders", "science_fiction_n_horror",
                ],
                "default": "standard",
            },
            "prompt": {"type": "string", "description": "Guides creative upscaling. Reuse the source image's own prompt."},
            "creativity": {"type": "integer", "minimum": -10, "maximum": 10, "default": 0},
            "hdr": {"type": "integer", "minimum": -10, "maximum": 10, "default": 0},
            "resemblance": {"type": "integer", "minimum": -10, "maximum": 10, "default": 0},
            "fractality": {"type": "integer", "minimum": -10, "maximum": 10, "default": 0},
            "engine": {
                "type": "string",
                "enum": ["automatic", "magnific_illusio", "magnific_sharpy", "magnific_sparkle"],
                "default": "automatic",
            },

            # --- precision mode ---
            "sharpen": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
            "smart_grain": {"type": "integer", "minimum": 0, "maximum": 100, "default": 7},
            "ultra_detail": {"type": "integer", "minimum": 0, "maximum": 100, "default": 30},

            "filter_nsfw": {"type": "boolean", "default": False},
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "mode": {"type": "string"},
            "format": {"type": "string"},
        },
    }

    idempotency_key_fields = ["image", "mode", "scale_factor", "prompt", "engine"]
    side_effects = ["writes an image to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = [
        "Open the output at 100% zoom and check edges, skin, and text for invented artifacts",
    ]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("mode", "creative") == "precision":
            return _PRECISION_COST
        return _COST_BY_SCALE.get(inputs.get("scale_factor", "2x"), 0.06)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Larger scale factors take proportionally longer per the API docs.
        return _RUNTIME_BY_SCALE.get(inputs.get("scale_factor", "2x"), 45.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not mag.api_key():
            return self._unconfigured()

        mode = inputs.get("mode", "creative")
        try:
            image = mag.as_input(inputs["image"])
        except Exception as e:
            return ToolResult(success=False, error=f"Could not read image input: {e}")

        common = {"image": image, "filter_nsfw": inputs.get("filter_nsfw")}
        if mode == "precision":
            endpoint = _PRECISION_PATH
            payload = {
                **common,
                "sharpen": inputs.get("sharpen"),
                "smart_grain": inputs.get("smart_grain"),
                "ultra_detail": inputs.get("ultra_detail"),
            }
            extra: dict[str, Any] = {"mode": mode}
        else:
            endpoint = _CREATIVE_PATH
            payload = {
                **common,
                "scale_factor": inputs.get("scale_factor"),
                "optimized_for": inputs.get("optimized_for"),
                "prompt": inputs.get("prompt"),
                "creativity": inputs.get("creativity"),
                "hdr": inputs.get("hdr"),
                "resemblance": inputs.get("resemblance"),
                "fractality": inputs.get("fractality"),
                "engine": inputs.get("engine"),
            }
            extra = {
                "mode": mode,
                "scale_factor": inputs.get("scale_factor", "2x"),
                "engine": inputs.get("engine", "automatic"),
            }

        return self._generate(
            inputs, endpoint, payload, model=f"magnific_upscaler_{mode}", data_extra=extra
        )
