"""Kling O3 image-reference video through fal.ai, separate from legacy KlingVideo.

Use start_image_url for the first frame, image_urls/image_paths for appearance
references (@Image1, @Image2). No job is submitted during request validation.
"""
from tools.fal_media import FalMedia


class KlingO3FalVideo(FalMedia):
    name = "kling_o3_fal_video"
    capability = "video_generation"
    capabilities = ["reference_to_video"]
    supports = {"reference_to_video": True, "reference_image": True, "aspect_ratio": True}
    best_for = ["Kling O3 first-frame and identity-reference video via fal.ai"]
    routes = {
        "kling-o3-standard": {
            "reference_to_video": "fal-ai/kling-video/o3/standard/reference-to-video"
        },
        "kling-o3-pro": {
            "reference_to_video": "fal-ai/kling-video/o3/pro/reference-to-video"
        },
    }

    def build_request(self, inputs):
        if inputs.get("image_url"):
            raise ValueError("Use start_image_url for the first frame; image_urls are references")
        return super().build_request({"operation": "reference_to_video", **inputs})
