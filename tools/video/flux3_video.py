"""Schema-backed flux3_video on fal; no automatic host/model fallback."""

from tools.fal_media import FalMedia


class Flux3Video(FalMedia):
    name = "flux3_video"
    capability = "video_generation"
    routes = {
        "flux-3-max": {
            "text_to_video": "blackforestlabs/flux-3-max/text-to-video",
            "image_to_video": "blackforestlabs/flux-3-max/image-to-video",
        }
    }
    capabilities = ["text_to_video", "image_to_video"]
    best_for = ["flux3_video"]
