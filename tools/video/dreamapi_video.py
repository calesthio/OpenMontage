"""DreamAPI video generation and video editing."""

from __future__ import annotations

from tools.dreamapi_models import models_for
from tools.dreamapi_tool import DreamApiTool

_MODELS = sorted(models_for("video_generation"))


class DreamApiVideo(DreamApiTool):
    name = "dreamapi_video"

    def _dreamapi_concrete(self) -> None:
        return None
    capability = "video_generation"
    capabilities = ["text_to_video", "image_to_video", "video_edit", "video_translate", "face_swap", "matting"]
    default_output = "dreamapi_video.mp4"
    supports = {**DreamApiTool.supports, "text_to_video": True, "image_to_video": True}
    best_for = [
        "DreamVideo 3.0 text and image video",
        "Wan 2.1 and Seedance routes on one DreamAPI key",
        "video translation, face swap, matting, and enhancement",
    ]
    fallback_tools = ["atlas_video", "seedance_video", "wan_fal_video"]
    input_schema = {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string", "enum": _MODELS},
            "prompt": {"type": "string"},
            "image": {"type": "string"},
            "images": {"type": "array", "items": {"type": "string"}},
            "videos": {"type": "array", "items": {"type": "string"}},
            "audios": {"type": "array", "items": {"type": "string"}},
            "first": {"type": "string"},
            "last": {"type": "string"},
            "video": {"type": "string"},
            "src_video": {"type": "string"},
            "src_file": {"type": "string"},
            "face": {"type": "string"},
            "alpha": {"type": "string"},
            "image_url": {"type": "string"},
            "end_image_url": {"type": "string"},
            "duration": {"type": "integer"},
            "resolution": {"type": "string"},
            "ratio": {"type": "string"},
            "aspect_ratio": {"type": "string"},
            "seed": {"type": "integer"},
            "generate_audio": {"type": "boolean"},
            "omni_reference_task_type": {"type": "string"},
            "source_language": {"type": "string", "enum": ["en", "zh", "es"]},
            "target_language": {"type": "string", "enum": ["en", "zh", "es"]},
            "enable_lip_sync": {"type": "boolean"},
            "task_mode": {"type": "string", "enum": ["replace_body", "pose2v"]},
            "quality_mode": {"type": "string", "enum": ["high", "base"]},
            "background_type": {"type": "string", "enum": ["color", "image", "video"]},
            "background_color": {"type": "string"},
            "background_url": {"type": "string"},
            "bit_rate": {"type": "string"},
            "remove_color_spill": {"type": "boolean"},
            "output_path": {"type": "string"},
            "task_id": {"type": "string"},
        },
    }
