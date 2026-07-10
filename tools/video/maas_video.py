"""DolphinLitePark MaaS platform video generation tool.

Calls the internal MaaS gateway at /v1/video/generations using an async
polling pattern. Supports text-to-video, image-to-video, reference-to-video
and video-edit across 17 models from Volcengine Seedance, DashScope Wan /
HappyHorse, H100/LTX, H100/Wan2.2 and the fanya alias.

Gateway base URL: https://api.aiapbot.com (override via MAAS_API_BASE)
Auth:            Authorization: Bearer <MAAS_API_KEY>

Reference-image field names are NOT uniform across model families (per
docs/multimodal-call-guide-v4.md) — sending the wrong field name for a model
doesn't error, it just silently drops the reference, so this matters more
than it looks:
  - leapfast/ltx-2.3, leapfast/wan2.2: `image` (base64/data-uri, preferred)
    | `image_url` (public URL) | `image_base64` (explicit, highest
    priority) — mutually exclusive.
  - happyhorse-1.0-i2v / -r2v: `image` (URL only, >=300x300px) — note this
    is a URL despite sharing a field name with LTX/Wan2.2's base64 field.
  - volcengine Seedance family: no standard-DTO image field is documented
    at all — only a native-passthrough `content: [...]` array (see
    MaasVideo._build_payload). Also: image_to_video/reference_to_video for
    this family must NOT include duration_seconds, or the upstream
    Volcengine API rejects it with InvalidParameter (400).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# Default poll interval recommended by the gateway (seconds)
_POLL_INTERVAL = 5
# Give up after this many seconds total
_POLL_TIMEOUT = 600


class MaasVideo(BaseTool):
    name = "maas_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "maas"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MAAS_API_KEY"]
    install_instructions = (
        "Set MAAS_API_KEY to your DolphinLitePark API key (sk-dlp-...).\n"
        "Optionally set MAAS_API_BASE to override the gateway URL\n"
        "(default: https://api.aiapbot.com)."
    )
    # seedance-2-0 covers the volcengine/doubao-seedance* and fanya/*
    # models; ltx2 covers leapfast/ltx-2.3 specifically (same underlying
    # LTX-2.3 22B model as the standalone tools/ltx2.py — see that skill's
    # "MaaS Gateway Route" note for what does/doesn't carry over).
    agent_skills = ["ai-video-gen", "seedance-2-0", "ltx2"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video", "video_edit"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_edit": True,
        "native_audio": True,
        "cinematic_quality": True,
        "multiple_resolutions": True,
    }
    best_for = [
        "internal MaaS quota — billed in CNY, no external API key needed",
        "Seedance 2.0 cinematic T2V/I2V (volcengine/doubao-seedance-2.0)",
        "HappyHorse 1.0 high-end production (720p–1080p)",
        "Wan 2.7 cost-effective I2V and video-edit",
        "LTX-2.3 via self-hosted H100 GPU cluster",
        "leapfast/wan2.2: cheaper/faster H100 T2V+I2V previews when the clip doesn't need audio",
    ]
    not_good_for = [
        "offline / air-gapped environments",
        "access without a valid MAAS_API_KEY (sk-dlp-...)",
    ]
    fallback_tools = ["seedance_video", "wan_video", "kling_video"]

    # ── Model catalogue (sourced from maas.aiapbot.com/models, 2026-06-28;
    # leapfast/wan2.2 added 2026-07-08 per docs/multimodal-call-guide-v4.md) ──
    # 17 video models across 4 provider families.
    # Pricing is in CNY per second of generated video.
    MODELS = {
        # ── Volcengine Seedance ───────────────────────────────────────────────
        # Recommended default: cinematic quality, 3D camera motion
        "volcengine/doubao-seedance-2.0":        {"ops": ["t2v", "i2v"], "price_480p": 0.60, "price_720p": 1.00},
        "volcengine/doubao-seedance-2.0-fast":   {"ops": ["t2v", "i2v"], "price_480p": 0.63, "price_720p": 1.42},
        "volcengine/doubao-seedance-1.5-pro":    {"ops": ["t2v", "i2v"], "price_720p": 1.04},
        "volcengine/doubao-seedance-1.0-pro":    {"ops": ["t2v", "i2v"], "price_720p": 0.65},
        "volcengine/doubao-seedance-1.0-pro-fast": {"ops": ["t2v"],      "price_720p": 1.19},
        # fanya alias → same Seedance 2.0 backend
        "fanya/seedance2.0":                     {"ops": ["t2v", "i2v"], "price_480p": 0.75, "price_720p": 1.25},
        # ── DashScope Wan 2.7 ────────────────────────────────────────────────
        "wan2.7-i2v":                            {"ops": ["i2v"],        "price_720p": 0.22},
        "wan2.7-videoedit":                      {"ops": ["video_edit"], "price_720p": 0.22},
        # ── DashScope Wanx 2.1 (per-clip billing, not per-second) ───────────
        "wanx2.1-t2v-plus":                      {"ops": ["t2v"],        "price_per_clip": 0.83},
        "wanx2.1-t2v-turbo":                     {"ops": ["t2v"],        "price_per_clip": 0.50},
        "wanx2.1-i2v-plus":                      {"ops": ["i2v"],        "price_per_clip": 0.83},
        # ── DashScope HappyHorse 1.0 (high-end) ─────────────────────────────
        "happyhorse-1.0-t2v":                    {"ops": ["t2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-i2v":                    {"ops": ["i2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-r2v":                    {"ops": ["r2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-video-edit":             {"ops": ["video_edit"], "price_720p": 1.17, "price_1080p": 2.08},
        # ── H100 Self-hosted GPU Cluster ─────────────────────────────────────
        # i2v confirmed live 2026-07-10 (submit -> succeeded, output correctly
        # conditioned on the reference frame) — the "t2v only" note from
        # 2026-06-28 undersold this route; see image_strength/image_frame_idx
        # in input_schema for the params this operation accepts.
        "leapfast/ltx-2.3":                          {"ops": ["t2v", "i2v"], "price_480p": 0.50, "price_720p": 0.70},
        # Lighter/faster than LTX-2.3, same H100 cluster. No audio track —
        # route to leapfast/ltx-2.3 instead if the caller needs sound.
        "leapfast/wan2.2":                           {"ops": ["t2v", "i2v"], "price_720p": 0.35},
    }
    DEFAULT_MODEL = "volcengine/doubao-seedance-2.0"

    # Model families needing payload shapes that diverge from the standard
    # DTO built below — see the module docstring for why.
    _SEEDANCE_MODELS = {
        "volcengine/doubao-seedance-2.0",
        "volcengine/doubao-seedance-2.0-fast",
        "volcengine/doubao-seedance-1.5-pro",
        "volcengine/doubao-seedance-1.0-pro",
        "volcengine/doubao-seedance-1.0-pro-fast",
        "fanya/seedance2.0",
    }
    _HAPPYHORSE_I2V_MODELS = {"happyhorse-1.0-i2v", "happyhorse-1.0-r2v"}
    _WAN22_SIZE_BY_ASPECT = {"16:9": "1280*704", "9:16": "704*1280", "1:1": "1280*704"}

    # Maps the public `operation` enum to the MODELS[model]["ops"] short codes,
    # so execute() can validate a request against what the chosen model
    # actually supports.
    _OPERATION_TO_OP_CODE = {
        "text_to_video": "t2v",
        "image_to_video": "i2v",
        "reference_to_video": "r2v",
        "video_edit": "video_edit",
    }

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Video generation prompt"},
            "model": {
                "type": "string",
                "description": (
                    "Gateway model ID. Available models (17 total):\n"
                    "T2V: volcengine/doubao-seedance-2.0 (default), volcengine/doubao-seedance-2.0-fast, "
                    "volcengine/doubao-seedance-1.5-pro, volcengine/doubao-seedance-1.0-pro, "
                    "volcengine/doubao-seedance-1.0-pro-fast, fanya/seedance2.0, "
                    "wanx2.1-t2v-plus, wanx2.1-t2v-turbo, happyhorse-1.0-t2v, leapfast/ltx-2.3, "
                    "leapfast/wan2.2 (no audio track — use leapfast/ltx-2.3 if sound is needed)\n"
                    "I2V: wan2.7-i2v, wanx2.1-i2v-plus, happyhorse-1.0-i2v, leapfast/wan2.2, "
                    "leapfast/ltx-2.3 (confirmed live 2026-07-10), "
                    "volcengine/doubao-seedance-2.0 (and other seedance variants — routed via "
                    "native passthrough, see image_url)\n"
                    "R2V: happyhorse-1.0-r2v\n"
                    "Edit: wan2.7-videoedit, happyhorse-1.0-video-edit"
                ),
                "default": "volcengine/doubao-seedance-2.0",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "video_edit"],
                "default": "text_to_video",
            },
            "duration_seconds": {
                "type": "integer",
                "enum": [5, 10],
                "default": 5,
                "description": "Clip duration in seconds",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "default": "720p",
                "description": "Output resolution (affects billing tier)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "audio": {
                "type": "boolean",
                "default": True,
                "description": "Include audio track in generated video",
            },
            "image_url": {
                "type": "string",
                "description": (
                    "Public image URL for image_to_video/reference_to_video. "
                    "Routed to the correct field name per model family "
                    "internally (see module docstring) — always pass the URL "
                    "here regardless of which model you picked."
                ),
            },
            "image_base64": {
                "type": "string",
                "description": (
                    "data:image/...;base64,... reference image, for models "
                    "that accept base64 directly (leapfast/ltx-2.3, "
                    "leapfast/wan2.2). Takes priority over image_url when set."
                ),
            },
            "image_strength": {
                "type": "number",
                "default": 0.8,
                "description": "leapfast/ltx-2.3 only: reference-frame lock strength, 0 (ignore) to 1 (hard lock).",
            },
            "output_path": {"type": "string", "description": "Local path to save the MP4"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["prompt", "model", "duration_seconds", "resolution"]
    side_effects = ["writes video file to output_path", "calls MaaS gateway API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and visual quality"
    ]

    def _api_key(self) -> str | None:
        return os.environ.get("MAAS_API_KEY")

    def _base_url(self) -> str:
        return os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Return estimated cost in CNY (not USD — MaaS bills internally in CNY)."""
        model = inputs.get("model", self.DEFAULT_MODEL)
        info = self.MODELS.get(model, {})
        duration = inputs.get("duration_seconds", 5)
        resolution = inputs.get("resolution", "720p")

        if "price_per_clip" in info:
            return info["price_per_clip"]

        price_key = f"price_{resolution}"
        rate = info.get(price_key) or info.get("price_720p") or info.get("price_480p") or 0.0
        return round(rate * duration, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = inputs.get("duration_seconds", 5)
        # Seedance 2.0 typically takes 60-120s; longer clips take more time
        return 90.0 + (duration - 5) * 15.0

    def _build_payload(
        self, model: str, operation: str, inputs: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Build the gateway request payload (and any extra headers) for this
        model family. See the module docstring for why this can't be one
        shape shared across every model."""
        prompt = inputs["prompt"]
        image_url = inputs.get("image_url")
        image_b64 = inputs.get("image_base64")
        wants_reference = operation in ("image_to_video", "reference_to_video")

        if model in self._SEEDANCE_MODELS and wants_reference:
            # No standard-DTO image field is documented for this family —
            # only native passthrough. duration_seconds is deliberately
            # omitted: Volcengine's own API rejects it on i2v/r2v with a 400
            # InvalidParameter error.
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            ref = image_b64 or image_url
            if ref:
                content.append({"type": "image_url", "image_url": {"url": ref}})
            payload: dict[str, Any] = {"model": f"native/{model}", "content": content}
            if inputs.get("aspect_ratio"):
                payload["ratio"] = inputs["aspect_ratio"]
            return payload, {"X-DLP-Passthrough": "true"}

        payload = {
            "model": model,
            "prompt": prompt,
            "duration_seconds": inputs.get("duration_seconds", 5),
            "resolution": inputs.get("resolution", "720p"),
            "audio": inputs.get("audio", True),
        }
        if inputs.get("aspect_ratio"):
            payload["ratio"] = inputs["aspect_ratio"]

        if wants_reference:
            if model in self._HAPPYHORSE_I2V_MODELS:
                # HappyHorse's standard DTO takes the reference as a plain
                # URL under `image` — NOT `image_url` (that field name is
                # only meaningful to the LTX/Wan2.2 family below).
                if image_url:
                    payload["image"] = image_url
            else:
                # leapfast/ltx-2.3, leapfast/wan2.2, and the DashScope Wan/
                # Wanx models: image_base64 > image_url priority, matching
                # the gateway's documented precedence for this family.
                if image_b64:
                    payload["image"] = image_b64
                elif image_url:
                    payload["image_url"] = image_url
                if model == "leapfast/ltx-2.3":
                    payload["image_strength"] = inputs.get("image_strength", 0.8)

        if model == "leapfast/wan2.2":
            # No resolution enum or audio track for this model — it uses its
            # own fixed size grid instead.
            payload.pop("resolution", None)
            payload.pop("audio", None)
            payload["size"] = self._WAN22_SIZE_BY_ASPECT.get(
                inputs.get("aspect_ratio", "16:9"), "1280*704"
            )

        return payload, {}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MAAS_API_KEY not set. " + self.install_instructions,
            )

        base_url = self._base_url()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        model = inputs.get("model", self.DEFAULT_MODEL)
        operation = inputs.get("operation", "text_to_video")
        resolution = inputs.get("resolution", "720p")

        # Each model declares which ops it actually supports (MODELS[model]
        # ["ops"]). Without this check, requesting image_to_video/
        # reference_to_video against a t2v-only model (e.g. happyhorse-1.0-t2v)
        # silently drops the image_url from the payload below and returns a
        # normal-looking text-to-video clip — the caller has no way to tell
        # the reference was ignored short of comparing pixels across shots.
        # That's exactly how a multi-shot consistency pass can burn real
        # money on 4 independent generations before anyone notices none of
        # them honored the reference. Fail loud, before the paid API call.
        model_info = self.MODELS.get(model)
        if model_info is None:
            return ToolResult(
                success=False,
                error=f"Unknown model: {model!r}. See MaasVideo.MODELS for the supported catalogue.",
            )
        op_code = self._OPERATION_TO_OP_CODE.get(operation)
        if op_code is not None and op_code not in model_info["ops"]:
            supported = [
                m for m, info in self.MODELS.items() if op_code in info["ops"]
            ]
            return ToolResult(
                success=False,
                error=(
                    f"Model {model!r} does not support operation {operation!r} "
                    f"(it only supports: {model_info['ops']}). "
                    f"Models that support {operation!r}: {supported}"
                ),
            )

        payload, extra_headers = self._build_payload(model, operation, inputs)
        headers.update(extra_headers)

        start = time.time()

        # ── Step 1: Submit job ────────────────────────────────────────────────
        try:
            resp = requests.post(
                f"{base_url}/v1/video/generations",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS submit failed: {e}")

        job_data = resp.json()
        job_id = job_data.get("job_id")
        if not job_id:
            return ToolResult(
                success=False,
                error=f"No job_id in gateway response: {job_data}",
            )

        # ── Step 2: Poll for completion ───────────────────────────────────────
        # The job is already submitted and will be billed regardless, so tolerate
        # transient poll blips (502/504/reset/timeout) instead of abandoning a
        # paid generation on the first one.
        deadline = start + _POLL_TIMEOUT
        poll_errors = 0
        _MAX_POLL_ERRORS = 5
        while time.time() < deadline:
            time.sleep(_POLL_INTERVAL)
            try:
                poll_resp = requests.get(
                    f"{base_url}/v1/video/jobs/{job_id}",
                    headers=headers,
                    timeout=15,
                )
                poll_resp.raise_for_status()
            except Exception as e:
                poll_errors += 1
                if poll_errors >= _MAX_POLL_ERRORS:
                    return ToolResult(
                        success=False,
                        error=f"MaaS poll failed {poll_errors}x (last: {e}); job_id={job_id}",
                    )
                continue  # transient — retry on the next interval
            poll_errors = 0

            status_data = poll_resp.json()
            status = status_data.get("status", "unknown")

            if status == "succeeded":
                break
            if status in ("failed", "cancelled"):
                err = status_data.get("error") or f"Job {status}"
                return ToolResult(success=False, error=f"MaaS video generation {status}: {err}")
            # still processing — keep polling

        else:
            return ToolResult(
                success=False,
                error=f"MaaS video generation timed out after {_POLL_TIMEOUT}s (job_id={job_id})",
            )

        # ── Step 3: Download result ───────────────────────────────────────────
        output_path = Path(inputs.get("output_path", f"maas_{job_id}.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            dl_resp = requests.get(
                f"{base_url}/v1/video/jobs/{job_id}/result",
                headers=headers,
                stream=True,
                timeout=120,
            )
            dl_resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS video download failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "maas",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": operation,
                "resolution": resolution,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "job_id": job_id,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            # MaaS bills in CNY per second of generated video; report the
            # resolution/duration-based charge so cost tracking is meaningful.
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
