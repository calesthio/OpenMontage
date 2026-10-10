"""Ideogram 4.5 generation and precision edits on fal."""

from tools.fal_media import FalMedia


class IdeogramFalImage(FalMedia):
    name = "ideogram_fal_image"
    capability = "image_generation"
    capabilities = ["text_to_image", "image_edit", "precise_edit"]
    supports = {"image_edit": True, "mask": True, "multiple_reference_images": True}
    best_for = ["Precise regional edits and readable typography"]
    routes = {
        "ideogram-4.5": {
            "generate": "ideogram/v4.5",
            "edit": "ideogram/v4.5/edit",
            "precise_edit": "ideogram/v4.5/edit",
        }
    }
