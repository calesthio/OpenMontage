"""Authoritative ModelRunner model catalog used by the media gateway tools.

Every entry is keyed by the exact live endpoint id (`owner/alias`) and mirrors
the machine-readable schema and pricing served by the ModelRunner catalog API
(GET https://api.modelrunner.run/models) and each model's live page. Keeping
route ids explicit prevents a valid text-to-video id from being rewritten to a
sibling route that does not exist.

Rates were verified against the live catalog on 2026-08-28 (PRICING_SNAPSHOT).
Several routes bill per second of finished video at a rate that depends on the
chosen `resolution` — those carry a rate table, not a single number. Confirm
current pricing on the live model page before quoting or spending on a batch.
"""

from __future__ import annotations

from typing import Any

PRICING_SNAPSHOT = "2026-08-28"

# Rough planning heuristic for speech-length estimates (English narration runs
# ~13-17 characters per spoken second). Only used by estimate_cost().
CHARS_PER_SECOND_OF_SPEECH = 15


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

_WAN_27_RATES = {"720P": 0.10, "1080P": 0.15}
_WAN_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4")
_HAPPY_HORSE_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4", "4:5", "5:4", "9:21", "21:9")
_SEEDANCE_MINI_RATES = {"480p": 0.053, "720p": 0.113}
_SEEDANCE_RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive")

VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "wan-video/wan/v2.7/text-to-video": {
        "family": "wan-video/wan/v2.7",
        "operation": "text_to_video",
        "rates_per_output_second": dict(_WAN_27_RATES),
        "default_rate": 0.15,
        "durations": (2, 15),
        "default_duration": 5,
        "resolutions": ("720P", "1080P"),
        # The API defaults to 1080P; the tool defaults to the cheaper 720P
        # tier because OpenMontage drafts first and re-renders keepers.
        "default_resolution": "720P",
        "ratio_key": "aspect_ratio",
        "ratios": _WAN_RATIOS,
        "default_ratio": "16:9",
        "prompt_required": True,
        "image_key": None,
        "end_image_key": None,
        "optional_fields": ("negative_prompt", "seed", "enable_prompt_expansion"),
        "native_audio": True,
        "output_format": "mp4",
    },
    "wan-video/wan/v2.7/image-to-video": {
        "family": "wan-video/wan/v2.7",
        "operation": "image_to_video",
        "rates_per_output_second": dict(_WAN_27_RATES),
        "default_rate": 0.15,
        "durations": (2, 15),
        "default_duration": 5,
        "resolutions": ("720P", "1080P"),
        "default_resolution": "720P",
        # The clip inherits its frame shape from the source image; the route
        # accepts no aspect-ratio field at all.
        "ratio_key": None,
        "ratios": (),
        "default_ratio": None,
        "prompt_required": False,
        "image_key": "start_image_url",
        "end_image_key": "end_image_url",
        "optional_fields": ("negative_prompt", "seed", "enable_prompt_expansion"),
        "native_audio": True,
        "output_format": "mp4",
    },
    "alibaba/happy-horse/v1.1/text-to-video": {
        "family": "alibaba/happy-horse/v1.1",
        "operation": "text_to_video",
        "rates_per_output_second": {"720P": 0.14, "1080P": 0.18},
        "default_rate": 0.18,
        "durations": (3, 15),
        "default_duration": 5,
        "resolutions": ("720P", "1080P"),
        "default_resolution": "720P",
        "ratio_key": "ratio",
        "ratios": _HAPPY_HORSE_RATIOS,
        "default_ratio": "16:9",
        "prompt_required": True,
        "image_key": None,
        "end_image_key": None,
        "optional_fields": ("seed",),
        "native_audio": True,  # dialogue written in the prompt is lip-synced
        "output_format": "mp4",
    },
    "bytedance/seedance-v2-mini/text-to-video": {
        "family": "bytedance/seedance-v2-mini",
        "operation": "text_to_video",
        "rates_per_output_second": dict(_SEEDANCE_MINI_RATES),
        "default_rate": 0.113,
        "durations": (4, 15),
        "default_duration": 5,
        "resolutions": ("480p", "720p"),
        "default_resolution": "720p",
        "ratio_key": "aspect_ratio",
        "ratios": _SEEDANCE_RATIOS,
        "default_ratio": "16:9",
        "prompt_required": True,
        "image_key": None,
        "end_image_key": None,
        "optional_fields": ("generate_audio",),
        "native_audio": True,
        "output_format": "mp4",
    },
    "bytedance/seedance-v2-mini/image-to-video": {
        "family": "bytedance/seedance-v2-mini",
        "operation": "image_to_video",
        "rates_per_output_second": dict(_SEEDANCE_MINI_RATES),
        "default_rate": 0.113,
        "durations": (4, 15),
        "default_duration": 5,
        "resolutions": ("480p", "720p"),
        "default_resolution": "720p",
        "ratio_key": "aspect_ratio",
        "ratios": _SEEDANCE_RATIOS,
        "default_ratio": "adaptive",  # keeps the source image's frame shape
        "prompt_required": True,  # this route requires a motion prompt
        "image_key": "image",
        "end_image_key": None,
        "optional_fields": ("generate_audio",),
        "native_audio": True,
        "output_format": "mp4",
    },
}


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------

