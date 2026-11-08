"""Schema-backed flux3_fal_image on fal; no automatic host/model fallback."""

from tools.fal_media import FalMedia


class Flux3FalImage(FalMedia):
    name = "flux3_fal_image"
    capability = "image_generation"
    routes = {
        "flux-3-image": {
            "generate": "blackforestlabs/flux-3/text-to-image",
            "edit": "blackforestlabs/flux-3/edit-image",
        }
    }
    capabilities = ["generate", "edit"]
    best_for = ["flux3_fal_image"]
