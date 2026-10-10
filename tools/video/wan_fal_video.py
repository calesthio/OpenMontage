"""Wan 3.0 hosted by fal, separate from the local Wan engine."""

from tools.fal_media import FalMedia


class WanFalVideo(FalMedia):
    name = "wan_fal_video"
    capability = "video_generation"
    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = dict.fromkeys(
        [
            "text_to_video",
            "image_to_video",
            "reference_to_video",
            "native_audio",
            "reference_video",
            "reference_audio",
        ],
        True,
    )
    best_for = ["Wan 3.0 generation using a fal account"]
    routes = {
        "wan-3.0": {
            op: f"alibaba/wan-3.0/{op.replace('_', '-')}" for op in capabilities
        }
    }
