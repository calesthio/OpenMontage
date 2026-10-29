"""Magnific video generation — one API key across Seedance, Kling, Veo, WAN, LTX,
Hailuo, Runway, and PixVerse.

Magnific (formerly the Freepik API) is a multi-model aggregator, so this is the
direct counterpart to `higgsfield_video`: pick a `model`, everything else stays
the same. Seedance 2.0 Pro is the default, matching the house preference for
premium clips with native audio.

Endpoints verified against https://docs.magnific.com/llms.txt

API: https://docs.magnific.com/api-reference/video/seedance-2-pro/overview
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, NamedTuple, Optional

from tools import _magnific as mag
from tools._magnific import MagnificTool
from tools.base_tool import Determinism, ResourceProfile, ToolResult, ToolTier

_DEFAULT_MODEL = "seedance_2_pro_1080p"
_MAX_SEED = 4294967295


class VideoModel(NamedTuple):
    """One model's endpoints and planning hints.

    `path` serves both operations for the models with a single unified endpoint;
    `t2v`/`i2v` override it for the models that split them, and None means the
    model does not support that operation at all. `status` is the GET path when
    it differs from the POST (Seedance posts per-resolution, polls one path).
    `cost` is approximate USD for a 5s clip — Magnific bills in credits with no
    published per-model USD rate, so it is a planning estimate only.
    """

    path: str = ""
    t2v: Optional[str] = None
    i2v: Optional[str] = None
    status: Optional[str] = None
    audio: bool = False
    cost: float = 0.0
    runtime: float = 0.0

    def endpoint(self, operation: str) -> Optional[str]:
        override = self.i2v if operation == "image_to_video" else self.t2v
        if override is not None:
            return override
        return self.path or None

    def status_for(self, endpoint: str) -> str:
        return self.status or endpoint


_SEEDANCE_PRO = "/v1/ai/video/seedance-2-pro"
_SEEDANCE_2_5 = "/v1/ai/video/seedance-2-5-pro"
_KLING_V3 = "/v1/ai/video/kling-v3"

_MODELS: dict[str, VideoModel] = {
    "seedance_2_pro_480p": VideoModel(f"{_SEEDANCE_PRO}-480p", status=_SEEDANCE_PRO, audio=True, cost=0.30, runtime=90.0),
    "seedance_2_pro_720p": VideoModel(f"{_SEEDANCE_PRO}-720p", status=_SEEDANCE_PRO, audio=True, cost=0.55, runtime=120.0),
    "seedance_2_pro_1080p": VideoModel(f"{_SEEDANCE_PRO}-1080p", status=_SEEDANCE_PRO, audio=True, cost=0.85, runtime=150.0),
    "seedance_2_pro_4k": VideoModel(f"{_SEEDANCE_PRO}-4k", status=_SEEDANCE_PRO, audio=True, cost=2.00, runtime=300.0),
    "seedance_2_fast_720p": VideoModel("/v1/ai/video/seedance-2-fast-720p", status="/v1/ai/video/seedance-2-fast", audio=True, cost=0.30, runtime=60.0),
    "seedance_2_mini_720p": VideoModel("/v1/ai/video/seedance-2-mini-720p", status="/v1/ai/video/seedance-2-mini", audio=True, cost=0.15, runtime=45.0),
    "seedance_2_5_pro_1080p": VideoModel(f"{_SEEDANCE_2_5}-1080p", status=_SEEDANCE_2_5, audio=True, cost=0.85, runtime=150.0),
    "kling_v3_pro": VideoModel("/v1/ai/video/kling-v3-pro", status=_KLING_V3, cost=0.50, runtime=180.0),
    "kling_v3_std": VideoModel("/v1/ai/video/kling-v3-std", status=_KLING_V3, cost=0.25, runtime=150.0),
    "veo_3_1": VideoModel(t2v="/v1/ai/text-to-video/veo-3-1", i2v="/v1/ai/image-to-video/veo-3-1", audio=True, cost=1.50, runtime=180.0),
    "veo_3_1_fast": VideoModel(t2v="/v1/ai/text-to-video/veo-3-1-fast", i2v="/v1/ai/image-to-video/veo-3-1-fast", audio=True, cost=0.60, runtime=90.0),
    "wan_2_7": VideoModel(t2v="/v1/ai/text-to-video/wan-2-7", i2v="/v1/ai/image-to-video/wan-2-7", cost=0.20, runtime=120.0),
    "ltx_2_pro": VideoModel(t2v="/v1/ai/text-to-video/ltx-2-pro", i2v="/v1/ai/image-to-video/ltx-2-pro", audio=True, cost=0.40, runtime=120.0),
    "minimax_hailuo_2_3_1080p": VideoModel(i2v="/v1/ai/image-to-video/minimax-hailuo-2-3-1080p", cost=0.45, runtime=150.0),
    "runway_4_5": VideoModel(t2v="/v1/ai/text-to-video/runway-4-5", i2v="/v1/ai/image-to-video/runway-4-5", cost=0.50, runtime=120.0),
    "pixverse_v6": VideoModel(t2v="/v1/ai/text-to-video/pixverse-v6", cost=0.25, runtime=90.0),
}

_ASPECT_RATIOS = [
    "film_horizontal_21_9", "widescreen_16_9", "classic_4_3", "square_1_1",
    "traditional_3_4", "social_story_9_16", "film_vertical_9_21",
]


class MagnificVideo(MagnificTool):
    """Generate a video clip through the Magnific multi-model API."""

    name = "magnific_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    determinism = Determinism.SEEDED
    agent_skills = ["seedance-2-0", "seedance-2-5", "ai-video-gen"]

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=1000, network_required=True)

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_to_last_frame": True,
        "reference_images": True,
        "native_audio": True,
        "multi_model_routing": True,
        "camera_direction": True,
        "seeded": True,
    }
    best_for = [
        "multi-model video generation behind a single Magnific key",
        "Seedance 2.0 Pro clips with native synchronized audio at up to 4K",
        "first-to-last-frame transitions from two stills (image + image_end)",
        "reference-driven shots — up to 9 images cited as @Image1..@Image9 in the prompt",
    ]
    not_good_for = ["offline generation", "sub-4-second micro-clips", "frame-exact editorial control"]
    fallback_tools = ["higgsfield_video", "seedance_video", "kling_video", "veo_video"]
    quality_score = 0.89

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Scene, motion, style, and camera movement. Up to 2000 chars."},
            "model": {"type": "string", "enum": sorted(_MODELS), "default": _DEFAULT_MODEL},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
                "description": "Inferred from `image` when omitted.",
            },
            "image": {"type": "string", "description": "First-frame image: local path, https URL, or base64."},
            "image_end": {"type": "string", "description": "Last-frame image. With `image`, generates a transition."},
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 9,
                "description": "Seedance only. Cite them in the prompt as @Image1..@Image9.",
            },
            "duration": {"type": "integer", "minimum": 4, "maximum": 15, "default": 5},
            "aspect_ratio": {"type": "string", "enum": _ASPECT_RATIOS, "default": "widescreen_16_9"},
            "camera_fixed": {"type": "boolean", "default": False, "description": "true = locked tripod shot."},
            "sound_effects": {"type": "boolean", "default": True, "description": "Native audio, on models that support it."},
            "no_music": {"type": "boolean", "default": False, "description": "Keep dialogue and SFX, drop the score."},
            "seed": {
                "type": "integer",
                "minimum": -1,
                "maximum": _MAX_SEED,
                "default": -1,
                "description": "-1 draws a random seed, which is sent and reported so the clip can be reproduced.",
            },
            "output_path": {"type": "string", "default": "magnific_video.mp4"},
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"output_path": {"type": "string"}, "model": {"type": "string"}},
    }

    idempotency_key_fields = ["prompt", "model", "operation", "duration", "seed"]
    side_effects = ["writes a video file to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = ["Watch the clip for motion coherence, identity drift, and audio sync"]

    def _resolve(self, inputs: dict[str, Any]) -> tuple[str, VideoModel, str, str]:
        """Return (model, spec, operation, endpoint), raising on an unsupported combination."""
        model = inputs.get("model", _DEFAULT_MODEL)
        spec = _MODELS.get(model)
        if spec is None:
            raise ValueError(f"Unknown Magnific model {model!r}. Known: {', '.join(sorted(_MODELS))}")
        operation = inputs.get("operation") or ("image_to_video" if inputs.get("image") else "text_to_video")
        endpoint = spec.endpoint(operation)
        if endpoint is None:
            other = "image_to_video" if operation == "text_to_video" else "text_to_video"
            raise ValueError(f"Magnific model {model!r} does not support {operation}; it only supports {other}.")
        return model, spec, operation, endpoint

    @staticmethod
    def _seed(inputs: dict[str, Any]) -> int:
        """Resolve an explicit seed, or draw one so the clip stays reproducible.

        `-1` is the API's "pick randomly" sentinel, which would leave the caller
        with no way to regenerate a clip they liked.
        """
        seed = inputs.get("seed")
        if seed is None or seed == -1:
            return random.randint(0, _MAX_SEED)
        return int(seed)

    @staticmethod
    def _duration(inputs: dict[str, Any]) -> int:
        return int(inputs.get("duration", 5) or 5)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        spec = _MODELS.get(inputs.get("model", _DEFAULT_MODEL))
        return 0.0 if spec is None else round(spec.cost * (self._duration(inputs) / 5), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        spec = _MODELS.get(inputs.get("model", _DEFAULT_MODEL))
        return 0.0 if spec is None else round(spec.runtime * (self._duration(inputs) / 5), 1)

    def _max_wait(self, inputs: dict[str, Any]) -> float:
        # Video queues are deeper than the still/audio endpoints, so allow a
        # longer ceiling relative to the estimate than the shared default.
        return self.estimate_runtime(inputs) * 6 + 180

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not mag.api_key():
            return self._unconfigured()

        try:
            model, spec, operation, endpoint = self._resolve(inputs)
        except ValueError as e:
            return ToolResult(success=False, error=str(e))

        seed = self._seed(inputs)
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "duration": inputs.get("duration"),
            "aspect_ratio": mag.normalize_ratio(inputs.get("aspect_ratio"), _ASPECT_RATIOS),
            "camera_fixed": inputs.get("camera_fixed"),
            "seed": seed,
        }
        if spec.audio:
            payload["sound_effects"] = inputs.get("sound_effects")
            payload["no_music"] = inputs.get("no_music")

        try:
            if inputs.get("image"):
                payload["image"] = mag.as_input(inputs["image"])
            if inputs.get("image_end"):
                payload["image_end"] = mag.as_input(inputs["image_end"])
            if inputs.get("reference_images"):
                payload["reference_images"] = [mag.as_input(r) for r in inputs["reference_images"]]
        except Exception as e:
            return ToolResult(success=False, error=f"Could not read a reference image: {e}")

        result = self._generate(
            inputs,
            endpoint,
            payload,
            model=model,
            status_path=spec.status_for(endpoint),
            data_extra={
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "widescreen_16_9"),
                "native_audio": bool(spec.audio and inputs.get("sound_effects", True)),
            },
        )
        if result.success:
            from tools.video._shared import probe_output

            result.data.update(probe_output(Path(result.data["output_path"])))
            result.seed = seed
        return result
