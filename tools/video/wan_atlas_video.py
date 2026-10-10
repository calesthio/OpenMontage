"""Wan 3.0 through Atlas Cloud, using its native reference contract."""

from tools.schema_media import SchemaMedia


class WanAtlasVideo(SchemaMedia):
    name = "wan_atlas_video"
    provider = "atlascloud"
    capability = "video_generation"
    credential = "ATLASCLOUD_API_KEY"
    dependencies = ["env:ATLASCLOUD_API_KEY"]
    install_instructions = "Configure ATLASCLOUD_API_KEY."
    catalog_file = "atlas_refresh.json"
    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = dict.fromkeys(capabilities + ["native_audio"], True)
    best_for = ["Wan 3.0 native and ESR video through Atlas Cloud"]
    models = {
        "wan-3.0": {
            op: "alibaba/wan-3.0/" + op.replace("_", "-") for op in capabilities
        }
    }
