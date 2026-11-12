"""GPT Image 2.5 and Nano Banana Pro on Atlas Cloud."""

from tools.schema_media import SchemaMedia


class AtlasRefreshImage(SchemaMedia):
    name = "atlas_refresh_image"
    provider = "atlascloud"
    capability = "image_generation"
    credential = "ATLASCLOUD_API_KEY"
    dependencies = ["env:ATLASCLOUD_API_KEY"]
    install_instructions = "Configure ATLASCLOUD_API_KEY."
    catalog_file = "atlas_refresh.json"
    capabilities = ["text_to_image", "image_edit"]
    supports = {"image_edit": True, "multiple_reference_images": True}
    best_for = ["GPT Image 2.5 and Nano Banana Pro generation and edits on Atlas"]
    models = {
        model: {"generate": family + "/text-to-image", "edit": family + "/edit"}
        for model, family in [
            ("gpt-image-2.5-flare", "openai/gpt-image-2.5-flare"),
            ("gpt-image-2.5-sunburst", "openai/gpt-image-2.5-sunburst"),
            ("gemini-3-pro-image", "google/nano-banana-pro"),
        ]
    }
