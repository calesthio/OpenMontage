"""DreamAPI model catalog.

Endpoints and limits follow the public dreamfaceapp/skill tools. A model id is
the only way to reach an endpoint. Unknown ids never receive the API key.
Prices are account-specific, so this catalog does not invent a dollar rate.
"""

from __future__ import annotations

from typing import Any

FieldKind = str


def _field(
    key: str,
    kind: FieldKind,
    *,
    json_key: str | None = None,
    required: bool = False,
    choices: tuple[str, ...] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    max_items: int | None = None,
    max_length: int | None = None,
    multiple_of: int | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "json": json_key or key,
        "kind": kind,
        "required": required,
        "choices": choices,
        "min": min_value,
        "max": max_value,
        "max_items": max_items,
        "max_length": max_length,
        "multiple_of": multiple_of,
    }


def _prompt(max_length: int = 4000) -> dict[str, Any]:
    return _field("prompt", "string", required=True, max_length=max_length)


def _media(key: str, json_key: str | None = None, required: bool = False) -> dict[str, Any]:
    return _field(key, "media", json_key=json_key, required=required)


def _medias(key: str, json_key: str, max_items: int, required: bool = False) -> dict[str, Any]:
    return _field(key, "media_list", json_key=json_key, required=required, max_items=max_items)


_SEEDANCE_SHARED = [
    _medias("images", "images", 9),
    _media("image_url", "imageUrl"),
    _media("end_image_url", "endImageUrl"),
    _field("ratio", "string"),
    _field("seed", "number"),
    _field("generate_audio", "boolean", json_key="generateAudio"),
]


def _entry(
    model_id: str,
    capability: str,
    endpoint: str,
    note: str,
    fields: list[dict[str, Any]],
    *,
    constants: dict[str, Any] | None = None,
    shape: str | None = None,
) -> tuple[str, dict[str, Any]]:
    return model_id, {
        "id": model_id,
        "capability": capability,
        "endpoint": endpoint,
        "note": note,
        "fields": fields,
        "constants": constants or {},
        "shape": shape,
    }


