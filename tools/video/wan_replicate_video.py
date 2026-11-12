"""Wan 3.0 through Replicate; no unsupported reference-video routing."""

from tools.schema_media import SchemaMedia


class WanReplicateVideo(SchemaMedia):
    name = "wan_replicate_video"
    provider = "replicate"
    capability = "video_generation"
    credential = "REPLICATE_API_TOKEN"
    dependencies = ["env:REPLICATE_API_TOKEN"]
    install_instructions = "Configure REPLICATE_API_TOKEN."
    catalog_file = "replicate_refresh.json"
    capabilities = ["text_to_video", "image_to_video"]
    supports = dict.fromkeys(capabilities, True)
    best_for = ["Wan 3.0 text or first-frame video through Replicate"]
    models = {"wan-3.0": {op: "alibaba/wan-3" for op in capabilities}}

    def estimate_cost(self, inputs):
        return {"480p": 0.05, "720p": 0.10, "1080p": 0.20}[
            inputs.get("resolution", "1080p")
        ] * inputs.get("duration", 5)
