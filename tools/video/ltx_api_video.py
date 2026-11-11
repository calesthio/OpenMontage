"""LTX-2.5 Fast and Pro direct asynchronous API."""

from tools.schema_media import SchemaMedia


class LTXAPIVideo(SchemaMedia):
    name = "ltx_api_video"
    provider = "ltx"
    capability = "video_generation"
    credential = "LTX_API_KEY"
    dependencies = ["env:LTX_API_KEY"]
    install_instructions = "Configure LTX_API_KEY from https://console.ltx.io."
    catalog_file = "ltx_refresh.json"
    capabilities = ["text_to_video", "image_to_video", "audio_to_video"]
    supports = dict.fromkeys(capabilities + ["native_audio", "last_frame"], True)
    best_for = [
        "LTX-2.5 Fast/Pro direct video at verified resolution and FPS combinations"
    ]
    models = {
        model: {
            op: op.replace("_", "-")
            for op in ["text_to_video", "image_to_video", "audio_to_video"]
        }
        for model in ["ltx-2-5-fast", "ltx-2-5-pro"]
    }
