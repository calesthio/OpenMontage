"""GPT Image 2.5 via exact fal endpoints."""

from tools.fal_media import FalMedia


class OpenAIFalImage(FalMedia):
    name = "openai_fal_image"
    capability = "image_generation"
    capabilities = ["text_to_image", "image_edit"]
    supports = {
        "image_edit": True,
        "mask": True,
        "multiple_reference_images": True,
        "transparency": True,
    }
    best_for = ["GPT Image 2.5 with an existing fal account"]
    routes = {
        f"gpt-image-2.5-{v}": {
            "generate": f"openai/gpt-image-2.5/{v}/text-to-image",
            "edit": f"openai/gpt-image-2.5/{v}/edit",
        }
        for v in ("flare", "sunburst")
    }