# Standard preset canvases (shared by the routes that take an `image_size`
# preset or a custom {width, height} object). Used to estimate megapixel and
# aspect handling; the provider renders the authoritative dimensions.
IMAGE_SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "square": (512, 512),
    "square_hd": (1024, 1024),
    "portrait_4_3": (768, 1024),
    "portrait_16_9": (576, 1024),
    "landscape_4_3": (1024, 768),
    "landscape_16_9": (1024, 576),
}

_SEEDREAM_BASE_SIZES = (
    "1024x1024", "1376x768", "768x1376", "1264x848", "848x1264", "1200x896", "896x1200",
)
_SEEDREAM_2K_SIZES = (
    "2048x2048", "2752x1536", "1536x2752", "2528x1696", "1696x2528", "2400x1792", "1792x2400",
)

IMAGE_MODELS: dict[str, dict[str, Any]] = {
    "bytedance/seedream-v5/text-to-image": {
        "family": "bytedance/seedream-v5",
        "operation": "text_to_image",
        "cost_per_image": 0.035,
        # `size` is a fixed WxH enum; every option is 2K-class and the price
        # is flat across all of them.
        "size_style": "wxh_enum",
        "sizes": _SEEDREAM_2K_SIZES,
        "default_size": "2048x2048",
        "size_rates": None,
        "optional_fields": (),
        "output_format": "jpeg",
    },
    "bytedance/seedream-v5-pro/text-to-image": {
        "family": "bytedance/seedream-v5-pro",
        "operation": "text_to_image",
        "cost_per_image": 0.09,
        "size_style": "wxh_enum",
        "sizes": _SEEDREAM_BASE_SIZES + _SEEDREAM_2K_SIZES,
        "default_size": "1024x1024",
        # The per-image price is tiered by the chosen size: ~1-2.4MP canvases
        # bill at the lower rate, 2K-class canvases at the premium rate.
        "size_rates": {
            **{size: 0.045 for size in _SEEDREAM_BASE_SIZES},
            **{size: 0.09 for size in _SEEDREAM_2K_SIZES},
        },
        "optional_fields": (),
        "output_format": "jpeg",
    },
    "recraft/v4.1/text-to-image": {
        "family": "recraft/v4.1",
        "operation": "text_to_image",
        "cost_per_image": 0.035,
        # `image_size` takes a named preset or a custom {width, height}
        # object (up to 2048x2048 / ultra-wide crops).
        "size_style": "preset_or_dims",
        "sizes": tuple(IMAGE_SIZE_PRESETS),
        "default_size": "square_hd",
        "size_rates": None,
        "max_dimension": 2048,
        "optional_fields": (),
        "output_format": "webp",
    },
    "recraft/v4.1/pro/text-to-image": {
        "family": "recraft/v4.1/pro",
        "operation": "text_to_image",
        "cost_per_image": 0.21,
        "size_style": "preset_or_dims",
        "sizes": tuple(IMAGE_SIZE_PRESETS),
        "default_size": "square_hd",
        "size_rates": None,
        "max_dimension": 2048,
        "optional_fields": (),
        "output_format": "webp",
    },
    "stability-ai/stable-diffusion-v3.5-large": {
        "family": "stability-ai/stable-diffusion-v3.5",
        "operation": "text_to_image",
        # Billed per megapixel of OUTPUT, not per image.
        "cost_per_megapixel": 0.065,
        "cost_per_image": None,
        "size_style": "preset_or_dims",
        "sizes": tuple(IMAGE_SIZE_PRESETS),
        "default_size": "landscape_4_3",
        "size_rates": None,
        "max_dimension": 2048,
        "optional_fields": (
            "negative_prompt", "guidance_scale", "num_inference_steps", "output_format", "seed",
        ),
        "output_format": "jpeg",
    },
}


# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------

