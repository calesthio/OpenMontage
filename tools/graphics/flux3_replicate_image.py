"""FLUX 3 Image on Replicate using the captured host schema."""

from tools.schema_media import SchemaMedia


class Flux3ReplicateImage(SchemaMedia):
    name = "flux3_replicate_image"
    provider = "replicate"
    capability = "image_generation"
    credential = "REPLICATE_API_TOKEN"
    dependencies = ["env:REPLICATE_API_TOKEN"]
    install_instructions = "Configure REPLICATE_API_TOKEN."
    catalog_file = "replicate_refresh.json"
    capabilities = ["text_to_image", "image_edit"]
    supports = {"image_edit": True, "multiple_reference_images": True}
    models = {
        "flux-3-image": {
            "generate": "black-forest-labs/flux-3-image",
            "edit": "black-forest-labs/flux-3-image",
        }
    }
