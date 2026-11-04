"""Authoritative Atlas Cloud model catalog used by the media gateway tools.

The entries mirror the machine-readable schemas served by each live model page.
Keeping task ids explicit prevents a valid text-to-video id from being rewritten
to a sibling route that does not actually exist.
"""

from __future__ import annotations

from typing import Any


SEEDANCE_RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive")
SEEDANCE_25_RESOLUTIONS = (
    "480p", "720p", "720p-esr", "1080p-esr", "1440p-esr", "4k-esr",
    "1080p-esr & 60fps",
)
SEEDANCE_20_RESOLUTIONS = (
    "480p", "720p", "720p-SR", "1080p", "1080p-SR", "1440p-SR", "4k",
)
H3_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")


def _video_spec(
    family: str,
    operation: str,
    rate: float,
    *,
    duration: tuple[int, ...] | None,
    resolution: tuple[str, ...],
    default_resolution: str,
    ratio_key: str,
    ratios: tuple[str, ...],
    default_ratio: str,
    media_style: str = "none",
    variant: str = "standard",
    optional_fields: tuple[str, ...] = (),
    media_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "family": family,
        "operation": operation,
        "variant": variant,
        "cost_per_second": rate,
        "durations": duration,
        "resolutions": resolution,
        "default_resolution": default_resolution,
        "ratio_key": ratio_key,
        "ratios": ratios,
        "default_ratio": default_ratio,
        "media_style": media_style,
        "optional_fields": optional_fields,
        "media_limits": media_limits or {},
    }


VIDEO_MODELS: dict[str, dict[str, Any]] = {}

for version, rate, durations, resolutions in (
    ("2.5", 0.134, tuple(range(4, 31)) + (-1,), SEEDANCE_25_RESOLUTIONS),
    ("2.0", 0.112, tuple(range(4, 16)) + (-1,), SEEDANCE_20_RESOLUTIONS),
):
    family = f"bytedance/seedance-{version}"
    common = ("generate_audio", "watermark", "return_last_frame")
    common += ("output_format",) if version == "2.5" else ("bitrate_mode",)
    for operation, suffix, media_style in (
        ("text_to_video", "text-to-video", "none"),
        ("image_to_video", "image-to-video", "seedance_image"),
        ("reference_to_video", "reference-to-video", "seedance_references"),
    ):
        model_id = f"{family}/{suffix}"
        limits = {}
        if operation == "reference_to_video":
            limits = {"images": 30, "videos": 10, "audios": 10} if version == "2.5" else {"images": 9, "videos": 3, "audios": 3}
        VIDEO_MODELS[model_id] = _video_spec(
            family,
            operation,
            rate,
            duration=durations,
            resolution=resolutions,
            default_resolution="720p",
            ratio_key="ratio",
            ratios=("adaptive",) if operation == "image_to_video" and version == "2.5" else SEEDANCE_RATIOS,
            default_ratio="adaptive",
            media_style=media_style,
            optional_fields=common,
            media_limits=limits,
        )

for operation, suffix, rate, media_style in (
    ("text_to_video", "text-to-video", 0.125, "none"),
    ("image_to_video", "image-to-video", 0.130, "gemini_image"),
    ("reference_to_video", "reference-to-video", 0.135, "gemini_images"),
    ("video_edit", "video-edit", 0.140, "gemini_video_edit"),
):
    model_id = f"google/gemini-omni-flash/{suffix}"
    VIDEO_MODELS[model_id] = _video_spec(
        "google/gemini-omni-flash",
        operation,
        rate,
        duration=None if operation == "video_edit" else tuple(range(3, 11)),
        resolution=("720p",),
        default_resolution="720p",
        ratio_key="aspect_ratio",
        ratios=("16:9", "9:16") if operation != "video_edit" else (),
        default_ratio="16:9",
        media_style=media_style,
        optional_fields=("thinking_level", "seed"),
        media_limits={"images": 10} if operation in {"reference_to_video", "video_edit"} else {},
    )

for operation, suffix, rate, media_style in (
    ("text_to_video", "text-to-video-developer", 0.112, "none"),
    ("image_to_video", "image-to-video-developer", 0.112, "gemini_images"),
    ("reference_to_video", "reference-to-video-developer", 0.120, "gemini_video_clips"),
):
    model_id = f"google/gemini-omni-flash/{suffix}"
    VIDEO_MODELS[model_id] = _video_spec(
        "google/gemini-omni-flash",
        operation,
        rate,
        duration=(4, 6, 8, 10),
        resolution=("720p", "1080p", "4k"),
        default_resolution="720p",
        ratio_key="aspect_ratio",
        ratios=("16:9", "9:16"),
        default_ratio="16:9",
        media_style=media_style,
        variant="developer",
        optional_fields=("seed",),
    )