TTS_MODELS: dict[str, dict[str, Any]] = {
    "hexgrad/kokoro-82m": {
        "family": "hexgrad/kokoro-82m",
        # Billed by GPU compute time ($0.000225/s on the serving GPU), not by
        # audio length — a typical clip costs a fraction of a cent. The
        # estimate below is an upper-bound approximation.
        "billing": "compute_time",
        "estimated_cost_per_audio_second": 0.000015,
        "minimum_estimate": 0.0001,
        "text_key": "text",
        "max_text_length": None,
        "default_voice": "af_bella",
        # 46 named voices across 6 languages; the two-letter prefix encodes
        # language and gender (af_/am_ American, bf_/bm_ British English,
        # ff_ French, hf_/hm_ Hindi, if_/im_ Italian, jf_/jm_ Japanese,
        # zf_/zm_ Mandarin). Values are passed through and validated by the
        # API before any billing happens.
        "voice_note": "46 voices; prefix = language+gender (af_=US female, am_=US male, ...)",
        "speed_range": (0.1, 5.0),
        "optional_fields": (),
        "output_format": "wav",
        "languages": "en fr hi it ja zh",
    },
    "google/gemini-3.1-flash-tts": {
        "family": "google/gemini-3.1-flash-tts",
        "billing": "per_audio_second",
        "cost_per_audio_second": 0.0006,
        # This route takes one `prompt` field carrying "{style direction}:
        # {text}" — the tool composes it from `instructions` + `text`.
        "text_key": "prompt",
        "max_text_length": 7500,  # combined direction+text cap is ~8000 bytes
        "default_voice": "Kore",
        "voice_note": "30 prebuilt voices (Kore, Puck, Aoede, Charon, Sulafat, ...)",
        "speed_range": None,
        "optional_fields": ("language_code",),
        "output_format": "wav",
        "languages": "24 locales via language_code (default en-us)",
    },
    "elevenlabs/tts/multilingual-v2": {
        "family": "elevenlabs/tts/multilingual-v2",
        "billing": "per_audio_second",
        "cost_per_audio_second": 0.0015,
        "text_key": "text",
        "max_text_length": None,
        "default_voice": "Rachel",
        "voice_note": "21 named voices (Rachel, Aria, Roger, Sarah, Charlie, George, ...)",
        "speed_range": (0.7, 1.2),
        "optional_fields": (
            "stability", "similarity_boost", "style", "language_code",
            "apply_text_normalization", "previous_text", "next_text",
        ),
        "output_format": "mp3",
        "languages": "29 languages, auto-detected or forced via language_code",
    },
    "resemble-ai/chatterbox/text-to-speech/multilingual": {
        "family": "resemble-ai/chatterbox",
        "billing": "per_audio_second",
        "cost_per_audio_second": 0.000375,
        "text_key": "text",
        "max_text_length": 300,
        # On this route `voice` selects the LANGUAGE (english, french,
        # german, spanish, ...), not a named speaker.
        "default_voice": "english",
        "voice_note": "voice = language selector (english, french, german, spanish, ...23 total)",
        "speed_range": None,
        "optional_fields": ("exaggeration", "temperature", "cfg_scale", "seed"),
        "output_format": "wav",
        "languages": "23 languages via the voice selector",
    },
}

# ISO 639-1 -> Chatterbox multilingual `voice` (language selector) values.
CHATTERBOX_LANGUAGES = {
    "en": "english", "ar": "arabic", "da": "danish", "de": "german", "el": "greek",
    "es": "spanish", "fi": "finnish", "fr": "french", "he": "hebrew", "hi": "hindi",
    "it": "italian", "ja": "japanese", "ko": "korean", "ms": "malay", "nl": "dutch",
    "no": "norwegian", "pl": "polish", "pt": "portuguese", "ru": "russian",
    "sv": "swedish", "sw": "swahili", "tr": "turkish", "zh": "chinese",
}


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------

MUSIC_MODELS: dict[str, dict[str, Any]] = {
    "google/lyria2": {
        "family": "google/lyria2",
        "cost_per_output": 0.06,
        "fixed_duration_seconds": 30,  # ~30s, no duration control
        "duration_range": None,
        "duration_key": None,
        "vocals": False,  # instrumental only
        "optional_fields": ("negative_prompt", "seed"),
        "output_format": "wav",
    },
    "google/lyria-3/clip": {
        "family": "google/lyria-3",
        "cost_per_output": 0.04,
        "fixed_duration_seconds": 30,
        "duration_range": None,
        "duration_key": None,
        "vocals": True,  # sings lyrics by default; prompt "instrumental only" to suppress
        "optional_fields": (),
        "output_format": "mp3",
    },
    "stability-ai/stable-audio-2.5/text-to-audio": {
        "family": "stability-ai/stable-audio-2.5",
        "cost_per_output": 0.20,  # flat per generation regardless of length
        "fixed_duration_seconds": None,
        "duration_range": (1, 190),
        "duration_key": "seconds_total",
        "vocals": False,
        "optional_fields": ("guidance_scale", "num_inference_steps", "seed"),
        "output_format": "wav",
    },
}


def operation_routes(catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Return family -> operation -> exact live endpoint id."""
    routes: dict[str, dict[str, str]] = {}
    for model_id, spec in catalog.items():
        routes.setdefault(spec["family"], {})[spec["operation"]] = model_id
    return routes


VIDEO_ROUTES = operation_routes(VIDEO_MODELS)
IMAGE_ROUTES = operation_routes(IMAGE_MODELS)
