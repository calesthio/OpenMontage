"""DreamAPI image generation, editing, try-on, and face swap."""

from __future__ import annotations

from tools.dreamapi_models import models_for
from tools.dreamapi_tool import DreamApiTool

_MODELS = sorted(models_for("image_generation"))


class DreamApiImage(DreamApiTool):
    name = "dreamapi_image"

    def _dreamapi_concrete(self) -> None:
        return None
    capability = "image_generation"
    capabilities = ["generate_image", "image_edit", "virtual_try_on", "face_swap", "background_removal"]
    default_output = "dreamapi_image.png"
    best_for = [
        "DreamImage 2.0 edits",
        "Flux text and image generation",
        "Seedream, Nano Banana, and GPT Image routes on one DreamAPI key",
        "virtual try-on and image face swap",
    ]
    fallback_tools = ["flux_image", "openai_image", "atlas_image"]
    input_schema = {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string", "enum": _MODELS},
            "prompt": {"type": "string"},
            "text": {"type": "string"},
            "image": {"type": "string"},
            "images": {"type": "array", "items": {"type": "string"}},
            "url": {"type": "string"},
            "face": {"type": "string"},
            "model_image": {"type": "string"},
            "upper": {"type": "string"},
            "lower": {"type": "string"},
            "overall": {"type": "string"},
            "seedream_model": {"type": "string"},
            "size": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "num": {"type": "integer"},
            "n": {"type": "integer"},
            "quality": {"type": "string"},
            "seed": {"type": "integer"},
            "image_size": {"type": "string"},
            "aspect_ratio": {"type": "string"},
            "left": {"type": "integer"},
            "right": {"type": "integer"},
            "top": {"type": "integer"},
            "bottom": {"type": "integer"},
            "enable_shoes": {"type": "boolean"},
            "output_path": {"type": "string"},
            "task_id": {"type": "string"},
        },
    }
