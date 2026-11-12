"""Schema-backed vidu_video on fal; no automatic host/model fallback."""

from tools.fal_media import FalMedia


class ViduVideo(FalMedia):
    name = "vidu_video"
    capability = "video_generation"
    routes = {
        "vidu-q4": {
            "image_to_video": "fal-ai/vidu/q4/image-to-video",
            "reference_to_video": "fal-ai/vidu/q4/reference-to-video",
        }
    }
    capabilities = ["image_to_video", "reference_to_video"]
    best_for = ["vidu_video"]
