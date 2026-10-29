"""DreamAPI talking avatar and lip sync."""

from __future__ import annotations

from tools.dreamapi_models import models_for
from tools.dreamapi_tool import DreamApiTool

_MODELS = sorted(models_for("avatar"))


class DreamApiAvatar(DreamApiTool):
    name = "dreamapi_avatar"

    def _dreamapi_concrete(self) -> None:
        return None
    capability = "avatar"
    capabilities = ["talking_avatar", "lip_sync"]
    default_output = "dreamapi_avatar.mp4"
    best_for = ["DreamAvatar 3.0 Fast from a portrait and audio", "LipSync and LipSync 2.0 on an existing video"]
    fallback_tools = ["kling_avatar", "kling_lip_sync", "talking_head"]
    input_schema = {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string", "enum": _MODELS},
            "prompt": {"type": "string"},
            "image": {"type": "string"},
            "audio": {"type": "string"},
            "src_video": {"type": "string"},
            "vocal_audio": {"type": "string"},
            "resolution": {"type": "string", "enum": ["480p", "720p"]},
            "video_width": {"type": "integer"},
            "video_height": {"type": "integer"},
            "video_enhance": {"type": ["boolean", "integer"]},
            "fps": {"type": "string"},
            "output_path": {"type": "string"},
            "task_id": {"type": "string"},
        },
    }
