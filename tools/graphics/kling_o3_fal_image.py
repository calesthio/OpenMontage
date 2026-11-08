"""Kling Image O3 text and reference-image generation on fal.ai."""
from tools.fal_media import FalMedia


class KlingO3FalImage(FalMedia):
    name = "kling_o3_fal_image"
    capability = "image_generation"
    capabilities = ["text_to_image", "image_to_image"]
    supports = {"text_to_image": True, "image_to_image": True}
    best_for = ["Kling Image O3 images and reference-image edits on fal.ai"]
    routes = {
        "kling-o3-image": {
            "text_to_image": "fal-ai/kling-image/o3/text-to-image",
            "image_to_image": "fal-ai/kling-image/o3/image-to-image",
        }
    }

    def build_request(self, inputs):
        operation = inputs.get("generation_mode") or inputs.get("operation")
        if not operation or operation == "generate":
            operation = "image_to_image" if any(
                inputs.get(k) for k in ("image_url", "image_urls", "image_path", "image_paths")
            ) else "text_to_image"
        elif operation == "edit":
            operation = "image_to_image"
        return super().build_request({**inputs, "operation": operation, "generation_mode": operation})