MODELS: dict[str, dict[str, Any]] = dict([
    _entry("dreamvideo-3-text", "video_generation", "/api/async/dreamvideo_3.0/text_to_video", "Text to video, 3-15s.", [_prompt(), _field("duration", "number", min_value=3, max_value=15), _field("resolution", "string", choices=("480P", "720P")), _field("aspect_ratio", "string", json_key="aspectRatio", choices=("auto", "9:16", "3:4", "1:1", "4:3", "16:9")), _field("seed", "number")]),
    _entry("dreamvideo-3-image", "video_generation", "/api/async/dreamvideo_3.0/image_to_video", "One image, or two images for first-last frame.", [_prompt(), _medias("images", "images", 9, True), _field("duration", "number", min_value=3, max_value=15), _field("resolution", "string", choices=("480P", "720P")), _field("aspect_ratio", "string", json_key="aspectRatio", choices=("auto", "9:16", "3:4", "1:1", "4:3", "16:9")), _field("seed", "number")]),
    _entry("wan-2.1-text", "video_generation", "/api/async/wan/text_to_video/2.1", "Wan 2.1 text to video.", [_prompt(1500), _field("resolution", "string", choices=("480p", "720p"))]),
    _entry("wan-2.1-image", "video_generation", "/api/async/wan/image_to_video/2.1", "Wan 2.1 image to video.", [_prompt(1500), _media("image", "image", True), _field("resolution", "string", choices=("480p", "720p"))]),
    _entry("wan-2.1-head-tail", "video_generation", "/api/async/wan/head_tail_to_video/2.1", "Wan 2.1 first and last frame.", [_prompt(1500), _media("first", "firstImage", True), _media("last", "lastImage", True)]),
    _entry("seedance-2.5", "video_generation", "/api/async/seedance_2.5", "Seedance 2.5, 4-30s.", [_prompt(1500), _field("resolution", "string", required=True, choices=("480p", "720p", "1080p")), _field("duration", "number", required=True, min_value=4, max_value=30), *_SEEDANCE_SHARED, _medias("videos", "videos", 10), _medias("audios", "audios", 3), _field("omni_reference_task_type", "string", json_key="omniReferenceTaskType", choices=("reference", "edit", "extend"))], constants={"model": "seedance-2.5"}),
    _entry("seedance-2.0", "video_generation", "/api/async/seedance_2.0", "Seedance 2.0, 4-15s, up to 4k.", [_prompt(1500), _field("resolution", "string", required=True, choices=("480p", "720p", "1080p", "4k")), _field("duration", "number", required=True, min_value=4, max_value=15), *_SEEDANCE_SHARED, _medias("videos", "videos", 3), _medias("audios", "audios", 3)], constants={"model": "seedance-2.0"}),
    _entry("seedance-2.0-mini", "video_generation", "/api/async/seedance_2.0", "Seedance 2.0 Mini, 480p or 720p.", [_prompt(1500), _field("resolution", "string", required=True, choices=("480p", "720p")), _field("duration", "number", required=True, min_value=4, max_value=15), *_SEEDANCE_SHARED, _medias("videos", "videos", 3), _medias("audios", "audios", 3)], constants={"model": "seedance-2.0-mini"}),
    _entry("dreamimage-2", "image_generation", "/api/async/dreamimage_2.0", "Edit an image with a prompt.", [_prompt(), _media("image", "image", True)]),
    _entry("flux-text", "image_generation", "/api/async/flux_text2image", "Flux text to image.", [_prompt(), _field("width", "number", min_value=16, max_value=1600, multiple_of=16), _field("height", "number", min_value=16, max_value=1600, multiple_of=16), _field("num", "number", min_value=1, max_value=10), _field("seed", "number")]),
    _entry("flux-image", "image_generation", "/api/async/flux_image2image", "Flux image to image, one reference.", [_prompt(), _media("image", "imageUrl", True), _field("width", "number", min_value=16, max_value=1600, multiple_of=16), _field("height", "number", min_value=16, max_value=1600, multiple_of=16), _field("num", "number", min_value=1, max_value=10), _field("seed", "number")]),
    _entry("seedream", "image_generation", "/api/async/seedream", "Seedream 4.0, 4.5, 5.0 Lite, or 5.0 Pro.", [_field("seedream_model", "string", json_key="model", choices=("seedream-5.0-pro", "seedream-5.0-lite", "seedream-4.5", "seedream-4.0")), _prompt(), _medias("images", "image", 10), _field("size", "string"), _field("seed", "number")]),
    _entry("nano-banana-2", "image_generation", "/api/async/google_gemini_image", "Nano Banana 2.", [_field("text", "string", required=True), _field("image_size", "string", json_key="imageSize", choices=("512", "1K", "2K", "4K")), _field("aspect_ratio", "string", json_key="aspectRatio"), _medias("images", "images", 14)], constants={"model": "gemini-3.1-flash-image-preview"}),
    _entry("nano-banana-pro", "image_generation", "/api/async/google_gemini_image", "Nano Banana Pro.", [_field("text", "string", required=True), _field("image_size", "string", json_key="imageSize", choices=("1K", "2K")), _field("aspect_ratio", "string", json_key="aspectRatio"), _medias("images", "images", 14)], constants={"model": "gemini-3-pro-image-preview"}),
    _entry("gpt-image-2", "image_generation", "/api/async/gpt_image", "GPT Image 2.", [_prompt(), _field("width", "number", min_value=16, max_value=3840, multiple_of=16), _field("height", "number", min_value=16, max_value=3840, multiple_of=16), _field("quality", "string", choices=("low", "medium", "high")), _field("n", "number", min_value=1, max_value=10), _medias("images", "images", 4)]),
    _entry("gpt-image-2.5-flare-text", "image_generation", "/api/async/gpt_image_2.5/flare/text_to_image", "GPT Image 2.5 Flare text to image.", [_prompt(), _field("width", "number", min_value=16, max_value=3840, multiple_of=16), _field("height", "number", min_value=16, max_value=3840, multiple_of=16), _field("quality", "string", choices=("low", "medium", "high", "xhigh", "max")), _field("n", "number", min_value=1, max_value=10)]),
    _entry("gpt-image-2.5-flare-image", "image_generation", "/api/async/gpt_image_2.5/flare/image_to_image", "GPT Image 2.5 Flare image to image.", [_prompt(), _field("width", "number", min_value=16, max_value=3840, multiple_of=16), _field("height", "number", min_value=16, max_value=3840, multiple_of=16), _field("quality", "string", choices=("low", "medium", "high", "xhigh", "max")), _field("n", "number", min_value=1, max_value=10), _medias("images", "images", 4, True)]),
    _entry("gpt-image-2.5-sunburst-text", "image_generation", "/api/async/gpt_image_2.5/sunburst/text_to_image", "GPT Image 2.5 Sunburst text to image.", [_prompt(), _field("width", "number", min_value=16, max_value=3840, multiple_of=16), _field("height", "number", min_value=16, max_value=3840, multiple_of=16), _field("quality", "string", choices=("low", "medium", "high", "xhigh", "max")), _field("n", "number", min_value=1, max_value=10)]),
    _entry("gpt-image-2.5-sunburst-image", "image_generation", "/api/async/gpt_image_2.5/sunburst/image_to_image", "GPT Image 2.5 Sunburst image to image.", [_prompt(), _field("width", "number", min_value=16, max_value=3840, multiple_of=16), _field("height", "number", min_value=16, max_value=3840, multiple_of=16), _field("quality", "string", choices=("low", "medium", "high", "xhigh", "max")), _field("n", "number", min_value=1, max_value=10), _medias("images", "images", 4, True)]),
    _entry("colorize", "image_generation", "/api/async/colorize", "Colorize a face photo.", [_media("url", "url", True)]),
    _entry("enhance", "image_generation", "/api/async/enhance", "Enhance one image.", [_media("image", "imageUrl", True)]),
    _entry("outpainting", "image_generation", "/api/async/outpainting", "Expand an image by pixel margins.", [_media("url", "url", True), _field("left", "number", min_value=0), _field("right", "number", min_value=0), _field("top", "number", min_value=0), _field("bottom", "number", min_value=0)], shape="outpaint"),
    _entry("swap-face", "image_generation", "/api/async/swap_face", "Swap a face in an image.", [_media("url", "url", True), _media("face", "faceImgUrl", True)]),
    _entry("remove-background", "image_generation", "/api/async/remove_background", "Remove an image background.", [_media("url", "url", True)]),
    _entry("try-on", "image_generation", "/api/async/tryon_clothes", "Virtual try-on. Provide upper, lower, or overall.", [_media("model_image", "modelImage", True), _media("upper", "upperClothes"), _media("lower", "lowerClothes"), _media("overall", "overallClothes"), _field("prompt", "string"), _field("enable_shoes", "boolean", json_key="enableShoes"), _field("width", "number", min_value=1), _field("height", "number", min_value=1)]),
    _entry("lipsync", "avatar", "/api/async/lipsync", "Drive a video with new audio.", [_media("src_video", "srcVideoUrl", True), _media("audio", "audioUrl", True), _field("video_width", "number", min_value=0), _field("video_height", "number", min_value=0), _field("video_enhance", "boolean")], shape="lipsync"),
    _entry("lipsync-2", "avatar", "/api/async/lipsync/2.0", "Lip sync 2.0 with optional vocal audio.", [_media("src_video", "srcVideoUrl", True), _media("audio", "audioUrl", True), _media("vocal_audio", "vocalAudioUrl"), _field("video_width", "number", min_value=0), _field("video_height", "number", min_value=0), _field("video_enhance", "number", min_value=0, max_value=1), _field("fps", "string")], shape="lipsync2"),
    _entry("dreamavatar-3-fast", "avatar", "/api/async/dreamavatar/image_to_video/3.0fast", "Portrait plus audio, max about 3 minutes.", [_media("image", "image", True), _media("audio", "audio", True), _prompt(), _field("resolution", "string", choices=("480p", "720p"))]),
    _entry("dreamact", "video_generation", "/api/async/wan/dreamact/2.1", "Motion transfer. Driving video max about 1 minute.", [_media("video", "video", True), _medias("images", "images", 8, True), _field("seed", "number"), _field("resolution", "string", choices=("480P", "720P")), _field("task_mode", "string", json_key="taskMode", choices=("replace_body", "pose2v")), _field("quality_mode", "string", json_key="qualityMode", choices=("high", "base"))]),
    _entry("video-translate-2", "video_generation", "/api/async/video_translate/2.0", "Translate speech among en, zh, and es.", [_media("video", "videoUrl", True), _field("source_language", "string", json_key="sourceLanguage", required=True, choices=("en", "zh", "es")), _field("target_language", "string", json_key="targetLanguage", required=True, choices=("en", "zh", "es")), _field("enable_lip_sync", "boolean", json_key="enableLipSync")]),
    _entry("swap-face-video", "video_generation", "/api/async/swap_face_for_video", "Swap a face in a video, max about 5 minutes.", [_media("src_video", "srcVideoUrl", True), _media("face", "srcImgUrl", True)]),
    _entry("video-matting", "video_generation", "/api/async/image_matting_process_video", "Matte an MP4 and keep the alpha.", [_media("src_file", "srcFileUrl", True), _field("bit_rate", "string", json_key="bitRate"), _field("remove_color_spill", "boolean", json_key="removeColorSpill")]),
    _entry("matting-composite", "video_generation", "/api/async/image_matting_composite_video", "Composite a matted video over a new background.", [_media("src_file", "srcFileUrl", True), _media("alpha", "mattingAlphaFileUrl", True), _field("background_type", "string", json_key="backgroundType", required=True, choices=("color", "image", "video")), _field("background_color", "string", json_key="backgroundColor"), _media("background_url", "backgroundUrl")]),
    _entry("watermark-remover", "video_generation", "/api/async/video_watermark_remover", "Remove a watermark. Max about 120s and 2K.", [_media("video", "video", True), _field("prompt", "string"), _field("seed", "number")]),
    _entry("video-enhance", "video_generation", "/api/async/video_super_resolution", "Enhance one video.", [_media("src_video", "srcVideoUrl", True)]),
    _entry("voice-clone", "tts", "/api/async/voice_clone", "Clone a voice and return cloneId.", [_media("voice_url", "voiceUrl", True)]),
    _entry("tts-clone", "tts", "/api/async/do_tts_clone", "Speak with a cloned voice.", [_field("clone_id", "string", json_key="cloneId", required=True), _field("text", "string", required=True), _field("lang", "string", json_key="lan", required=True)]),
    _entry("tts-common", "tts", "/api/async/do_tts_common", "Standard DreamAPI voices.", [_field("audio_id", "string", json_key="audioId", required=True), _field("text", "string", required=True), _field("lang", "string", json_key="lan", required=True)]),
    _entry("tts-pro", "tts", "/api/async/do_tts_pro", "Pro DreamAPI voices.", [_field("audio_id", "string", json_key="audioId", required=True), _field("text", "string", required=True), _field("lang", "string", json_key="lan", required=True)]),
])