for operation, suffix, media_style in (
    ("text_to_video", "text-to-video", "none"),
    ("image_to_video", "image-to-video", "h3_image"),
    ("reference_to_video", "reference-to-video", "h3_refers"),
):
    model_id = f"minimax/h3/{suffix}"
    VIDEO_MODELS[model_id] = _video_spec(
        "minimax/h3",
        operation,
        0.100,
        duration=tuple(range(4, 16)),
        resolution=("768P", "2K"),
        default_resolution="2K",
        ratio_key="ratio",
        ratios=("adaptive", *H3_RATIOS) if operation != "text_to_video" else H3_RATIOS,
        default_ratio="adaptive" if operation != "text_to_video" else "1:1",
        media_style=media_style,
    )


IMAGE_MODELS: dict[str, dict[str, Any]] = {
    "bytedance/seedream-v5.0-pro/text-to-image": {
        "family": "bytedance/seedream-v5.0-pro", "operation": "generate",
        "cost_per_image": 0.045, "size_style": "star", "media_style": "none",
        "optional_fields": ("thinking", "prompt_optimization_mode", "enable_base64_output"),
    },
    "bytedance/seedream-v5.0-pro/edit": {
        "family": "bytedance/seedream-v5.0-pro", "operation": "edit",
        "cost_per_image": 0.045, "size_style": "star", "media_style": "images",
        "max_images": 10,
        "optional_fields": ("thinking", "prompt_optimization_mode", "enable_base64_output"),
    },
    "bytedance/seedream-v5.0-pro/layer-decomposition": {
        "family": "bytedance/seedream-v5.0-pro", "operation": "decompose",
        "cost_per_image": 0.022, "size_style": "tier", "media_style": "image",
        "max_images": 1,
        "optional_fields": ("optimize_prompt_options", "enable_sync_mode", "enable_base64_output"),
    },
    "bytedance/seedream-v5.0-lite/edit": {
        "family": "bytedance/seedream-v5.0-lite", "operation": "edit",
        "cost_per_image": 0.032, "size_style": "star", "media_style": "images",
        "max_images": 14, "optional_fields": ("enable_base64_output",),
    },
    "openai/gpt-image-2/text-to-image": {
        "family": "openai/gpt-image-2", "operation": "generate",
        "cost_per_image": 0.009, "size_style": "x", "media_style": "none",
        "optional_fields": ("quality", "enable_sync_mode", "enable_base64_output"),
    },
    "openai/gpt-image-2/edit": {
        "family": "openai/gpt-image-2", "operation": "edit",
        "cost_per_image": 0.010, "size_style": "x", "media_style": "images",
        "max_images": 10,
        "optional_fields": ("quality", "enable_sync_mode", "enable_base64_output"),
    },
    "google/nano-banana-2/text-to-image": {
        "family": "google/nano-banana-2", "operation": "generate",
        "cost_per_image": 0.080, "size_style": "ratio", "media_style": "none",
        "optional_fields": (
            "resolution", "thinking_level", "media_resolution", "enable_web_search",
            "enable_image_search", "enable_sync_mode", "enable_base64_output",
        ),
    },
    "google/nano-banana-2/edit": {
        "family": "google/nano-banana-2", "operation": "edit",
        "cost_per_image": 0.080, "size_style": "ratio", "media_style": "images",
        "max_images": 14,
        "optional_fields": (
            "resolution", "thinking_level", "media_resolution", "enable_web_search",
            "enable_image_search", "enable_sync_mode", "enable_base64_output",
        ),
    },
}


def operation_routes(catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Return family -> operation -> exact live model id."""
    routes: dict[str, dict[str, str]] = {}
    for model_id, spec in catalog.items():
        family = spec["family"]
        operation = spec["operation"]
        variant = spec.get("variant", "standard")
        route_key = operation if variant == "standard" else f"{operation}_{variant}"
        routes.setdefault(family, {})[route_key] = model_id
    return routes


VIDEO_ROUTES = operation_routes(VIDEO_MODELS)
IMAGE_ROUTES = operation_routes(IMAGE_MODELS)