_SEEDREAM_LIMITS = {
    "seedream-5.0-pro": (921600, 4624220, {"1K", "1.5K", "2K"}),
    "seedream-5.0-lite": (3686400, 16777216, {"2K", "3K", "4K"}),
    "seedream-4.5": (3686400, 16777216, {"2K", "4K"}),
    "seedream-4.0": (921600, 16777216, {"1K", "2K", "4K"}),
}


def models_for(capability: str) -> dict[str, dict[str, Any]]:
    return {model_id: spec for model_id, spec in MODELS.items() if spec["capability"] == capability}


def _read_field(field: dict[str, Any], value: Any) -> Any:
    if value is None or value == "":
        return None
    kind = field["kind"]
    key = field["key"]
    if kind in {"string", "media"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        text = value.strip()
        if field["choices"] and text not in field["choices"]:
            raise ValueError(f"{key} must be one of {', '.join(field['choices'])}")
        if field["max_length"] is not None and len(text) > field["max_length"]:
            raise ValueError(f"{key} must be at most {field['max_length']} characters")
        return text
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        if field["min"] is not None and value < field["min"]:
            raise ValueError(f"{key} must be at least {field['min']}")
        if field["max"] is not None and value > field["max"]:
            raise ValueError(f"{key} must be at most {field['max']}")
        if field["multiple_of"] and int(value) % field["multiple_of"] != 0:
            raise ValueError(f"{key} must be a multiple of {field['multiple_of']}")
        return value
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")
        return value
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{key} must be an array of strings")
    items = [item.strip() for item in value]
    if field["required"] and not items:
        raise ValueError(f"{key} is required")
    if field["max_items"] is not None and len(items) > field["max_items"]:
        raise ValueError(f"{key} accepts at most {field['max_items']} items")
    return items


def _seedream_size_error(model: str, size: str) -> str | None:
    limits = _SEEDREAM_LIMITS.get(model)
    if limits is None:
        return f"Unknown Seedream model: {model}"
    minimum, maximum, tiers = limits
    normalized = size.strip().upper().replace(" ", "")
    if normalized in tiers:
        return None
    parts = normalized.lower().replace("*", "x").split("x")
    if len(parts) != 2:
        return f"Invalid size {size} for {model}"
    width, height = int(parts[0]), int(parts[1])
    total = width * height
    if total < minimum or total > maximum:
        return f"size {size} is outside {model} pixel range"
    if width * 16 < height or height * 16 < width:
        return f"size {size} aspect ratio is outside 1:16 to 16:1"
    return None


def _shape(spec: dict[str, Any], flat: dict[str, Any]) -> dict[str, Any]:
    shape = spec["shape"]
    if shape == "outpaint":
        return {"url": flat["url"], "outPaintSize": {"left": flat.get("left", 0), "right": flat.get("right", 0), "top": flat.get("top", 0), "bottom": flat.get("bottom", 0)}}
    if shape in {"lipsync", "lipsync2"}:
        body: dict[str, Any] = {
            "srcVideoUrl": flat["srcVideoUrl"],
            "audioUrl": flat["audioUrl"],
            "videoParams": {
                "video_width": flat.get("videoWidth", flat.get("video_width", 0)),
                "video_height": flat.get("videoHeight", flat.get("video_height", 0)),
                "video_enhance": flat.get("videoEnhance", flat.get("video_enhance", 1 if shape == "lipsync2" else False)),
            },
        }
        if flat.get("vocalAudioUrl"):
            body["vocalAudioUrl"] = flat["vocalAudioUrl"]
        if flat.get("fps"):
            body["fps"] = flat["fps"]
        return body
    return flat


def build_body(model_id: str, inputs: dict[str, Any], capability: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate inputs and return ``(spec, json_body)``. No network."""
    spec = MODELS.get(model_id)
    if spec is None:
        raise ValueError(f"Unknown DreamAPI model {model_id!r}. Use get_info()['model_catalog'].")
    if spec["capability"] != capability:
        raise ValueError(f"{model_id} is a {spec['capability']} model, not {capability}")
    allowed = {field["key"] for field in spec["fields"]}
    for key, value in inputs.items():
        if value is not None and key not in allowed and key not in {"model", "output_path", "poll_interval", "poll_timeout", "task_id"}:
            raise ValueError(f"{key} is not supported by DreamAPI model {model_id}")
    flat = dict(spec["constants"])
    for field in spec["fields"]:
        value = _read_field(field, inputs.get(field["key"]))
        if value is None:
            if field["required"]:
                raise ValueError(f"{field['key']} is required for DreamAPI model {model_id}")
            continue
        flat[field["json"]] = value
    if model_id == "try-on" and not any(flat.get(key) for key in ("upperClothes", "lowerClothes", "overallClothes")):
        raise ValueError("try-on requires upper, lower, or overall")
    if flat.get("endImageUrl") and not flat.get("imageUrl"):
        raise ValueError("end_image_url requires image_url")
    if isinstance(flat.get("size"), str):
        error = _seedream_size_error(str(flat.get("model", "seedream-5.0-pro")), flat["size"])
        if error:
            raise ValueError(error)
    if model_id == "video-translate-2" and flat.get("sourceLanguage") == flat.get("targetLanguage"):
        raise ValueError("source_language and target_language must differ")
    return spec, _shape(spec, flat)
